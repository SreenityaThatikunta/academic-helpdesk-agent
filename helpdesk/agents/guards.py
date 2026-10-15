"""Deterministic safety nets around the LLM."""

import re

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmResponse

from helpdesk.tools.unanswered import LOGGED_FLAG, log_unanswered_question

REFUSAL = "I don't know the answer"
# llama3.1 sometimes "calls" a tool by printing it: {"name": "x", "parameters": {...}}
TEXT_TOOL_CALL = re.compile(r'\{\s*"name"\s*:\s*"\w+"\s*,\s*"parameters"\s*:\s*\{.*?\}\s*\}', re.S)


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
    if REFUSAL.lower() not in text.lower() or callback_context.state.get(LOGGED_FLAG):
        return None
    user = callback_context.user_content
    question = "".join(p.text or "" for p in (user.parts if user else [])) or "(unknown question)"
    log_unanswered_question(question, f"auto-logged by {callback_context.agent_name}: refused without calling the tool")
    callback_context.state[LOGGED_FLAG] = True
    return None
