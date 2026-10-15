"""Writes eval/questions.jsonl, the evaluation set (30 items).

Fields:
  id, category, turns (list of user messages; >1 = one conversation in one session)
  per turn in `expect` (one dict per turn):
    behavior        answer | clarify | refuse | suggest | draft
    answer          human-readable expected answer (for the report)
    must_include    list of regex groups; every group must match the answer (case-insensitive)
    must_not        regexes that must NOT match (e.g. a superseded rule)
    sources         a correct citation must contain one of these strings (groundedness)
    tools           a relevant tool that must have been called (any of these)
    agent           expected specialist in multi mode (helpdesk_orchestrator = handled by the router);
                    a list when either specialist is a reasonable route
    to              expected draft recipient (draft behavior)
Every expected answer was verified against the tools / documents (see PROGRESS_LOG Phase 6).
"""

import json
from pathlib import Path

REGS = ["Academic Regulations"]
CIRC51 = ["Circular 51"]
EXAM_GUIDE = ["New Guidelines for Institute Examination"]
ALLOC = ["Slot System", "Classroom Allocation", "26_Slot_System"]
MAJOR_TT = ["Major Exam", "Major_Exam", "Major Examinations"]
REFUSE = {"behavior": "refuse", "answer": "I don't know + logged", "agent": "helpdesk_orchestrator"}


def ans(answer, must_include, sources, tools, agent, must_not=()):
    return {"behavior": "answer", "answer": answer, "must_include": must_include, "must_not": list(must_not),
            "sources": sources, "tools": tools, "agent": agent}


