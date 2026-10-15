"""Generate the report's LaTeX tables from the evaluation data (no hand-copied numbers).

Usage: .venv/bin/python report/make_tables.py   (after eval/score.py)
Writes report/tables/*.tex
"""

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "report" / "tables"
CONFIGS = ["single · qwen3:8b", "multi · qwen3:8b", "single · llama3.1:8b", "multi · llama3.1:8b"]
SHORT = {c: c.replace(" · ", " / ").replace(":8b", "") for c in CONFIGS}
CATS = ["policy", "schedule", "count", "email", "out_of_scope", "multi_intent", "conversation"]


def tex(s: str) -> str:
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "§": r"\S{}",
           "≥": r"$\geq$", "→": r"$\rightarrow$", "–": "--", "—": "---", "‖": r"$\|$", "’": "'", "“": "``", "”": "''"}
    return "".join(rep.get(ch, ch) for ch in str(s))


def pct(n, d):
    return f"{100 * n / d:.0f}\\% ({n}/{d})" if d else "--"


# ----------------------------------------------------------------- figures (plain TikZ)
REASON_GROUPS = [
    ("Missing / wrong facts", {"missing expected facts", "missing rule facts"}),
    ("No draft saved", {"no draft", "wrong recipient"}),
    ("False refusal", {"refused"}),
    ("Outdated rule used", {"superseded/forbidden content"}),
    ("Did not clarify", {"gave a credit number", "did not ask for branch/year"}),
]
OUTCOMES = [  # (label, colour)
    ("correct + grounded", "good"),
    ("correct (refuse / clarify / suggest)", "good!45"),
    ("correct, not grounded", "warn"),
    ("false refusal", "bad!55"),
    ("wrong", "bad"),
]
AGENTS = ["policy_agent", "schedule_agent", "email_agent", "helpdesk_orchestrator"]
AGENT_SHORT = {"policy_agent": "policy", "schedule_agent": "schedule", "email_agent": "email",
               "helpdesk_orchestrator": "router"}


def outcome_of(x) -> int:
    if x["correct"]:
        if x["grounded"] is True:
            return 0
        if x["grounded"] is None:
            return 1
        return 2
    return 3 if (x["refused"] and x["behavior"] != "refuse") else 4


