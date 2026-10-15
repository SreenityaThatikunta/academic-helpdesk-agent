"""Unit tests for the agent tools (CSV-backed tools need no Ollama; search_documents is excluded)."""

import json

import pytest

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


def test_ih_groups_tagged_from_syllabi():
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
