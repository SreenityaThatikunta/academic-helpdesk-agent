"""Score the raw eval results and write summary tables.

Usage: .venv/bin/python eval/score.py [--no-overrides]
Reads  eval/questions.jsonl, eval/results/*/raw.jsonl, eval/overrides.csv (manual review)
Writes eval/results/scored.jsonl, eval/results/summary.md, eval/results/review.md
"""

import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "eval"
RESULTS = EVAL / "results"
REFUSAL = re.compile(r"I don'?t know|I do not know", re.I)
CLARIFY = (re.compile(r"branch|programme|program", re.I), re.compile(r"year|join|batch", re.I))
ROUTER = "helpdesk_orchestrator"
CONFIG_ORDER = ["single · qwen3:8b", "multi · qwen3:8b", "single · llama3.1:8b", "multi · llama3.1:8b"]


def load_questions() -> dict:
    qs = {}
    for line in (EVAL / "questions.jsonl").read_text().splitlines():
        it = json.loads(line)
        for i, exp in enumerate(it["expect"]):
            qs[(it["id"], i)] = {**exp, "category": it["category"], "question": it["turns"][i]}
    return qs


def load_overrides() -> dict:
    path = EVAL / "overrides.csv"
    if not path.exists():
        return {}
    out = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            out[(row["run"], row["id"], int(row["turn"]), row["field"])] = (row["value"].lower() == "true",
                                                                           row["reason"])
    return out


def _matches_all(patterns, text) -> bool:
    return all(re.search(p, text, re.I) for p in patterns or [])


def _matches_any(patterns, text) -> bool:
    return any(re.search(p, text, re.I) for p in patterns or [])


def key_facts(answer: str) -> str:
    """Normalised facts used to detect answers that changed across repeats."""
    if REFUSAL.search(answer):
        return "REFUSED"
    code_re = re.compile(r"\b[A-Z]{2,4}\s?\d{4}\b")
    codes = sorted({c.replace(" ", "") for c in code_re.findall(answer)})
    rest = code_re.sub(" ", answer)  # so "CSL 7650" doesn't also count as the number 7650
    nums = sorted({n.replace(" ", "") for n in re.findall(r"\b\d+(?:\.\d+)?(?:\s?%)?", rest)}
                  - {"2026", "2027", "2024", "2019", "2025"})
    return f"codes={','.join(codes)} nums={','.join(nums)}"


def score_record(r: dict, exp: dict) -> dict:
    ans = r["answer"] or ""
    calls = [c["name"] for c in r["tool_calls"]]
    refused = bool(REFUSAL.search(ans))
    beh = exp["behavior"]
    reason = ""

    if r["error"]:
        correct, reason = False, f"error: {r['error'][:80]}"
    elif beh == "refuse":
        correct = refused
        reason = "" if correct else "did not refuse"
    elif beh == "clarify":
        asks = all(p.search(ans) for p in CLARIFY)
        gave_number = bool(re.search(r"\b1[02]\s*(OE\s*)?credits?", ans, re.I))
        correct = asks and not gave_number and not refused
        reason = "" if correct else ("gave a credit number" if gave_number else "did not ask for branch/year")
    elif beh == "suggest":
        correct = _matches_all(exp.get("must_include"), ans) and "draft_email" not in calls
        reason = "" if correct else ("drafted without confirmation" if "draft_email" in calls else "no CSL7650 suggestion")
    elif beh == "draft":
        draft_calls = [c for c in r["tool_calls"] if c["name"] == "draft_email"]
        to_ok = any(str(c["args"].get("to", "")).strip().lower() == exp["to"] for c in draft_calls)
        content_ok = _matches_all(exp.get("must_include"), ans + " ".join(d["text"] for d in r["drafts"]))
        stale = _matches_any(exp.get("must_not"), ans)
        correct = to_ok and bool(r["drafts"]) and content_ok and not stale
        reason = "" if correct else ("no draft" if not draft_calls else "wrong recipient" if not to_ok
                                     else "missing rule facts" if not content_ok else "superseded rule")
    else:  # answer
        inc = _matches_all(exp.get("must_include"), ans)
        stale = _matches_any(exp.get("must_not"), ans)
        correct = inc and not stale and not refused
        reason = "" if correct else ("refused" if refused else "superseded/forbidden content" if stale
                                     else "missing expected facts")

    grounded = None
    if beh in ("answer", "draft"):
        tool_ok = any(t in calls for t in exp.get("tools", [])) if exp.get("tools") else True
        srcs = exp.get("sources") or []
        cite_ok = (not srcs) or any(s.lower() in ans.lower() for s in srcs)
        if beh == "draft" and not srcs:
            cite_ok = "get_instructor_email" in calls  # recipient came from the lookup, not invented
        grounded = bool(correct and tool_ok and cite_ok)

    routed = None
    if r["mode"] == "multi":
        first = next((a for a in r["agents"] if a != ROUTER), ROUTER)
        want = exp.get("agent")
        routed = first in want if isinstance(want, list) else first == want

    return {"correct": correct, "reason": reason, "grounded": grounded, "refused": refused, "routed": routed,
            "first_agent": next((a for a in r["agents"] if a != ROUTER), ROUTER), "facts": key_facts(ans)}


