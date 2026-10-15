"""Unit tests for the eval scoring rules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
from score import key_facts, score_record  # noqa: E402


def rec(answer, calls=(), mode="single", agents=("academic_helpdesk",), drafts=(), logged=False, error=""):
    return {"answer": answer, "tool_calls": [{"name": n, "args": a} for n, a in calls], "mode": mode,
            "agents": list(agents), "drafts": list(drafts), "logged": logged, "error": error}


ATTEND = {"behavior": "answer", "must_include": [r"75\s?%", r"de-?regist|deregist"], "must_not": [r"\bC grade"],
          "sources": ["Circular 51"], "tools": ["search_documents"], "agent": "policy_agent"}


def test_answer_correct_and_grounded():
    s = score_record(rec("Keep 75% or face de-registration.\nSource: Circular 51, pp. 1-2",
                         [("search_documents", {})]), ATTEND)
    assert s["correct"] and s["grounded"]


def test_answer_with_superseded_rule_is_wrong():
    s = score_record(rec("Below 75% you can sit but need a C grade; de-registration...", [("search_documents", {})]),
                     ATTEND)
    assert not s["correct"] and s["reason"] == "superseded/forbidden content"


def test_answer_right_but_uncited_is_not_grounded():
    s = score_record(rec("75%, else de-registration.", [("search_documents", {})]), ATTEND)
    assert s["correct"] and not s["grounded"]


def test_refusal_on_in_scope_is_false_refusal():
    s = score_record(rec("I don't know the answer to that."), ATTEND)
    assert not s["correct"] and s["refused"]


def test_clarify_rejects_numbers():
    exp = {"behavior": "clarify"}
    assert score_record(rec("Which B.Tech branch are you in, and which year did you join?"), exp)["correct"]
    assert not score_record(rec("You need 12 credits. Which branch and year?"), exp)["correct"]


def test_suggest_must_not_draft():
    exp = {"behavior": "suggest", "must_include": [r"CSL\s?7650"]}
    assert score_record(rec("Did you mean CSL7650?", [("lookup_course", {})]), exp)["correct"]
    assert not score_record(rec("Did you mean CSL7650? Drafted.", [("draft_email", {"to": "x@y.z"})]), exp)["correct"]


def test_draft_needs_right_recipient_and_file():
    exp = {"behavior": "draft", "to": "gaurav.harit@iitj.example", "tools": ["draft_email"]}
    good = rec("Saved.", [("get_instructor_email", {}), ("draft_email", {"to": "Gaurav.Harit@iitj.example"})],
               drafts=[{"file": "a.md", "text": "..."}])
    bad = rec("Saved.", [("draft_email", {"to": "someone@iitj.example"})], drafts=[{"file": "a.md", "text": ""}])
    assert score_record(good, exp)["correct"] and score_record(good, exp)["grounded"]
    assert score_record(bad, exp)["reason"] == "wrong recipient"


def test_routing_uses_first_specialist():
    s = score_record(rec("75% ... de-registration. Source: Circular 51", [("search_documents", {})], mode="multi",
                         agents=["helpdesk_orchestrator", "policy_agent"]), ATTEND)
    assert s["routed"]
    s = score_record(rec("I don't know", mode="multi", agents=["helpdesk_orchestrator"]),
                     {"behavior": "refuse", "agent": "helpdesk_orchestrator"})
    assert s["routed"] and s["correct"]


def test_key_facts_ignore_years_and_detect_refusal():
    assert key_facts("CSL7650 slot E on 22 Nov 2026") == key_facts("Slot E for CSL 7650, 22 November 2026")
    assert key_facts("I don't know the answer") == "REFUSED"
