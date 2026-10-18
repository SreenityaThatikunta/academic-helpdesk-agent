"""Minimal web UI for the helpdesk: chat, sources and a document graph.

Usage:
    .venv/bin/python -m helpdesk.web.server                # http://localhost:8000, mode/model from .env
    .venv/bin/python -m helpdesk.web.server --mode multi --port 8080
"""

import argparse
import asyncio
import csv
import json
import logging
import re
import warnings
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
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
        names = {e["label"].lower()}
        if e["doc_id"]:  # answers cite a document by title or, for spreadsheets, by file name
            row = manifest()[e["doc_id"]]
            names |= {row["title"].lower(), Path(row["filename"]).name.lower(), Path(row["filename"]).stem.lower()}
        e["cited"] = any(n in answer for n in names)
    return sorted(found.values(), key=lambda e: not e["cited"])


def _short(value, n=80) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= n else text[: n - 1] + "…"


def trace_call(name: str, args: dict) -> dict:
    """One step of the live trace: which tool, with the argument worth showing."""
    if name == "transfer_to_agent":
        return {"step": "handoff", "to": args.get("agent_name", "")}
    main = next((args[k] for k in ("query", "course", "course_or_instructor", "subject", "question", "department")
                 if args.get(k)), "")
    extra = {k: v for k, v in args.items() if k in ("document", "level") and v}
    return {"step": "call", "arg": _short(main), "extra": {k: _short(v, 40) for k, v in extra.items()}}


def trace_result(name: str, r) -> dict:
    """Short human summary of a tool result, plus the documents it touched (for the graph)."""
    r = r if isinstance(r, dict) else {}
    docs, ok, summary = [], True, ""
    if name.startswith("search_documents"):
        hits = r.get("results") or []
        docs = list(dict.fromkeys(d for d in (_doc_for_title(h.get("citation", "")) for h in hits) if d))
        ok = bool(r.get("found")) and bool(hits)
        summary = f"{len(hits)} passage{'s' * (len(hits) != 1)} from {', '.join(docs)}" if ok else "nothing relevant found"
    elif name in ("get_slot", "lookup_course"):
        if r.get("found"):
            c = r["courses"][0]
            summary = f"{c['course_code']} {c['course_name']}" + (f" · slot {', '.join(c['slots'])}" if c.get("slots") else "")
        else:
            ok = False
            sug = ", ".join(x["course_code"] for x in r.get("suggestions") or [])
            summary = "not offered this semester" + (f" · did you mean {sug}?" if sug else "")
    elif name == "list_courses":
        summary = f"{r.get('count', 0)} courses"
    elif name == "get_instructor_email":
        ok = bool(r.get("found"))
        summary = ", ".join(i["name"] for i in r.get("instructors") or []) or "no instructor found"
    elif name == "draft_email":
        ok = r.get("status") == "draft_saved"
        summary = "draft saved, not sent" if ok else r.get("message", "could not save draft")
    elif name == "log_unanswered_question":
        summary = f"forwarded to the academic office (ticket {r.get('ticket_id', '?')})"
    elif name == "transfer_to_agent":
        return {}
    src = r.get("source")
    for s in [src] if isinstance(src, str) else (src or []):
        if (d := _doc_for_file(s)) and d not in docs:
            docs.append(d)
    return {"ok": ok, "summary": summary, "docs": docs}


def extract_cards(turn) -> list[dict]:
    """Structured views of what the tools returned: course time table, email draft, course list."""
    cards, courses = [], {}
    calls = {c["name"]: c["args"] for c in turn.tool_calls}
    for res in turn.tool_results:
        r = res["response"] if isinstance(res["response"], dict) else {}
        if res["name"] in ("get_slot", "lookup_course") and r.get("found"):
            for c in r["courses"]:
                # get_slot adds the weekly schedule and exams; keep the richer record
                if c["course_code"] not in courses or "weekly_schedule" in c:
                    courses[c["course_code"]] = c
        elif res["name"] == "draft_email" and r.get("status") == "draft_saved":
            a = calls.get("draft_email", {})
            cards.append({"kind": "email", "to": a.get("to", ""), "cc": a.get("cc", ""), "subject": a.get("subject", ""),
                          "body": a.get("body", ""), "path": r.get("path", "")})
        elif res["name"] == "list_courses" and r.get("count"):
            cards.append({"kind": "courses", "count": r["count"], "filters": r.get("filters", {}),
                          "courses": r["courses"][:200]})
    cards[:0] = [{"kind": "course", **c} for c in list(courses.values())[:3]]
    return cards


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


def create_app(mode: str, model: str) -> FastAPI:
    app = FastAPI(title="Academic Helpdesk")
    desk = Helpdesk(build_agent(mode, model))
    known: set[str] = set()
    lock = asyncio.Lock()  # one local model: answer one question at a time

    async def answer(body: ChatIn, on_event=None) -> dict:
        async with lock:
            if on_event:
                on_event("start", None, None, None)
            if body.session_id in known:
                desk.session_id = body.session_id
            else:  # new chat, or the server restarted since this chat began
                known.add(await desk.new_session())
            turn = await desk.ask(body.message.strip(), on_event=on_event)
        return {
            "session_id": desk.session_id,
            "answer": turn.answer,
            "error": turn.error,
            "seconds": turn.seconds,
            "agents": turn.agents,
            "tool_calls": [{"agent": c["agent"], "name": c["name"]} for c in turn.tool_calls],
            "sources": extract_sources(turn),
            "cards": extract_cards(turn),
        }

    @app.get("/api/info")
    async def info():
        return {"mode": mode, "model": model, "semester": config.CURRENT_SEMESTER}

    @app.post("/api/chat")
    async def chat(body: ChatIn):
        if not body.message.strip():
            raise HTTPException(400, "empty message")
        return await answer(body)

    @app.post("/api/chat/stream")
    async def chat_stream(body: ChatIn):
        """Server-sent events: start, call, result (as the agent works), then done with the full answer."""
        if not body.message.strip():
            raise HTTPException(400, "empty message")
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(kind, agent, name, data):
            if kind == "start":
                queue.put_nowait({"type": "start"})
            elif kind == "call":
                queue.put_nowait({"type": "call", "agent": agent, "name": name, **trace_call(name, data)})
            elif kind == "result" and (summary := trace_result(name, data)):
                queue.put_nowait({"type": "result", "agent": agent, "name": name, **summary})

        async def work():
            try:
                queue.put_nowait({"type": "done", **await answer(body, on_event)})
            except Exception as e:  # noqa: BLE001 - report anything to the page
                queue.put_nowait({"type": "error", "message": f"{type(e).__name__}: {e}"})

        task = asyncio.create_task(work())

        async def events():
            try:
                while True:
                    ev = await queue.get()
                    yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
                    if ev["type"] in ("done", "error"):
                        break
            finally:
                await task  # finish the turn even if the page went away, so the session stays consistent

        return StreamingResponse(events(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

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
