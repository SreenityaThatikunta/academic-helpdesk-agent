"""Run questions through an ADK agent and capture the answer, tool calls and routing.

Used by the CLI (one long session) and by the evaluation (a fresh session per question).
"""

import re
import time
import uuid
from dataclasses import dataclass, field

from google.adk.runners import InMemoryRunner
from google.genai import types

APP = "academic_helpdesk"
THINK_RE = re.compile(r"<think>.*?</think>", re.S)


@dataclass
class Turn:
    question: str
    answer: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # {agent, name, args}
    tool_results: list[dict] = field(default_factory=list)  # {agent, name, response}
    agents: list[str] = field(default_factory=list)  # authors of events, in order (routing)
    seconds: float = 0.0
    error: str = ""


class Helpdesk:
    def __init__(self, agent, user_id: str = "student"):
        self.agent = agent
        self.runner = InMemoryRunner(agent=agent, app_name=APP)
        self.user_id = user_id
        self.session_id: str | None = None

    async def new_session(self) -> str:
        s = await self.runner.session_service.create_session(app_name=APP, user_id=self.user_id,
                                                             session_id=uuid.uuid4().hex)
        self.session_id = s.id
        return s.id

    async def ask(self, question: str, fresh: bool = False, on_event=None) -> Turn:
        if fresh or self.session_id is None:
            await self.new_session()
        turn, start = Turn(question), time.perf_counter()
        msg = types.Content(role="user", parts=[types.Part(text=question)])
        try:
            async for event in self.runner.run_async(user_id=self.user_id, session_id=self.session_id, new_message=msg):
                if event.author and event.author != "user" and (not turn.agents or turn.agents[-1] != event.author):
                    turn.agents.append(event.author)
                for call in event.get_function_calls():
                    turn.tool_calls.append({"agent": event.author, "name": call.name, "args": dict(call.args or {})})
                    if on_event:
                        on_event("call", event.author, call.name, dict(call.args or {}))
                for resp in event.get_function_responses():
                    turn.tool_results.append({"agent": event.author, "name": resp.name, "response": resp.response})
                if event.is_final_response() and event.content and event.content.parts:
                    text = "".join(p.text or "" for p in event.content.parts)
                    if text.strip():
                        turn.answer = THINK_RE.sub("", text).strip()
        except Exception as e:  # keep the eval running if one question breaks
            turn.error = f"{type(e).__name__}: {e}"
        turn.seconds = round(time.perf_counter() - start, 2)
        return turn
