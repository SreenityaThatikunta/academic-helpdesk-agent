"""Deterministic safety nets around the LLM."""

import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse
from google.genai import types

from helpdesk.tools.unanswered import LOGGED_FLAG, log_unanswered_question

REFUSAL = "I don't know the answer"
REFUSAL_SENTENCE = "I don't know the answer to that. I've forwarded your question to the academic office."
# llama3.1 sometimes "calls" a tool by printing it: {"name": "x", "parameters": {...}}
TEXT_TOOL_CALL = re.compile(r'\{\s*"name"\s*:\s*"\w+"\s*,\s*"parameters"\s*:\s*\{.*?\}\s*\}', re.S)
SOURCE_LINE = re.compile(r"^\s*\**\s*Sources?\s*\**\s*:.*$", re.I | re.M)


def log_refusals(callback_context: CallbackContext, llm_response: LlmResponse) -> None:
    """after_model_callback: if the model refuses but skipped log_unanswered_question, log it here.
    Also strips tool calls the model printed as JSON text instead of actually calling.

    Small models sometimes write the refusal sentence without calling the tool; the
    assignment requires every unanswered question to reach a human, so don't rely on the prompt.
    """
    parts = (llm_response.content.parts if llm_response.content else None) or []
    if any(p.function_call for p in parts):
        return None  # the tool call (often log_unanswered_question itself) hasn't run yet
    for p in parts:
        if p.text and TEXT_TOOL_CALL.search(p.text):
            p.text = TEXT_TOOL_CALL.sub("", p.text).strip()
    text = "".join(p.text or "" for p in parts)
    if REFUSAL.lower() not in text.lower():
        return None
    # A refusal has nothing to cite; models sometimes add "Source: <the refusal again>"
    for p in parts:
        if p.text:
            p.text = SOURCE_LINE.sub("", p.text).strip()
    if callback_context.state.get(LOGGED_FLAG):
        return None
    user = callback_context.user_content
    question = "".join(p.text or "" for p in (user.parts if user else [])) or "(unknown question)"
    log_unanswered_question(question, f"auto-logged by {callback_context.agent_name}: refused without calling the tool")
    callback_context.state[LOGGED_FLAG] = True
    return None


def drop_transfer_noise(callback_context: CallbackContext, llm_request) -> None:
    """before_model_callback for specialists: remove transfer_to_agent bookkeeping from the context.

    After a transfer ADK shows the specialist the router's `transfer_to_agent` call and its
    `None` result as extra "For context: ..." user messages, so the newest user turn the model
    sees is noise instead of the student's question. 8B models then skip instructions such as
    "ask for the programme first". Real messages from other agents are kept.
    """
    contents = llm_request.contents or []

    def text(c):
        return "".join(p.text or "" for p in (c.parts or []))

    drop = set()
    for i, c in enumerate(contents):
        if c.role == "user" and "`transfer_to_agent`" in text(c):
            drop.add(i)
            # the "For context: ..." preamble ADK puts right before each quoted block
            if i > 0 and text(contents[i - 1]).startswith("For context:"):
                drop.add(i - 1)
    if drop:
        llm_request.contents = [c for i, c in enumerate(contents) if i not in drop]
    return None


def standardize_router_refusal(callback_context: CallbackContext, llm_response: LlmResponse) -> None:
    """after_model_callback for the router: once it has logged a question as unanswerable, its reply
    must be the fixed refusal sentence (it sometimes paraphrased, e.g. "The academic office has been
    notified..."), so refusals look the same everywhere and are easy to detect."""
    parts = (llm_response.content.parts if llm_response.content else None) or []
    if not callback_context.state.get(LOGGED_FLAG) or any(p.function_call for p in parts):
        return None
    text = "".join(p.text or "" for p in parts).strip()
    if text and REFUSAL.lower() not in text.lower():
        for i, p in enumerate(parts):
            p.text = REFUSAL_SENTENCE if i == 0 else ""
    return None


# The student asks for something to be written: the only reason to hand a message to email_agent
EMAIL_REQUEST = re.compile(r"\b(e-?mail|mail|draft|write|compose|letter|message)\b", re.I)

# Keyword fallback routes used only when the router returns an empty message
FALLBACK_ROUTES = [
    (EMAIL_REQUEST, "email_agent"),
    (re.compile(r"\b(slot|teach(es|ing)?|instructor|professor|classroom|room|timings?|time ?table|"
                r"how many .*(courses|electives)|courses? (offered|floated))\b", re.I), "schedule_agent"),
]


