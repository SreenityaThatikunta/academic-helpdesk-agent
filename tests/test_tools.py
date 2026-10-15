"""Unit tests for the agent tools (CSV-backed tools need no Ollama; search_documents is excluded)."""

import json
import re

import pytest
from pathlib import Path

from helpdesk import config
from helpdesk.tools import (
    ALL_TOOLS,
    draft_email,
    get_instructor_email,
    get_slot,
    list_courses,
    log_unanswered_question,
    lookup_course,
)
from helpdesk.tools._data import normalize_code


@pytest.fixture
def tmp_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DRAFTS_DIR", tmp_path / "drafts")
    monkeypatch.setattr(config, "UNANSWERED_LOG", tmp_path / "logs" / "unanswered.jsonl")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("text,code", [("csl 7650", "CSL7650"), ("CSL-7650", "CSL7650"), ("Autonomous Systems", None)])
def test_normalize_code(text, code):
    assert normalize_code(text) == code


def test_lookup_by_code_and_name_agree():
    by_code = lookup_course("CSL7650")
    by_name = lookup_course("autonomous systems")
    assert by_code["found"] and by_name["found"]
    assert by_code["courses"][0]["course_code"] == by_name["courses"][0]["course_code"] == "CSL7650"


def test_lookup_unknown_code_suggests_closest_same_prefix():
    r = lookup_course("CSL7570")
    assert not r["found"]
    codes = [s["course_code"] for s in r["suggestions"]]
    assert "CSL7650" in codes
    assert all(c.startswith("CSL") for c in codes)


def test_get_slot_autonomous_systems():
    c = get_slot("Autonomous Systems")["courses"][0]
    assert c["slots"] == ["E"]
    assert c["instructors"] == ["Gaurav Harit"]
    assert "Tue 11- 11:50" in c["weekly_schedule"]
    major = [e for e in c["exams"] if e["exam"] == "Major"]
    assert major and major[0]["date"].startswith("22 November 2026")


def test_list_humanities_400_level_includes_ih_courses_from_aide():
    r = list_courses(department="Humanities", level="400")
    assert r["count"] == 3
    assert {c["course_code"] for c in r["courses"]} == {"LAL4070", "LAL4850", "AIL4070"}
    assert r["source"]


def test_ih_groups_tagged_from_ih_list():
    r = list_courses(department="HSS")
    groups = {c["course_code"]: c["ih_group"] for c in r["courses"]}
    assert groups["LAL3080"] == "IH2" and groups["AIL7380"] == "IH3"
    # a SoLA course outside the IH bouquets is still Humanities, just untagged
    assert groups["LAL1080"] == ""


def test_list_courses_unknown_department_is_empty():
    assert list_courses(department="Underwater Basket Weaving")["count"] == 0


def test_instructor_email_by_course_is_dummy():
    r = get_instructor_email("CSL7650")
    assert r["found"]
    assert r["instructors"][0]["email"] == "gaurav.harit@iitj.example"


def test_instructor_email_by_name():
    r = get_instructor_email("gaurav harit")
    assert r["found"] and r["instructors"][0]["name"] == "Gaurav Harit"


def test_instructor_email_unknown_course_suggests():
    r = get_instructor_email("CSL7570")
    assert not r["found"]
    assert any(s["course_code"] == "CSL7650" for s in r["suggestions"])


def test_draft_email_saves_file_and_never_sends(tmp_outputs):
    r = draft_email("gaurav.harit@iitj.example", "Leave request for 2 days", "Dear Sir,\n\nPlease grant leave.\n\nRegards")
    assert r["status"] == "draft_saved" and r["sent"] is False
    saved = (tmp_outputs / r["path"]).read_text()
    assert "NOT SENT" in saved and "Subject: Leave request for 2 days" in saved


def test_draft_email_rejects_bad_address(tmp_outputs):
    assert draft_email("not-an-email", "s", "b")["status"] == "error"


def test_log_unanswered_appends_jsonl(tmp_outputs):
    a = log_unanswered_question("Where can I eat on campus?", "out of scope: dining")
    b = log_unanswered_question("What is the PhD maximum duration?", "not found in documents")
    assert a["status"] == b["status"] == "logged" and a["ticket_id"] != b["ticket_id"]
    lines = config.UNANSWERED_LOG.read_text().splitlines()
    assert [json.loads(line)["question"] for line in lines] == ["Where can I eat on campus?", "What is the PhD maximum duration?"]


def test_all_tools_build_adk_declarations():
    from google.adk.tools import FunctionTool

    for fn in ALL_TOOLS:
        decl = FunctionTool(fn)._get_declaration()
        assert decl.name == fn.__name__
        assert decl.description


def test_guard_strips_text_tool_calls_and_logs_refusal(tmp_outputs):
    from types import SimpleNamespace

    from google.adk.models import LlmResponse
    from google.genai import types

    from helpdesk.agents.guards import log_refusals

    text = ("I don't know the answer to that. I've forwarded your question to the academic office.\n"
            '{"name": "log_unanswered_question", "parameters": {"question": "Dining?", "reason": "out of scope"}}')
    resp = LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))
    ctx = SimpleNamespace(state={}, agent_name="t",
                          user_content=types.Content(role="user", parts=[types.Part(text="Dining?")]))
    log_refusals(ctx, resp)
    assert '"parameters"' not in resp.content.parts[0].text
    assert config.UNANSWERED_LOG.read_text().count("Dining?") == 1


