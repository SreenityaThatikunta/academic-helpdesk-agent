"""Run the evaluation set against model x mode x repeat and save raw results.

Usage:
    .venv/bin/python eval/run_eval.py                         # all models, both modes, 3 repeats
    .venv/bin/python eval/run_eval.py --models ollama_chat/qwen3:8b --modes multi --repeats 1
    .venv/bin/python eval/run_eval.py --only P01 S01          # subset of question ids

Each run writes eval/results/<mode>__<model>__r<k>/raw.jsonl (one line per turn) plus that run's
own drafts/ and unanswered.jsonl. Finished runs are skipped, so an interrupted eval can resume.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from helpdesk import config  # noqa: E402
from helpdesk.agents import build_agent  # noqa: E402
from helpdesk.runner import Helpdesk  # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
RESULTS = ROOT / "eval" / "results"
MODELS = ["ollama_chat/qwen3:8b", "ollama_chat/llama3.1:8b"]
MODES = ["single", "multi"]


def run_name(mode: str, model: str, rep: int) -> str:
    return f"{mode}__{model.split('/')[-1].replace(':', '-')}__r{rep}"


def _lines(path: Path) -> int:
    return len(path.read_text().splitlines()) if path.exists() else 0


def _truncate(obj, limit: int = 1500):
    s = json.dumps(obj, ensure_ascii=False, default=str)
    return s if len(s) <= limit else s[:limit] + "...<truncated>"


async def run_one(mode: str, model: str, rep: int, items: list[dict], force: bool) -> None:
    name = run_name(mode, model, rep)
    out_dir = RESULTS / name
    raw = out_dir / "raw.jsonl"
    expected_turns = sum(len(it["turns"]) for it in items)
    if raw.exists() and _lines(raw) == expected_turns and not force:
        print(f"skip {name} (done)")
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    raw.write_text("")
    # Isolate this run's side effects: tools read these at call time
    config.DRAFTS_DIR = out_dir / "drafts"
    config.UNANSWERED_LOG = out_dir / "unanswered.jsonl"
    for f in config.DRAFTS_DIR.glob("*.md") if config.DRAFTS_DIR.exists() else []:
        f.unlink()
    config.UNANSWERED_LOG.unlink(missing_ok=True)

    desk = Helpdesk(build_agent(mode, model))
    start = time.perf_counter()
    for it in items:
        await desk.new_session()  # fresh session per item; turns of one item share it
        for turn_no, question in enumerate(it["turns"]):
            logged_before = _lines(config.UNANSWERED_LOG)
            drafts_before = set(config.DRAFTS_DIR.glob("*.md")) if config.DRAFTS_DIR.exists() else set()
            t = await desk.ask(question)
            new_drafts = sorted((set(config.DRAFTS_DIR.glob("*.md")) if config.DRAFTS_DIR.exists() else set())
                                - drafts_before)
            rec = {
                "run": name, "mode": mode, "model": model, "repeat": rep,
                "id": it["id"], "category": it["category"], "turn": turn_no, "question": question,
                "answer": t.answer, "error": t.error, "seconds": t.seconds, "agents": t.agents,
                "tool_calls": t.tool_calls,
                "tool_results": [{"agent": r["agent"], "name": r["name"], "response": _truncate(r["response"])}
                                 for r in t.tool_results],
                "logged": _lines(config.UNANSWERED_LOG) > logged_before,
                "drafts": [{"file": d.name, "text": d.read_text()} for d in new_drafts],
            }
            with raw.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            flag = "ERR" if t.error else "ok "
            print(f"  [{name}] {flag} {it['id']}.{turn_no} {t.seconds:5.1f}s {' > '.join(t.agents)}", flush=True)
    print(f"done {name} in {time.perf_counter() - start:.0f}s", flush=True)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=MODELS)
    ap.add_argument("--modes", nargs="+", default=MODES)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--only", nargs="*", help="question ids to run")
    ap.add_argument("--force", action="store_true", help="re-run finished runs")
    args = ap.parse_args()

    items = [json.loads(line) for line in QUESTIONS.read_text().splitlines() if line.strip()]
    if args.only:
        items = [it for it in items if it["id"] in set(args.only)]
    # Repeat-major order: every config finishes repeat 1 before any starts repeat 2, so a
    # partial eval still covers all configs
    for rep in range(1, args.repeats + 1):
        for model in args.models:
            for mode in args.modes:
                await run_one(mode, model, rep, items, args.force)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    for name in ("LiteLLM", "google_adk", "google.adk"):
        logging.getLogger(name).setLevel(logging.ERROR)
    asyncio.run(main())