def route_empty_router_reply(callback_context: CallbackContext, llm_response: LlmResponse):
    """after_model_callback for the router: qwen3 sometimes returns an empty message (no text, no
    tool call) and the student gets nothing. Replace it with a transfer chosen by keyword rules;
    anything unmatched goes to policy_agent, which can search and still refuse properly."""
    parts = (llm_response.content.parts if llm_response.content else None) or []
    if any(p.function_call for p in parts) or "".join(p.text or "" for p in parts).strip():
        return None
    user = callback_context.user_content
    question = "".join(p.text or "" for p in (user.parts if user else []))
    target = next((agent for pat, agent in FALLBACK_ROUTES if pat.search(question)), "policy_agent")
    call = types.FunctionCall(name="transfer_to_agent", args={"agent_name": target})
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))


def _previous_reply(callback_context: CallbackContext) -> tuple[str | None, str]:
    """(agent, text) of the last specialist reply before the current student message."""
    for ev in reversed(callback_context.session.events):
        if ev.invocation_id == callback_context.invocation_id or ev.author in ("user", callback_context.agent_name):
            continue
        text = "".join(p.text or "" for p in ((ev.content.parts if ev.content else None) or [])).strip()
        if text:
            return ev.author, text
    return None, ""


def keep_email_agent_for_email_requests(callback_context: CallbackContext, llm_response: LlmResponse) -> None:
    """after_model_callback for the router: hand a message to email_agent only when it asks for an email
    to be written, or answers a question the email agent just asked ("Did you mean CSL7650?" -> "yes").
    Otherwise send it to policy_agent. After a few turns qwen3 routed rule questions that mention a
    make-up exam or illness ("Can I get a make-up exam if I miss the Minor due to illness?") to
    email_agent, whose description lists those topics as reasons to write an email."""
    parts = (llm_response.content.parts if llm_response.content else None) or []
    for p in parts:
        call = p.function_call
        if not call or call.name != "transfer_to_agent" or (call.args or {}).get("agent_name") != "email_agent":
            continue
        user = callback_context.user_content
        question = "".join(q.text or "" for q in (user.parts if user else []))
        if EMAIL_REQUEST.search(question):
            continue
        agent, reply = _previous_reply(callback_context)
        if agent == "email_agent" and "?" in reply:
            continue
        call.args = {**call.args, "agent_name": "policy_agent"}
    return None


# ADK's transcript of another agent's tool result: "[agent] `tool` tool returned result: {...}"
TOOL_RESULT_TRANSCRIPT = re.compile(r"tool returned result:?", re.I)


def trim_history(callback_context: CallbackContext, llm_request) -> None:
    """before_model_callback: shrink earlier turns. Their tool results (retrieved passages, course
    lists) are replaced by a short placeholder; the tool calls, user messages and agent answers stay.
    In a long CLI session the old results were re-sent on every question, pushing prompts past the
    8k context window (truncation, ~70 s answers). Tool calls must stay visible: when they were
    removed too, the model imitated the history and answered without calling tools (made-up facts).
    The current turn (from the latest student message) is untouched."""
    contents = llm_request.contents or []
    user = callback_context.user_content
    question = "".join(p.text or "" for p in (user.parts if user else [])).strip()

    def text(c):
        return "".join(p.text or "" for p in (c.parts or [])).strip()

    current = next((i for i in range(len(contents) - 1, -1, -1)
                    if contents[i].role == "user" and question and text(contents[i]) == question), None)
    if not current:
        return None
    trimmed = []
    for c in contents[:current]:
        parts = []
        for p in c.parts or []:
            if p.function_response:
                parts.append(types.Part(function_response=types.FunctionResponse(
                    id=p.function_response.id, name=p.function_response.name,
                    response={"note": "result omitted from history; call the tool again if you need it"})))
            elif p.text and TOOL_RESULT_TRANSCRIPT.search(p.text):
                parts.append(types.Part(text=TOOL_RESULT_TRANSCRIPT.split(p.text)[0] + "tool returned result: (omitted)"))
            else:
                parts.append(p)
        trimmed.append(types.Content(role=c.role, parts=parts))
    llm_request.contents = trimmed + list(contents[current:])
    return None
