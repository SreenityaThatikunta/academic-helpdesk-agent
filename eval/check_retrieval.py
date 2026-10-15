"""Phase 2 retrieval check: does the right document come back, and where
should the "not found" distance threshold sit?

Usage: .venv/bin/python eval/check_retrieval.py [k]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helpdesk.rag import search  # noqa: E402

# (question, acceptable source doc_ids)
IN_SCOPE = [
    ("What is the attendance requirement to sit in the Major exam?", {"D02"}),
    ("What happens if my attendance falls below 75%?", {"D02"}),
    ("How many Open Elective credits do I need to earn to get a B.Tech degree?", {"D01", "D21", "D09"}),
    ("How many Humanities (IH) credits are required for B.Tech?", {"D01", "D21", "D09"}),
    ("I missed my minor exam due to illness. Can I get a makeup exam?", {"D31", "D01", "D21", "D03"}),
    ("What is the deadline to apply for a makeup examination?", {"D31"}),
    ("What is an I grade and when is it given?", {"D31", "D01", "D21"}),
    ("When are the major examinations for semester I 2026-27?", {"D17", "D30"}),
    ("When is the last date for course withdrawal this semester?", {"D17"}),
    ("What topics are covered in the Autonomous Systems course?", {"D13", "D12"}),
    ("What is the syllabus of Health Economics LAL4070?", {"D29"}),
    ("How is the CGPA calculated?", {"D01", "D21", "D04"}),
    ("What is the minimum CGPA to avoid academic probation?", {"D01", "D21", "D04"}),
    ("What are the rules for grading and letter grades?", {"D01", "D21", "D04"}),
    ("What is the maximum duration allowed to complete a PhD?", {"D05"}),  # PG Regulations §11.5
    ("What is the maximum duration of the B.Tech programme?", {"D01", "D21"}),  # 14 semesters (2019) supersedes 8 years (D04)
    ("What are the IH2 humanities electives offered this semester?", {"D28", "D23", "D25"}),
    ("How many Programme Elective (PE) credits are needed for B.Tech?", {"D01", "D21", "D09"}),
    ("What happens if I am absent for four weeks in a semester?", {"D02"}),
]

OUT_OF_SCOPE = [
    "What are the available dining options on the campus?",
    "What is the best way to reach the campus from Jodhpur city center?",
    "What is the weather in Jodhpur today?",
    "Who won the cricket world cup in 2023?",
    "How do I apply for a hostel room change?",
    "What is the wifi password for the library?",
    "Recommend a good restaurant near IIT Jodhpur.",
    "What is the placement package of CSE students?",
]


def main(k: int = 5) -> None:
    hit1 = hitk = 0
    top_in = []
    print(f"{'rank':>4} {'dist':>6}  question  ->  top docs")
    for q, expected in IN_SCOPE:
        out = search(q, k=k, max_distance=2.0)
        res = out["results"]
        docs = [r["doc_id"] for r in res]
        rank = next((i + 1 for i, d in enumerate(docs) if d in expected), None)
        hit1 += rank == 1
        hitk += rank is not None
        top_in.append(out["best_distance"])
        flag = "OK " if rank == 1 else (f"@{rank} " if rank else "MISS")
        print(f"{flag:>4} {out['best_distance']:.3f}  {q[:60]:60}  {docs}")

    print("\nout of scope:")
    top_out = []
    for q in OUT_OF_SCOPE:
        out = search(q, k=1, max_distance=2.0)
        res = out["results"]
        top_out.append(out["best_distance"])
        print(f"     {out['best_distance']:.3f}  {q[:60]:60}  {res[0]['doc_id']} {res[0]['title'][:40]}")

    n = len(IN_SCOPE)
    print(f"\nhit@1 {hit1}/{n}   hit@{k} {hitk}/{n}")
    print(f"in-scope top-1 distance:     min {min(top_in):.3f}  max {max(top_in):.3f}")
    print(f"out-of-scope top-1 distance: min {min(top_out):.3f}  max {max(top_out):.3f}")
    for t in (0.35, 0.38, 0.40, 0.42, 0.45, 0.50):
        kept = sum(d <= t for d in top_in)
        rejected = sum(d > t for d in top_out)
        print(f"  threshold {t:.2f}: in-scope kept {kept}/{n}, out-of-scope rejected {rejected}/{len(top_out)}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