ITEMS = [
    # ---------------- policy ----------------
    ("P01", "policy", ["What is the attendance requirement to sit in the Major exam?"],
     [ans("At least 75% attendance in each course (full attendance expected); below 75% without valid reason the "
          "instructor can recommend de-registration (Circular 51, 2024, supersedes the old rule).",
          [r"75\s?%", r"de-?regist|deregist"], CIRC51, ["search_documents"], "policy_agent",
          must_not=[r"\bC grade", r"allowed to appear"])]),
    ("P02", "policy", ["What happens if I am absent from all classes for four weeks in a semester?"],
     [ans("Absence from all academic activities for 4+ weeks (with or without leave) results in automatic semester "
          "withdrawal / cancellation of registration.",
          [r"withdraw|cancel"], CIRC51 + ["PG Regulations", "Academic Regulations"], ["search_documents"],
          "policy_agent")]),
    ("P03", "policy", ["I missed a minor exam because I was sick. How do I apply for a make-up exam?"],
     [ans("Make-up is for a missed Minor; submit the Makeup/I-grade application (Annexure A) with a medical "
          "certificate issued/verified by the IITJ Medical Officer to the Office of Academic Affairs within 10 days.",
          [r"10 days|ten days", r"medical"], EXAM_GUIDE, ["search_documents"], "policy_agent",
          must_not=[r"supplementary week"])]),
    ("P04", "policy", ["What should I do if I miss the Major exam due to illness?"],
     [ans("Apply for an I grade (not a make-up); the I grade application must reach the Office of Academic Affairs "
          "before the last day of the examinations, with a verified medical certificate.",
          [r"\bI['\"\u201c\u201d]?[ -]?grade"], EXAM_GUIDE, ["search_documents"], "policy_agent")]),
    ("P05", "policy", ["What is the maximum duration allowed to complete a B.Tech programme?"],
     [ans("14 registered semesters (2019 Academic Regulations §11.4; supersedes the older 8-year rule).",
          [r"\b14\b"], REGS, ["search_documents"], "policy_agent", must_not=[r"\b8 years"])]),
    ("P06", "policy", ["How many examinations are held for a course in a semester?"],
     [ans("One Minor and one Major examination (Circular 52, Jul 2024; Examination Guidelines 2024).",
          [r"\bminor\b", r"\bmajor\b"], ["Circular 52"] + EXAM_GUIDE, ["search_documents"], "policy_agent",
          must_not=[r"two minor|three (exam|minor)"])]),
    ("P07", "policy", ["When are the minor examinations for Semester I of 2026-27?"],
     [ans("15-20 September 2026 (tentative).", [r"15", r"20", r"sep"],
          ["Academic Calendar AY 2026-27"] + ALLOC, ["search_documents", "get_slot"],
          ["policy_agent", "schedule_agent"])]),
    ("P08", "policy", ["What topics are covered in the Autonomous Systems course?"],
     [ans("Autonomous/semi-autonomous systems (mobile robots, cars): e.g. navigation, obstacle avoidance, planning, "
          "multi-agent systems, game theory.",
          [r"multi-?agent|navigation|obstacle|planning|robot"], ["Details of Courses Offered by Dept. of CSE",
                                                                 "M.Tech AI Curriculum"],
          ["search_documents"], "policy_agent")]),
    # Answer key corrected after the first full run: PG Regulations §11.5 (p. 22) does state it
    # (Phase 2 had wrongly concluded it was not in any document - see PROGRESS_LOG Phase 6)
    ("P09", "policy", ["What is the maximum duration allowed to complete a PhD?"],
     [ans("14 registered semesters, which may include up to 6 semesters of Registration kept Alive (RKA) "
          "(PG Regulations 2022 onwards, §11.5).", [r"\b14\b"], ["PG Regulations"], ["search_documents"],
          "policy_agent")]),
    # ---------------- schedule ----------------
    ("S01", "schedule", ["What is the slot for the course Autonomous Systems?"],
     [ans("CSL7650, slot E (Tue/Thu/Fri 11:00-11:50), LHC 106.", [r"\bE\b"], ALLOC, ["get_slot", "lookup_course"],
          "schedule_agent")]),
    ("S02", "schedule", ["Who teaches Health Economics this semester, and in which classroom?"],
     [ans("LAL4070, Alok Ranjan, LHC 204 (slot D).", [r"Alok", r"LHC\s?204"], ALLOC, ["get_slot", "lookup_course"],
          "schedule_agent")]),
    ("S03", "schedule", ["When is the major exam for CSL7650?"],
     [ans("22 November 2026 (Sunday), 09:00 AM-12:00 PM, tentative.", [r"22", r"nov"], MAJOR_TT + ALLOC,
          ["get_slot"], "schedule_agent")]),
    ("S04", "schedule", ["In which slot and classroom is the course Digital Society held?"],
     [ans("LAL3080, slot N, LHC 105 (Rachel Philip).", [r"\bN\b", r"LHC\s?105"], ALLOC,
          ["get_slot", "lookup_course"], "schedule_agent")]),
    ("S05", "schedule", ["What is the slot for CSL9999?"],
     [ans("No such course is offered this semester (no suggestions).",
          [r"not (offered|found|available)|isn't offered|no course|don't know|does not exist"], [],
          ["get_slot", "lookup_course"], "schedule_agent")]),
    # ---------------- count ----------------
    ("C01", "count", ["How many 400 level electives have been floated by the Humanities department in this semester?"],
     [ans("3: LAL4070 Health Economics, LAL4850 Introduction to Climate Change Economics, AIL4070 Fundamentals of "
          "Economics (IH3).", [r"\b3\b|three"], ALLOC + ["IH Course List"], ["list_courses"], "schedule_agent")]),
    ("C02", "count", ["How many IH2 courses are offered to 5th semester students this semester?"],
     [ans("6: LAL3030, LAL3060, LAL3080, LAL3090, LAL3040, LAL3130.", [r"\b6\b|six"],
          ["IH Course List", "IH2"] + ALLOC, ["search_documents", "list_courses"],
          ["schedule_agent", "policy_agent"])]),
    ("C03", "count", ["How many 700-level courses is the CSE department offering this semester?"],
     [ans("16.", [r"\b16\b|sixteen"], ALLOC, ["list_courses"], "schedule_agent")]),
    # ---------------- email ----------------
    ("E01", "email", ["Write an email to the course instructor of CSL7570 that I need leave for 2 days"],
     [{"behavior": "suggest", "answer": "CSL7570 is not offered; 'Did you mean CSL7650 (Autonomous Systems)?' - no draft",
       "must_include": [r"CSL\s?7650"], "agent": "email_agent", "tools": ["get_instructor_email", "lookup_course"]}]),
    ("E02", "email", ["Write an email to the instructor of Autonomous Systems saying I need sick leave for 3 days."],
     [{"behavior": "draft", "answer": "Draft to gaurav.harit@iitj.example (sick leave, 3 days), saved, not sent",
       "to": "gaurav.harit@iitj.example", "agent": "email_agent", "tools": ["draft_email"]}]),
    ("E03", "email", ["Draft an email to the Health Economics instructor asking permission for a make-up exam, "
                      "as I missed the minor exam due to fever."],
     [{"behavior": "draft", "answer": "Draft to alok.ranjan@iitj.example (make-up for missed minor), saved, not sent",
       "to": "alok.ranjan@iitj.example", "agent": "email_agent", "tools": ["draft_email"]}]),
    ("E04", "email", ["Write an email to Prof. Rachel Philip saying I will miss tomorrow's Digital Society class "
                      "due to a family emergency."],
     [{"behavior": "draft", "answer": "Draft to rachel.philip@iitj.example, saved, not sent",
       "to": "rachel.philip@iitj.example", "agent": "email_agent", "tools": ["draft_email"]}]),
    # ---------------- out of scope ----------------
    ("O01", "out_of_scope", ["What are the available dining options on the campus?"], [REFUSE]),
    ("O02", "out_of_scope", ["What is the best way to reach the campus from Jodhpur city center?"], [REFUSE]),
    ("O03", "out_of_scope", ["What will the weather be like in Jodhpur tomorrow?"], [REFUSE]),
    ("O04", "out_of_scope", ["How do I apply for a hostel room change?"], [REFUSE]),
    ("O05", "out_of_scope", ["Who won the cricket World Cup in 2023?"], [REFUSE]),
    ("O06", "out_of_scope", ["What is the average placement package for CSE students?"], [REFUSE]),
    # ---------------- multi-intent ----------------
    ("M01", "multi_intent", ["I missed my minor exam of CSL7650 because I was ill. What is the rule for a make-up "
                             "exam? Also write an email to the instructor asking for a make-up exam."],
     [{"behavior": "draft", "answer": "Rule: make-up for missed Minor, apply within 10 days with verified medical "
                                      "certificate (2024 Guidelines) + draft to gaurav.harit@iitj.example",
       "to": "gaurav.harit@iitj.example", "must_include": [r"10 days|ten days"], "must_not": [r"supplementary week"],
       "sources": EXAM_GUIDE, "agent": "email_agent", "tools": ["draft_email"]}]),
    ("M02", "multi_intent", ["When is the major exam for Autonomous Systems, and what is the attendance requirement "
                             "to sit in it?"],
     [ans("22 November 2026, 09:00-12:00 (tentative); attendance >= 75%, else de-registration may be recommended "
          "(Circular 51).", [r"22", r"nov", r"75\s?%"], CIRC51, ["get_slot"], "schedule_agent",
          must_not=[r"\bC grade", r"allowed to appear"])]),
    # ---------------- conversation ----------------
    ("V01", "conversation", ["How many Open Elective credits do I need to earn in order to get a B.Tech. Degree?",
                             "I am in B.Tech CSE, joined in 2023."],
     [{"behavior": "clarify", "answer": "Asks for B.Tech branch and year of joining (credits differ by "
                                        "programme/batch)", "agent": "policy_agent"},
      ans("10 OE credits (B.Tech CSE curriculum, batches before 2026, p. 10).", [r"\b10\b"], ["CSE Curriculum"],
          ["search_documents"], "policy_agent", must_not=[r"\b12\b"])]),
]


def main() -> None:
    out = Path(__file__).resolve().parent / "questions.jsonl"
    with out.open("w") as f:
        for id_, cat, turns, expect in ITEMS:
            assert len(turns) == len(expect), id_
            f.write(json.dumps({"id": id_, "category": cat, "turns": turns, "expect": expect}) + "\n")
    print(f"{len(ITEMS)} items -> {out}")


if __name__ == "__main__":
    main()
