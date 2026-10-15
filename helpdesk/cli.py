"""Interactive chat with the helpdesk.

Usage:
    .venv/bin/python -m helpdesk.cli                       # REPL, mode/model from .env
    .venv/bin/python -m helpdesk.cli --model ollama_chat/llama3.1:8b
    .venv/bin/python -m helpdesk.cli --ask "What is the slot for Autonomous Systems?"
Commands inside the REPL: /new (fresh session), /unanswered (questions forwarded to a human), /quit
"""

import argparse
import asyncio
import json
import logging
import warnings

from rich.console import Console
from rich.markdown import Markdown

from helpdesk import config
from helpdesk.agents import build_agent
from helpdesk.runner import Helpdesk
from helpdesk.tools.unanswered import read_unanswered

console = Console()


def _show_call(kind, agent, name, args):
    console.print(f"  [dim]→ {agent}: {name}({json.dumps(args, ensure_ascii=False)[:160]})[/dim]")


async def _answer(desk: Helpdesk, question: str) -> None:
    with console.status("thinking…"):
        turn = await desk.ask(question, on_event=_show_call)
    if turn.error:
        console.print(f"[red]Error:[/red] {turn.error}")
    console.print(Markdown(turn.answer or "_(no answer)_"))
    console.print(f"[dim]({turn.seconds}s, agents: {' → '.join(turn.agents)})[/dim]\n")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=config.MODE, choices=["single", "multi"])
    ap.add_argument("--model", default=config.MODEL)
    ap.add_argument("--ask", help="ask one question and exit")
    args = ap.parse_args()

    desk = Helpdesk(build_agent(args.mode, args.model))
    if args.ask:
        await _answer(desk, args.ask)
        return

    console.print(f"[bold]IIT Jodhpur Academic Helpdesk[/bold]  [dim]{args.mode} · {args.model}[/dim]")
    console.print("[dim]Ask about regulations, courses, slots, exams, or ask me to draft an email. "
                  "/new, /unanswered, /quit[/dim]\n")
    while True:
        try:
            q = console.input("[bold cyan]you>[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q in ("/quit", "/exit"):
            break
        if q == "/unanswered":
            open_qs = read_unanswered()
            for e in open_qs:
                console.print(f"  [yellow]{e['id']}[/yellow] {e['timestamp']}  {e['question']}  [dim]({e['reason']})[/dim]")
            console.print(f"[dim]{len(open_qs)} open question(s) in {config.UNANSWERED_LOG}[/dim]")
            continue
        if q == "/new":
            await desk.new_session()
            console.print("[dim]new session[/dim]")
            continue
        await _answer(desk, q)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    # ADK warns about Gemini context caching on every multi-agent start; irrelevant for Ollama
    logging.getLogger("google_adk").setLevel(logging.ERROR)
    asyncio.run(main())
