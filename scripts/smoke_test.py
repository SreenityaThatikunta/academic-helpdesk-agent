"""Phase 0 smoke test: ADK agent -> LiteLLM -> Ollama, with one tool call,
plus one embedding call to the Ollama embedding model.

Usage: .venv/bin/python scripts/smoke_test.py [model]
"""

import asyncio
import sys

import ollama
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from helpdesk import config  # noqa: E402


def get_course_slot(course_code: str) -> dict:
    """Returns the time table slot for a course code."""
    return {"course_code": course_code.upper(), "slot": "D", "source": "smoke_test"}


async def main(model: str) -> None:
    emb = ollama.embed(model=config.EMBED_MODEL, input="attendance requirement")
    print(f"[embed] {config.EMBED_MODEL}: dim={len(emb['embeddings'][0])}")

    agent = LlmAgent(
        name="smoke",
        model=LiteLlm(model=model),
        instruction="Use the get_course_slot tool to answer slot questions. Reply in one sentence. /no_think",
        tools=[get_course_slot],
    )
    runner = InMemoryRunner(agent=agent, app_name="smoke")
    session = await runner.session_service.create_session(app_name="smoke", user_id="u")
    msg = types.Content(role="user", parts=[types.Part(text="What is the slot for CSL7570?")])

    called = False
    async for event in runner.run_async(user_id="u", session_id=session.id, new_message=msg):
        for call in event.get_function_calls():
            called = True
            print(f"[tool call] {call.name}({call.args})")
        if event.is_final_response() and event.content and event.content.parts:
            print(f"[{model}] {event.content.parts[0].text.strip()}")
    print("PASS" if called else "FAIL: no tool call")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else config.MODEL))
