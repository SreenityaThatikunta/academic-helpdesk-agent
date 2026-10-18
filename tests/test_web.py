"""Unit tests for the web UI server: citations, trace summaries, answer cards and the JSON API.

Turns are built by hand from real tool outputs (CSV-backed tools), so no Ollama is needed; the
API tests never reach the agent (it is built on the first chat message).
"""

import pytest
from fastapi.testclient import TestClient

from helpdesk import config
from helpdesk.runner import Turn
from helpdesk.tools import get_slot, list_courses, log_unanswered_question, lookup_course
from helpdesk.web import server

REFUSAL = "I don't know the answer to that. I've forwarded your question to the academic office."


@pytest.fixture
def tmp_log(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "UNANSWERED_LOG", tmp_path / "logs" / "unanswered.jsonl")
    return tmp_path


def make_turn(answer="", calls=(), results=(), question="q"):
    """results: (tool name, response) pairs; calls: (tool name, args) pairs."""
    return Turn(question=question, answer=answer,
                tool_calls=[{"agent": "a", "name": n, "args": a} for n, a in calls],
                tool_results=[{"agent": "a", "name": n, "response": r} for n, r in results])


def search_result(*citations):
    return {"found": True, "results": [{"citation": c, "text": f"passage from {c}"} for c in citations]}


def kinds(cards):
    return [c["kind"] for c in cards]


# --- citations -> documents ---------------------------------------------------------------

@pytest.mark.parametrize("citation,doc", [
    ("Circular 51: Amendment in the Attendance Policy, pp. 1-2", "D02"),
    # both titles start with "Academic Regulations": the longest matching title wins
    ("Academic Regulations (web page), p. 1", "D21"),
    ("Academic Regulations (students enrolled from July 2019), p. 31", "D01"),
    ("Not a document we have, p. 3", None),
])
def test_doc_for_title(citation, doc):
    assert server._doc_for_title(citation) == doc


@pytest.mark.parametrize("source,doc", [
    ("26_Slot_System_AY2026-27_SemI.xlsx (Classroom Allocation)", "D26"),
    ("30_Major_Exam_Timetable_AY2026-27_SemI.xlsx", "D30"),
    ("faculty.csv (dummy emails)", None),
])
def test_doc_for_file(source, doc):
    assert server._doc_for_file(source) == doc


def test_sources_cited_first_with_page():
    turn = make_turn(
        answer="Attendance must be 75%.\n\nSource: Circular 51: Amendment in the Attendance Policy, pp. 1-2",
        results=[("search_documents", search_result("PG Regulations (enrolled July 2022 onwards), p. 9",
                                                    "Circular 51: Amendment in the Attendance Policy, pp. 1-2"))])
    sources = server.extract_sources(turn)
    assert [s["doc_id"] for s in sources] == ["D02", "D05"]
    assert sources[0]["cited"] and not sources[1]["cited"]
    assert sources[0]["page"] == 1 and sources[1]["page"] == 9
    assert sources[0]["snippets"] == ["passage from Circular 51: Amendment in the Attendance Policy, pp. 1-2"]


def test_sources_cited_by_file_name():
    # answers built on the time table cite the spreadsheet's file name, not its title
    slot = get_slot("CSL7650")
    turn = make_turn(answer="Slot E.\n\nSource: 26_Slot_System_AY2026-27_SemI.xlsx", results=[("get_slot", slot)])
    sources = {s["doc_id"]: s for s in server.extract_sources(turn)}
    assert sources["D26"]["cited"]
    assert not sources["D30"]["cited"]


# --- live trace -----------------------------------------------------------------------------

def test_trace_call():
    assert server.trace_call("transfer_to_agent", {"agent_name": "schedule_agent"}) == {"step": "handoff",
                                                                                        "to": "schedule_agent"}
    step = server.trace_call("search_documents", {"query": "open elective credits", "document": "CSE Curriculum",
                                                  "top_k": 5})
    assert step == {"step": "call", "arg": "open elective credits", "extra": {"document": "CSE Curriculum"}}


def test_trace_result_search():
    one = server.trace_result("search_documents", search_result("Circular 51: Amendment in the Attendance Policy, p. 1"))
    assert one == {"ok": True, "summary": "1 passage from D02", "docs": ["D02"]}
    none = server.trace_result("search_documents", {"found": False, "results": []})
    assert not none["ok"] and none["docs"] == []


def test_trace_result_tools():
    found = server.trace_result("get_slot", get_slot("Autonomous Systems"))
    assert found["ok"] and found["summary"] == "CSL7650 Autonomous Systems · slot E"
    assert {"D26", "D30"} <= set(found["docs"])
    missing = server.trace_result("get_slot", get_slot("CSL7570"))
    assert not missing["ok"] and "did you mean CSL7650" in missing["summary"]
    assert server.trace_result("draft_email", {"status": "draft_saved"})["summary"] == "draft saved, not sent"
    assert "abc123" in server.trace_result("log_unanswered_question", {"ticket_id": "abc123"})["summary"]
    assert server.trace_result("transfer_to_agent", None) == {}


# --- answer cards ---------------------------------------------------------------------------

def test_course_card_prefers_get_slot_record():
    turn = make_turn(results=[("lookup_course", lookup_course("CSL7650")), ("get_slot", get_slot("CSL7650"))])
    cards = server.extract_cards(turn)
    assert kinds(cards) == ["course"]
    assert cards[0]["course_code"] == "CSL7650"
    assert cards[0]["weekly_schedule"] and {e["exam"] for e in cards[0]["exams"]} == {"Minor", "Major"}


