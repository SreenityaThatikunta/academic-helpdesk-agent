"""Minimal web UI for the helpdesk: chat, sources and a document graph.

Usage:
    .venv/bin/python -m helpdesk.web.server                # http://localhost:8000, mode/model from .env
    .venv/bin/python -m helpdesk.web.server --mode multi --port 8080
"""

import argparse
import asyncio
import csv
import logging
import re
import warnings
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from helpdesk import config
from helpdesk.agents import build_agent
from helpdesk.runner import Helpdesk

STATIC = Path(__file__).parent / "static"
DATA = config.ROOT / "data"
FILE_NO = re.compile(r"^(\d{2})_")  # "26_Slot_System....xlsx" -> D26
DOC_REF = re.compile(r"\bD(\d{2})\b")


@lru_cache(maxsize=1)
def manifest() -> dict[str, dict]:
    with open(DATA / "manifest.csv", newline="") as f:
        return {r["doc_id"]: r for r in csv.DictReader(f)}


def _doc_for_title(citation: str) -> str | None:
    # citations are "<title>, p. 3"; titles may themselves contain commas, so match the longest prefix
    best = None
    for doc_id, row in manifest().items():
        if citation.startswith(row["title"]) and (best is None or len(row["title"]) > len(manifest()[best]["title"])):
            best = doc_id
    return best


def _doc_for_file(source: str) -> str | None:
    m = FILE_NO.match(source)
    return f"D{m.group(1)}" if m and f"D{m.group(1)}" in manifest() else None


def extract_sources(turn) -> list[dict]:
    """Documents the tools returned during a turn, cited ones first."""
    found: dict[str, dict] = {}

    def add(key, doc_id, label, snippet=""):
        entry = found.setdefault(key, {"doc_id": doc_id, "label": label, "snippets": [], "cited": False})
        if snippet and len(entry["snippets"]) < 3:
            entry["snippets"].append(snippet)

    for res in turn.tool_results:
        r = res["response"] if isinstance(res["response"], dict) else {}
        for hit in r.get("results") or []:
            if isinstance(hit, dict) and hit.get("citation"):
                doc_id = _doc_for_title(hit["citation"])
                add(hit["citation"], doc_id, hit["citation"], (hit.get("text") or "")[:400])
        src = r.get("source")
        for s in [src] if isinstance(src, str) else (src or []):
            doc_id = _doc_for_file(s)
            add(doc_id or s, doc_id, manifest()[doc_id]["title"] if doc_id else s)

    answer = turn.answer.lower()
    for e in found.values():
        title = manifest()[e["doc_id"]]["title"].lower() if e["doc_id"] else e["label"].lower()
        e["cited"] = title in answer or e["label"].lower() in answer
    return sorted(found.values(), key=lambda e: not e["cited"])


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


def create_app(mode: str, model: str) -> FastAPI:
    app = FastAPI(title="Academic Helpdesk")
    desk = Helpdesk(build_agent(mode, model))
    known: set[str] = set()
    lock = asyncio.Lock()  # one local model: answer one question at a time

    @app.get("/api/info")
    async def info():
        return {"mode": mode, "model": model, "semester": config.CURRENT_SEMESTER}

    @app.post("/api/chat")
    async def chat(body: ChatIn):
        if not body.message.strip():
            raise HTTPException(400, "empty message")
        async with lock:
            if body.session_id in known:
                desk.session_id = body.session_id
            else:  # new chat, or the server restarted since this chat began
                known.add(await desk.new_session())
            turn = await desk.ask(body.message.strip())
        return {
            "session_id": desk.session_id,
            "answer": turn.answer,
            "error": turn.error,
            "seconds": turn.seconds,
            "agents": turn.agents,
            "tool_calls": [{"agent": c["agent"], "name": c["name"]} for c in turn.tool_calls],
            "sources": extract_sources(turn),
        }

    @app.get("/api/graph")
    async def graph():
        docs = manifest()
        nodes = [{"id": d, "type": "doc", "title": r["title"], "category": r["category"], "date": r["date"],
                  "status": r["status"]} for d, r in docs.items()]
        links, seen = [], set()

        def link(a, b, kind):
            key = (min(a, b), max(a, b), kind)
            if a != b and key not in seen:
                seen.add(key)
                links.append({"source": a, "target": b, "kind": kind})

        for cat in sorted({r["category"] for r in docs.values()}):
            nodes.append({"id": f"#{cat}", "type": "tag", "title": cat.replace("_", " ")})
        for d, r in docs.items():
            link(d, f"#{r['category']}", "tag")
            for ref in DOC_REF.findall(r["notes"]):  # "Superseded by D01/D21", "see D31", ...
                if f"D{ref}" in docs:
                    link(d, f"D{ref}", "related")
        with open(DATA / "amendments.csv", newline="") as f:
            for r in csv.DictReader(f):
                link(r["doc_id"], r["superseded_by"], "amends")
        return {"nodes": nodes, "links": links}

    @app.get("/api/doc/{doc_id}")
    async def doc_file(doc_id: str):
        row = manifest().get(doc_id)
        if not row:
            raise HTTPException(404)
        path = (DATA / row["filename"]).resolve()
        if not path.is_relative_to(DATA.resolve()) or not path.exists():
            raise HTTPException(404)
        return FileResponse(path, content_disposition_type="inline")

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app


def main() -> None:
    import uvicorn

    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=config.MODE, choices=["single", "multi"])
    ap.add_argument("--model", default=config.MODEL)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    logging.getLogger("google_adk").setLevel(logging.ERROR)
    uvicorn.run(create_app(args.mode, args.model), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
