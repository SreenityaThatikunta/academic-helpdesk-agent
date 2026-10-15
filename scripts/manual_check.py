"""Phase 4 manual check: the assignment's example questions on one or more models.

Usage: .venv/bin/python scripts/manual_check.py [--mode single] [model ...]
Writes eval/results/manual_<mode>_<model>.json
"""

import argparse
import asyncio
import json
import logging
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helpdesk.agents import build_agent  # noqa: E402
from helpdesk.runner import Helpdesk  # noqa: E402

QUESTIONS = [
    "What is the attendance requirement to sit in the Major exam?",
    "What is the slot for the course Autonomous Systems?",
    "How many 400 level electives have been floated by the Humanities department in this semester?",
    "How many Open Elective credits do I need to earn in order to get a B.Tech. Degree?",
    "Write an email to the course instructor of CSL7570 that I need leave for 2 days",
    "What are the available dining options on the campus?",
    "What is the best way to reach the campus from Jodhpur city center?",
]


async def run(mode: str, model: str) -> list[dict]:
    desk = Helpdesk(build_agent(mode, model))
    out = []
    for q in QUESTIONS:
        t = await desk.ask(q, fresh=True)
        calls = ", ".join(f"{c['name']}({json.dumps(c['args'], ensure_ascii=False)[:70]})" for c in t.tool_calls)
        print(f"\n### Q: {q}\n[{t.seconds}s] tools: {calls or '-'}")
        print(t.error or t.answer)
        out.append({"question": q, "answer": t.answer, "tool_calls": t.tool_calls, "agents": t.agents,
                    "seconds": t.seconds, "error": t.error})
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="single")
    ap.add_argument("models", nargs="*", default=["ollama_chat/qwen3:8b", "ollama_chat/llama3.1:8b"])
    args = ap.parse_args()
    (ROOT / "eval" / "results").mkdir(parents=True, exist_ok=True)
    for model in args.models:
        print(f"\n================ {args.mode} · {model} ================")
        res = await run(args.mode, model)
        name = model.split("/")[-1].replace(":", "-")
        (ROOT / "eval" / "results" / f"manual_{args.mode}_{name}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    asyncio.run(main())