def test_email_card_from_draft_call():
    args = {"to": "gaurav.harit@iitj.example", "subject": "Leave request", "body": "Dear Prof. Harit, ..."}
    turn = make_turn(calls=[("draft_email", args)],
                     results=[("draft_email", {"status": "draft_saved", "path": "drafts/x.md"})])
    [card] = server.extract_cards(turn)
    assert card == {"kind": "email", "cc": "", "path": "drafts/x.md", **args}


def test_no_email_card_when_draft_failed():
    turn = make_turn(calls=[("draft_email", {"to": "bad"})],
                     results=[("draft_email", {"status": "error", "message": "Invalid email address(es): bad"})])
    assert server.extract_cards(turn) == []


def test_courses_card():
    result = list_courses("Humanities", "400")
    [card] = server.extract_cards(make_turn(results=[("list_courses", result)]))
    assert card["kind"] == "courses" and card["count"] == result["count"] == len(card["courses"])


def test_ticket_card_finds_auto_logged_question(tmp_log):
    # the guard logs a refusal itself when the model skipped the tool, so the turn has no tool result
    entry = log_unanswered_question("Where is the canteen?", "auto-logged by test")
    turn = make_turn(answer=REFUSAL, question="Where is the canteen?")
    [card] = server.extract_cards(turn)
    assert card == {"kind": "ticket", "ticket_id": entry["ticket_id"], "reason": "auto-logged by test"}


def test_ticket_card_from_tool_result(tmp_log):
    turn = make_turn(answer=REFUSAL, results=[("log_unanswered_question", {"status": "logged", "ticket_id": "t1"})])
    assert server.extract_cards(turn)[0]["ticket_id"] == "t1"


def test_clarify_card():
    turn = make_turn(answer="Which B.Tech programme (branch) are you in, and which year did you join?")
    [card] = server.extract_cards(turn)
    assert card["kind"] == "clarify"
    assert {"CSE", "AIDE", "EE"} <= set(card["branches"]) and 2026 in card["years"]


def test_suggest_card_only_when_asking():
    missing = get_slot("CSL7570")
    asking = make_turn(answer="CSL7570 is not offered. Did you mean CSL7650?", results=[("get_slot", missing)])
    [card] = server.extract_cards(asking)
    assert card["kind"] == "suggest" and card["options"][0] == {"code": "CSL7650", "name": "Autonomous Systems"}
    # the agent recovered on its own (e.g. looked up the right course): no chips
    recovered = make_turn(answer="Did you mean CSL7650? Its slot is E.",
                          results=[("get_slot", missing), ("get_slot", get_slot("CSL7650"))])
    assert kinds(server.extract_cards(recovered)) == ["course"]


# --- rule history -----------------------------------------------------------------------------

def test_rule_history_data():
    history = server.rule_history()
    makeup = next(h for h in history if h["kind"] == "amended" and h["new"] == ["D31"])
    assert set(makeup["old"]) == {"D01", "D21", "D05"}
    btech = next(h for h in history if h["kind"] == "superseded" and h["old"] == ["D04"])
    assert btech["new"] == ["D01", "D21"]
    docs = server.manifest()
    assert all(d in docs for h in history for d in h["old"] + h["new"])


def test_history_card_when_newer_rule_cited():
    cited = "New Guidelines for Institute Examination (2024), p. 8"
    turn = make_turn(answer=f"Yes.\n\nSource: {cited}", results=[("search_documents", search_result(cited))])
    [card] = server.extract_cards(turn)
    assert card["kind"] == "history"
    [step] = card["steps"]
    assert step["new"][0]["id"] == "D31" and {d["id"] for d in step["old"]} == {"D01", "D21", "D05"}


def test_history_card_when_superseded_document_cited():
    cited = "B.Tech Regulations (July 2014+ batches), p. 4"
    turn = make_turn(answer=f"8 years.\n\nSource: {cited}", results=[("search_documents", search_result(cited))])
    [step] = server.extract_cards(turn)[0]["steps"]
    assert step["kind"] == "superseded" and [d["id"] for d in step["new"]] == ["D01", "D21"]


def test_no_history_card_for_retrieved_only():
    retrieved = "New Guidelines for Institute Examination (2024), p. 8"
    turn = make_turn(answer="Something else entirely.", results=[("search_documents", search_result(retrieved))])
    assert server.extract_cards(turn) == []


# --- API ----------------------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(server.create_app("single", config.MODEL))


def test_api_info(client):
    info = client.get("/api/info").json()
    assert info["mode"] == "single" and set(info["modes"]) == {"single", "multi"}


def test_api_graph(client):
    graph = client.get("/api/graph").json()
    ids = {n["id"] for n in graph["nodes"]}
    docs = [n for n in graph["nodes"] if n["type"] == "doc"]
    assert len(docs) == len(server.manifest())
    assert all(n["ext"] in {"pdf", "xlsx", "html", "txt"} for n in docs)
    assert all(link["source"] in ids and link["target"] in ids for link in graph["links"])
    assert {"source": "D01", "target": "D02", "kind": "amends"} in graph["links"]


def test_api_doc(client):
    r = client.get("/api/doc/D02")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert client.get("/api/doc/D99").status_code == 404


def test_api_unanswered_newest_first(client, tmp_log):
    first = log_unanswered_question("first?", "test")["ticket_id"]
    second = log_unanswered_question("second?", "test")["ticket_id"]
    assert [e["id"] for e in client.get("/api/unanswered").json()] == [second, first]


def test_api_chat_rejects_empty_message(client):
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400
    assert client.post("/api/chat/stream", json={"message": ""}).status_code == 400


def test_static_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "<title>Academic Helpdesk</title>" in r.text