def figures(by, rows, items) -> None:
    # outcome table: how all turns of a configuration ended
    lines = []
    for c in CONFIGS:
        counts = [0] * len(OUTCOMES)
        for x in by[c]:
            counts[outcome_of(x)] += 1
        lines.append(f"{SHORT[c]} & " + " & ".join(str(n) for n in counts) + r" \\")
    (OUT / "outcomes.tex").write_text("\n".join(lines) + "\n")

    # 3. failure reasons: grouped horizontal bars (reason x config)
    bar_cols = ["accent", "accent!45", "warn", "warn!45"]
    scale = 0.38  # cm per failure
    pic = [r"\begin{tikzpicture}[font=\small]"]
    y = 0.0
    for label, reasons in REASON_GROUPS:
        pic.append(rf"\node[anchor=east] at (-0.1,{y - 0.42:.2f}) {{{label}}};")
        for k, c in enumerate(CONFIGS):
            n = sum(1 for x in by[c] if not x["correct"] and x["reason"] in reasons)
            yy = y - k * 0.21
            pic.append(rf"\fill[{bar_cols[k]}] (0,{yy - 0.09:.2f}) rectangle ({max(n * scale, 0.02):.2f},{yy + 0.09:.2f});")
            if n:
                pic.append(rf"\node[anchor=west, font=\tiny] at ({n * scale:.2f},{yy:.2f}) {{{n}}};")
        y -= 1.15
    lx = 0.0
    for k, c in enumerate(CONFIGS):
        pic.append(rf"\fill[{bar_cols[k]}] ({lx:.2f},{y + 0.1:.2f}) rectangle ({lx + 0.3:.2f},{y + 0.32:.2f}); "
                   rf"\node[anchor=west, font=\scriptsize] at ({lx + 0.32:.2f},{y + 0.21:.2f}) {{{SHORT[c]}}};")
        lx += 3.2
    pic.append(r"\end{tikzpicture}")
    (OUT / "fig_failures.tex").write_text("\n".join(pic) + "\n")

    # 5. routing matrices (multi): expected agent (rows) x routed-to (cols), per model
    expected = {}
    for it in items:
        for t, e in enumerate(it["expect"]):
            a = e.get("agent", "helpdesk_orchestrator")
            expected[(it["id"], t)] = a[0] if isinstance(a, list) else a
    pics = []
    for c in [c for c in CONFIGS if c.startswith("multi")]:
        m = {(a, b): 0 for a in AGENTS for b in AGENTS}
        for x in by[c]:
            ok = x["routed"]
            exp = expected[(x["id"], x["turn"])]
            got = exp if ok else x["first_agent"]
            m[(exp, got)] += 1
        s_ = 1.25
        pic = [r"\begin{tikzpicture}[font=\scriptsize]",
               rf"\node[font=\small\bfseries] at ({1.2 + 2 * s_:.2f},0.85) {{{SHORT[c]}}};",
               rf"\node[font=\scriptsize\itshape] at ({1.2 + 2 * s_:.2f},0.47) {{routed to}};"]
        for j, b in enumerate(AGENTS):
            pic.append(rf"\node[font=\tiny] at ({1.2 + j * s_ + s_ / 2:.2f},0.12) {{{AGENT_SHORT[b]}}};")
        for i, a in enumerate(AGENTS):
            y = -(i + 1) * 0.5
            pic.append(rf"\node[anchor=east] at (1.15,{y + 0.25:.2f}) {{{AGENT_SHORT[a]}}};")
            row_total = sum(m[(a, b)] for b in AGENTS) or 1
            for j, b in enumerate(AGENTS):
                n = m[(a, b)]
                v = 100 * n / row_total
                col = f"good!{int(v)}!white" if a == b else (f"bad!{int(min(100, v * 3))}!white" if n else "gray!8")
                x0 = 1.2 + j * s_
                pic.append(rf"\fill[{col}] ({x0:.2f},{y:.2f}) rectangle ({x0 + s_ - 0.05:.2f},{y + 0.45:.2f});")
                if n:
                    pic.append(rf"\node at ({x0 + s_ / 2 - 0.025:.2f},{y + 0.225:.2f}) {{{n}}};")
        pic.append(rf"\node[font=\scriptsize\itshape, rotate=90] at (-0.35,{-1.0:.2f}) {{expected}};")
        pic.append(r"\end{tikzpicture}")
        pics.append("\n".join(pic))
    (OUT / "fig_routing.tex").write_text("\n\\hspace{0.6cm}\n".join(pics) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in (ROOT / "eval/results/scored.jsonl").read_text().splitlines() if line]
    items = [json.loads(line) for line in (ROOT / "eval/questions.jsonl").read_text().splitlines() if line]
    by = defaultdict(list)
    for r in rows:
        by[r["config"]].append(r)

    # headline
    lines = []
    for c in CONFIGS:
        xs = by[c]
        g = [x for x in xs if x["grounded"] is not None]
        ref = [x for x in xs if x["behavior"] == "refuse"]
        nonref = [x for x in xs if x["behavior"] != "refuse"]
        rt = [x for x in xs if x["routed"] is not None]
        lat = sorted(x["seconds"] for x in xs)
        lines.append(" & ".join([
            SHORT[c], pct(sum(x["correct"] for x in xs), len(xs)), pct(sum(x["grounded"] for x in g), len(g)),
            pct(sum(x["refused"] for x in ref), len(ref)), pct(sum(x["refused"] for x in nonref), len(nonref)),
            pct(sum(x["routed"] for x in rt), len(rt)) if rt else "--",
            f"{statistics.mean(lat):.1f} / {lat[int(0.9 * (len(lat) - 1))]:.1f}"]) + r" \\")
    (OUT / "headline.tex").write_text("\n".join(lines) + "\n")

    # by category
    lines = []
    for c in CONFIGS:
        cells = []
        for cat in CATS:
            xs = [x for x in by[c] if x["category"] == cat]
            cells.append(f"{100 * sum(x['correct'] for x in xs) / len(xs):.0f}" if xs else "--")
        lines.append(SHORT[c] + " & " + " & ".join(cells) + r" \\")
    (OUT / "category.tex").write_text("\n".join(lines) + "\n")

    # bar chart (plain TikZ: pgfplots is not part of every TeX install)
    def rate(c, grounded=False):
        xs = [x for x in by[c] if (x["grounded"] is not None if grounded else True)]
        return 100 * sum((x["grounded"] if grounded else x["correct"]) for x in xs) / len(xs)

    h = 4.0  # cm for 100%
    pic = [r"\begin{tikzpicture}[font=\small]",
           rf"\draw[gray!60] (0,0) -- (13.2,0);"]
    for t in (25, 50, 75, 100):
        pic.append(rf"\draw[gray!20] (0,{h * t / 100:.2f}) -- (13.2,{h * t / 100:.2f}); "
                   rf"\node[left,font=\scriptsize,gray] at (0,{h * t / 100:.2f}) {{{t}\%}};")
    for i, c in enumerate(CONFIGS):
        x0 = 0.6 + i * 3.2
        for j, (val, col) in enumerate(((rate(c), "accent"), (rate(c, True), "accent!40"))):
            x = x0 + j * 1.05
            pic.append(rf"\fill[{col}] ({x:.2f},0) rectangle ({x + 0.9:.2f},{h * val / 100:.2f}); "
                       rf"\node[above,font=\scriptsize] at ({x + 0.45:.2f},{h * val / 100:.2f}) {{{val:.0f}}};")
        pic.append(rf"\node[below] at ({x0 + 0.97:.2f},0) {{{SHORT[c]}}};")
    pic += [r"\fill[accent] (4.0,4.6) rectangle (4.3,4.85); \node[right] at (4.3,4.72) {Accuracy};",
            r"\fill[accent!40] (6.6,4.6) rectangle (6.9,4.85); \node[right] at (6.9,4.72) {Groundedness};",
            r"\end{tikzpicture}"]
    (OUT / "chart.tex").write_text("\n".join(pic) + "\n")

    # consistency
    lines = []
    changed = []
    for c in CONFIGS:
        per = defaultdict(list)
        for x in by[c]:
            per[(x["id"], x["turn"])].append(x)
        unstable = sum(len({x["correct"] for x in v}) > 1 for v in per.values())
        chg = 0
        for k, v in sorted(per.items()):
            v = sorted(v, key=lambda x: x["repeat"])
            if len({x["facts"] for x in v}) > 1:
                chg += 1
                changed.append((c, k, v))
        lines.append(f"{SHORT[c]} & {unstable}/{len(per)} & {chg}/{len(per)} \\\\")
    (OUT / "consistency.tex").write_text("\n".join(lines) + "\n")
    lines = []
    for c, k, v in changed:
        marks = " ".join(r"\cmark" if x["correct"] else r"\xmark" for x in v)
        facts = r" $\|$ ".join(tex(x["facts"])[:40] for x in v)
        item = k[0] + (f".{k[1] + 1}" if k[0] == "V01" else "")
        lines.append(f"{SHORT[c]} & {item} & {marks} & \\texttt{{\\scriptsize {facts}}} \\\\")
    (OUT / "changed.tex").write_text("\n".join(lines) + "\n")

    # per question
    lines = []
    keys = sorted({(x["id"], x["turn"]) for x in rows})
    for k in keys:
        cells = []
        for c in CONFIGS:
            xs = [x for x in by[c] if (x["id"], x["turn"]) == k]
            n = sum(x["correct"] for x in xs)
            cell = f"{n}/{len(xs)}"
            cells.append(f"\\textbf{{{cell}}}" if n == len(xs) else (f"\\textcolor{{bad}}{{{cell}}}" if n == 0 else cell))
        item = k[0] + (f".{k[1] + 1}" if k[0] == "V01" else "")
        lines.append(f"{item} & " + " & ".join(cells) + r" \\")
    (OUT / "perquestion.tex").write_text("\n".join(lines) + "\n")

    # question set
    lines = []
    for it in items:
        for i, (q, e) in enumerate(zip(it["turns"], it["expect"])):
            item = it["id"] + (f".{i + 1}" if len(it["turns"]) > 1 else "")
            cat = it["category"].replace("_", " ")
            lines.append(f"{item} & {tex(cat)} & {tex(q)} & \\textit{{{tex(e['behavior'])}}}: {tex(e['answer'])} \\\\")
    (OUT / "questions.tex").write_text("\n".join(lines) + "\n")

    # routing errors (multi)
    mis = defaultdict(int)
    for r in rows:
        if r["routed"] is False:
            mis[(r["config"], r["id"], r["first_agent"])] += 1
    lines = [f"{SHORT[c]} & {i} & {tex(a)} & {n}/3 \\\\" for (c, i, a), n in sorted(mis.items())]
    (OUT / "misroutes.tex").write_text("\n".join(lines) + "\n")
    figures(by, rows, items)
    print(f"wrote {len(list(OUT.glob('*.tex')))} tables/figures to {OUT}")


if __name__ == "__main__":
    main()