def pct(n, d):
    return f"{100 * n / d:.0f}% ({n}/{d})" if d else "–"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-overrides", action="store_true")
    args = ap.parse_args()
    qs = load_questions()
    overrides = {} if args.no_overrides else load_overrides()

    rows = []
    for raw in sorted(RESULTS.glob("*/raw.jsonl")):
        for line in raw.read_text().splitlines():
            r = json.loads(line)
            exp = qs[(r["id"], r["turn"])]
            s = score_record(r, exp)
            for field in ("correct", "grounded"):
                key = (r["run"], r["id"], r["turn"], field)
                if key in overrides:
                    s[field], why = overrides[key]
                    s["override"] = (s.get("override", "") + f" {field}->{s[field]}: {why}").strip()
            model = r["model"].split("/")[-1]
            rows.append({**r, **s, "config": f"{r['mode']} · {model}", "behavior": exp["behavior"],
                         "category": exp["category"], "expected": exp["answer"]})
    (RESULTS / "scored.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n")

    by_cfg = defaultdict(list)
    for x in rows:
        by_cfg[x["config"]].append(x)
    configs = [c for c in CONFIG_ORDER if c in by_cfg] + sorted(set(by_cfg) - set(CONFIG_ORDER))

    md = ["# Evaluation summary", "",
          f"Runs: {len({x['run'] for x in rows})} · turns scored: {len(rows)} · "
          f"manual overrides applied: {sum(1 for x in rows if x.get('override'))}", ""]

    # ---- headline metrics
    md += ["## Headline metrics (all repeats pooled)", "",
           "| Config | Accuracy | Groundedness (answer/draft turns) | Correct refusals | False refusals | "
           "Refusals logged | Routing | Mean latency | p90 latency | Errors |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for c in configs:
        xs = by_cfg[c]
        acc = sum(x["correct"] for x in xs)
        g = [x for x in xs if x["grounded"] is not None]
        ref = [x for x in xs if x["behavior"] == "refuse"]
        nonref = [x for x in xs if x["behavior"] != "refuse"]
        logged = [x for x in ref if x["refused"]]
        rt = [x for x in xs if x["routed"] is not None]
        lat = sorted(x["seconds"] for x in xs)
        md.append(f"| {c} | {pct(acc, len(xs))} | {pct(sum(x['grounded'] for x in g), len(g))} | "
                  f"{pct(sum(x['refused'] for x in ref), len(ref))} | "
                  f"{pct(sum(x['refused'] for x in nonref), len(nonref))} | "
                  f"{pct(sum(x['logged'] for x in logged), len(logged))} | "
                  f"{pct(sum(x['routed'] for x in rt), len(rt)) if rt else '–'} | "
                  f"{statistics.mean(lat):.1f}s | {lat[int(0.9 * (len(lat) - 1))]:.1f}s | "
                  f"{sum(1 for x in xs if x['error'])} |")

    # ---- accuracy by category
    cats = ["policy", "schedule", "count", "email", "out_of_scope", "multi_intent", "conversation"]
    md += ["", "## Accuracy by category", "", "| Config | " + " | ".join(cats) + " |",
           "|---|" + "---|" * len(cats)]
    for c in configs:
        cells = []
        for cat in cats:
            xs = [x for x in by_cfg[c] if x["category"] == cat]
            cells.append(pct(sum(x["correct"] for x in xs), len(xs)))
        md.append(f"| {c} | " + " | ".join(cells) + " |")

    # ---- per question
    keys = sorted({(x["id"], x["turn"]) for x in rows})
    md += ["", "## Per question (correct runs out of repeats)", "",
           "| Item | Expected | " + " | ".join(configs) + " |", "|---|---|" + "---|" * len(configs)]
    for k in keys:
        exp = qs[k]["answer"][:70]
        cells = []
        for c in configs:
            xs = [x for x in by_cfg[c] if (x["id"], x["turn"]) == k]
            cells.append(f"{sum(x['correct'] for x in xs)}/{len(xs)}")
        md.append(f"| {k[0]}{'.' + str(k[1] + 1) if k[0] == 'V01' else ''} | {exp} | " + " | ".join(cells) + " |")

    # ---- consistency
    md += ["", "## Consistency across repeats", "",
           "A question is **unstable** when its correctness differs between repeats; its **facts changed** when "
           "the numbers / course codes in the answer differ between repeats (or it refused in some repeats only).",
           "", "| Config | Unstable correctness | Facts changed |", "|---|---|---|"]
    changed_rows = []
    for c in configs:
        unstable = factchg = 0
        for k in keys:
            xs = [x for x in by_cfg[c] if (x["id"], x["turn"]) == k]
            if len(xs) < 2:
                continue
            u = len({x["correct"] for x in xs}) > 1
            f = len({x["facts"] for x in xs}) > 1
            unstable += u
            factchg += f
            if u or f:
                changed_rows.append((c, k, [x["correct"] for x in sorted(xs, key=lambda x: x["repeat"])],
                                     [x["facts"] for x in sorted(xs, key=lambda x: x["repeat"])]))
        md.append(f"| {c} | {unstable}/{len(keys)} | {factchg}/{len(keys)} |")
    md += ["", "### Questions whose answers changed across runs", "",
           "| Config | Item | Correct per repeat | Key facts per repeat |", "|---|---|---|---|"]
    for c, k, cor, facts in changed_rows:
        md.append(f"| {c} | {k[0]}.{k[1] + 1} | {' '.join('✓' if v else '✗' for v in cor)} | "
                  f"{' ‖ '.join(facts)} |")

    (RESULTS / "summary.md").write_text("\n".join(md) + "\n")

    # ---- review sheet: every turn scored wrong (or not grounded), for manual checking
    rv = ["# Turns to review", "", "Each entry was scored wrong or not grounded. Add a row to eval/overrides.csv "
          "(run,id,turn,field,value,reason) if the automatic label is wrong.", ""]
    for x in rows:
        if x["correct"] and x["grounded"] in (True, None):
            continue
        calls = ", ".join(c["name"] for c in x["tool_calls"])
        rv += [f"## {x['run']} · {x['id']}.{x['turn']} · {x['behavior']} · correct={x['correct']} "
               f"grounded={x['grounded']} {('· ' + x['reason']) if x['reason'] else ''}",
               f"**Q:** {x['question']}  ", f"**Expected:** {x['expected']}  ",
               f"**Route:** {' > '.join(x['agents'])} · **tools:** {calls or '-'}  ",
               f"**Override:** {x.get('override', '-')}", "", "```", (x["answer"] or "")[:1500], "```", ""]
    (RESULTS / "review.md").write_text("\n".join(rv) + "\n")
    print((RESULTS / "summary.md").read_text())


if __name__ == "__main__":
    main()