def _index_ready() -> bool:
    try:
        import chromadb

        chromadb.PersistentClient(path=str(config.CHROMA_DIR)).get_collection(config.CHROMA_COLLECTION)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _index_ready(), reason="needs the vector index: run `python -m helpdesk.ingest` (and Ollama)")
def test_search_scoped_to_document_finds_cse_oe_credits():
    from helpdesk.tools import search_documents

    r = search_documents("Open Electives OE credits", 5, document="CSE Curriculum")
    assert r["found"]
    assert all("CSE" in x["citation"] for x in r["results"])
    assert any(re.search(r"Open Electives \(OE\)\s+10", x["text"]) for x in r["results"])


def test_router_refusal_paraphrase_is_standardized():
    from types import SimpleNamespace

    from google.adk.models import LlmResponse
    from google.genai import types

    from helpdesk.agents.guards import REFUSAL_SENTENCE, standardize_router_refusal
    from helpdesk.tools.unanswered import LOGGED_FLAG

    resp = LlmResponse(content=types.Content(role="model", parts=[
        types.Part(text="The academic office has been notified of your query.")]))
    standardize_router_refusal(SimpleNamespace(state={LOGGED_FLAG: True}), resp)
    assert resp.content.parts[0].text == REFUSAL_SENTENCE
    # no logging this turn -> a normal reply is left alone
    resp2 = LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Hello! I can help.")]))
    standardize_router_refusal(SimpleNamespace(state={}), resp2)
    assert resp2.content.parts[0].text == "Hello! I can help."


def test_empty_router_reply_falls_back_to_a_transfer():
    from types import SimpleNamespace

    from google.adk.models import LlmResponse
    from google.genai import types

    from helpdesk.agents.guards import route_empty_router_reply

    def route(q):
        ctx = SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text=q)]))
        out = route_empty_router_reply(ctx, LlmResponse(content=types.Content(role="model", parts=[])))
        return out.content.parts[0].function_call.args["agent_name"]

    assert route("Who teaches Health Economics this semester?") == "schedule_agent"
    assert route("Write an email to my instructor") == "email_agent"
    assert route("When is the semester break?") == "policy_agent"
    ok = LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Hi!")]))
    assert route_empty_router_reply(SimpleNamespace(user_content=None), ok) is None


def test_draft_email_outside_project_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DRAFTS_DIR", tmp_path / "elsewhere")
    r = draft_email("gaurav.harit@iitj.example", "Leave", "Dear Sir, ... Regards")
    assert r["status"] == "draft_saved" and Path(r["path"]).exists()


def test_refusal_source_line_is_removed(tmp_outputs):
    from types import SimpleNamespace

    from google.adk.models import LlmResponse
    from google.genai import types

    from helpdesk.agents.guards import log_refusals
    from helpdesk.tools.unanswered import LOGGED_FLAG

    text = ("I don't know the answer to that. I've forwarded your question to the academic office.\n\n"
            "Source: I don't know the answer to that. I've forwarded your question to the academic office.")
    resp = LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))
    log_refusals(SimpleNamespace(state={LOGGED_FLAG: True}, agent_name="t", user_content=None), resp)
    assert resp.content.parts[0].text == ("I don't know the answer to that. "
                                          "I've forwarded your question to the academic office.")
    # normal answers keep their source line
    ok = LlmResponse(content=types.Content(role="model", parts=[types.Part(text="Slot E.\nSource: Slot System")]))
    log_refusals(SimpleNamespace(state={}, agent_name="t", user_content=None), ok)
    assert "Source: Slot System" in ok.content.parts[0].text


def test_trim_history_stubs_old_tool_results_keeps_calls():
    from types import SimpleNamespace

    from google.genai import types

    from helpdesk.agents.guards import trim_history

    def c(role, *parts):
        return types.Content(role=role, parts=list(parts))

    call = types.Part(function_call=types.FunctionCall(name="search_documents", args={"query": "x"}))
    resp = types.Part(function_response=types.FunctionResponse(name="search_documents", response={"r": "long " * 500}))
    contents = [
        c("user", types.Part(text="How many credits?")),
        c("model", call), c("user", resp),
        c("model", types.Part(text="Which branch and year?")),
        c("user", types.Part(text="CSE, 2023")),          # current turn starts here
        c("model", call), c("user", resp),
    ]
    req = SimpleNamespace(contents=contents)
    trim_history(SimpleNamespace(user_content=types.Content(role="user", parts=[types.Part(text="CSE, 2023")])), req)
    old_resp = req.contents[2].parts[0].function_response
    assert req.contents[1].parts[0].function_call.name == "search_documents"   # old call kept
    assert "omitted" in old_resp.response["note"]                               # old result stubbed
    assert req.contents[3].parts[0].text == "Which branch and year?"            # old answer kept
    assert req.contents[6].parts[0].function_response.response["r"].startswith("long")  # current turn intact
