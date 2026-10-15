"""Build the structured CSVs used by the schedule/email tools from the
Semester-I AY 2026-27 spreadsheets in data/docs/.

Outputs (data/csv/):
  courses.csv  - one row per course offering (all departments)
  slots.csv    - slot letter -> day + time, from the slot system grid
  faculty.csv  - unique instructors with DUMMY email addresses
  exam_schedule.csv - minor + major exam slot schedule (date, time, slot)

Usage: .venv/bin/python scripts/build_csvs.py
"""

import re
import sys
from pathlib import Path

import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "data" / "docs"
OUT = ROOT / "data" / "csv"
COURSES_XLSX = DOCS / "25_Finalized_Courses_List_AY2026-27_SemI.xlsx"
SLOTS_XLSX = DOCS / "26_Slot_System_AY2026-27_SemI.xlsx"
MAJOR_XLSX = DOCS / "30_Major_Exam_Timetable_AY2026-27_SemI.xlsx"
# Institute Humanities (IH) bouquets offered this semester: every course code in these
# syllabus PDFs counts as IH, whichever department teaches it (e.g. AIDE economics courses)
IH_SYLLABI = {"IH2": DOCS / "28_IH2_Courses_Syllabus_AY2026-27_SemI.pdf",
              "IH3": DOCS / "29_IH3_Courses_Syllabus_AY2026-27_SemI.pdf"}
SEMESTER = "AY 2026-27 Semester I"
DUMMY_DOMAIN = "iitj.example"

# Sheet tab -> department name
DEPARTMENTS = {
    "EE": "Electrical Engineering",
    "ECE": "Electronics and Communication Engineering",
    "SoLA": "School of Liberal Arts (Humanities & Social Sciences)",
    "CET": "Centre for Emerging Technologies",
    "CIE": "Civil and Infrastructure Engineering",
    "MT": "Metallurgical and Materials Engineering",
    "Aero": "Aerospace Engineering",
    "EnAuto": "Energy and Automotive Engineering",
    "BSBE": "Bioscience and Bioengineering",
    "Math": "Mathematics",
    "Chemical": "Chemical Engineering",
    "AIDE": "Artificial Intelligence and Data Engineering",
    "CSE": "Computer Science and Engineering",
    "MedTech": "Medical Technologies",
    "SME": "School of Management and Entrepreneurship",
    "Physics": "Physics",
    "Chemistry": "Chemistry",
    "SOD": "School of Design",
    "ME": "Mechanical Engineering",
    "DESE": "Department of Engineering Science",
}

# Allocation-sheet department name keyword -> short code (first match wins)
ALLOCATION_DEPTS = [
    ("liberal arts", "SoLA"), ("digital humanities", "SoLA"), ("economics", "SoLA"),
    ("computer science", "CSE"), ("artificial intelligence", "AIDE"), ("electrical", "EE"),
    ("electronics", "ECE"), ("mechanical", "ME"), ("civil", "CIE"), ("chemical", "Chemical"),
    ("chemistry", "Chemistry"), ("physics", "Physics"), ("mathematics", "Math"), ("materials", "MT"),
    ("bioscience", "BSBE"), ("management", "SME"), ("design", "SOD"), ("medical", "MedTech"),
    ("education technology", "CET"), ("emerging technologies", "CET"), ("energy and automotive", "EnAuto"),
    ("aerospace", "Aero"), ("environmental", "DESE"), ("student", "OSA"), ("institute", "INST"),
]

# Normalised column name -> patterns matched against the sheet header (first match wins)
COLUMNS = {
    "course_code": [r"^course code$", r"^subject code$", r"^code$"],
    "course_name": [r"course name", r"course title", r"subject name", r"name of the course"],
    "ltp": [r"^\[?l-?t-?p\]?", r"^ltp$", r"credit \(l-t-p\)"],
    "credits": [r"^credits?$"],
    "instructor": [r"instructor", r"name of faculty", r"coordinator", r"instructor name"],
    "slot": [r"^slot$", r"preferred slot"],
    "category": [r"categ", r"course type", r"^type$"],
    "offered_for": [r"offered for", r"programme", r"program name", r"^batch$", r"^year$"],
    "remarks": [r"remark", r"comment", r"lab slot", r"lab/tutorial"],
}

CODE_RE = re.compile(r"^[A-Z]{2,4}\d{3,5}[A-Z]?$")


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _clean(v) -> str:
    if pd.isna(v):
        return ""
    s = _norm(v)
    return "" if s.lower() in {"nan", "-", "--"} else s


def _find_header(df: pd.DataFrame) -> int:
    for i in range(min(10, len(df))):
        cells = [_norm(c).lower() for c in df.iloc[i].tolist()]
        if any(c in {"course code", "subject code", "code"} or c.startswith("course code") for c in cells):
            return i
    raise ValueError("header row not found")


def _map_columns(header: list) -> dict:
    cells = [_norm(c).lower() for c in header]
    mapping, used = {}, set()
    for field, patterns in COLUMNS.items():
        for pat in patterns:
            hit = next((j for j, c in enumerate(cells) if j not in used and c != "nan" and re.search(pat, c)), None)
            if hit is not None:
                mapping[field] = hit
                used.add(hit)
                break
    return mapping


def _level(code: str) -> str:
    m = re.search(r"\d", code)
    return f"{m.group()}00" if m and CODE_RE.match(code) else ""


def _dept_code(name: str) -> str:
    """Map a full department name from the allocation sheet to a short code."""
    n = name.lower()
    for kw, code in ALLOCATION_DEPTS:
        if kw in n:
            return code
    return re.sub(r"[^A-Za-z]", "", name)[:10]


def _slot_code(slot: str) -> str:
    """'G (Wed)' -> 'G', 'R (Thu 6 - 7 PM)' -> 'R', 'NG3' -> 'NG3'."""
    m = re.match(r"^([A-Z]{1,3}\d{0,2})\b", slot.strip())
    return m.group(1) if m else ""


def build_allocation() -> pd.DataFrame:
    """Final course list with slots and classrooms (Classroom Allocation sheet)."""
    df = pd.read_excel(SLOTS_XLSX, sheet_name="Classroom Allocation", header=None).dropna(how="all")
    df = df.dropna(axis=1, how="all")
    df.columns = [_norm(c) for c in df.iloc[0]]
    rows = []
    for _, r in df.iloc[1:].iterrows():
        code = _clean(r.iloc[0]).replace(" ", "").upper()
        name = _clean(r["Subject"])
        if not code or not name:
            continue
        dept = _clean(r["Department"]) or "Institute (common course)"
        slot = _clean(r["Slot"])
        rows.append(
            {
                "department_code": _dept_code(dept),
                "department": dept,
                "course_code": code,
                "course_name": name,
                "level": _level(code),
                "ltp": _clean(r["L-T-P"]),
                "credits": _clean(r["Credit"]),
                # Co-Instructor is dropped: it mixes staff ID numbers into names
                "instructor": _clean(r["Instructor"]),
                "slot": slot,
                "slot_code": _slot_code(slot),
                "classroom": _clean(r["Classroom"]),
                "registered": _clean(r["Student Registered*"]),
                "semester": SEMESTER,
                "source": f"{SLOTS_XLSX.name} (Classroom Allocation)",
            }
        )
    return pd.DataFrame(rows)


def ih_groups() -> dict[str, str]:
    """Course code -> IH bouquet ("IH2"/"IH3") from the IH syllabus PDFs."""
    out = {}
    for group, pdf in IH_SYLLABI.items():
        with pymupdf.open(pdf) as d:
            text = "".join(p.get_text() for p in d)
        for code in re.findall(r"\b[A-Z]{3}\d{4}\b", text):
            out.setdefault(code, group)
    return out


def build_courses() -> pd.DataFrame:
    """Classroom allocation first (final); finalized-list rows fill in category / offered_for
    and add courses the allocation doesn't have."""
    alloc = build_allocation()
    final = build_finalized()
    extra = final.drop_duplicates("course_code").set_index("course_code")[["category", "offered_for", "remarks"]]
    alloc = alloc.join(extra, on="course_code")
    missing = final[(final.course_code == "") | ~final.course_code.isin(alloc.course_code)].copy()
    missing["slot_code"] = missing["slot"].map(_slot_code)
    missing["classroom"] = missing["registered"] = ""
    cols = ["department_code", "department", "course_code", "course_name", "level", "ltp", "credits", "instructor",
            "slot", "slot_code", "classroom", "registered", "category", "ih_group", "offered_for", "remarks", "semester",
            "source"]
    courses = pd.concat([alloc, missing], ignore_index=True)
    courses["ih_group"] = courses["course_code"].map(ih_groups())
    return courses[cols].fillna("")


def build_finalized() -> pd.DataFrame:
    sheets = pd.read_excel(COURSES_XLSX, sheet_name=None, header=None)
    rows = []
    for tab, df in sheets.items():
        df = df.dropna(how="all")
        h = _find_header(df)
        cols = _map_columns(df.iloc[h].tolist())
        for _, r in df.iloc[h + 1 :].iterrows():
            rec = {f: _clean(r.iloc[j]) for f, j in cols.items()}
            code = rec.get("course_code", "").replace(" ", "").upper()
            name = rec.get("course_name", "")
            if not name or name.lower().startswith(("course", "subject")):
                continue
            # ME packs credits into "L-T-P (Credits)", e.g. "3-0-0 (3)"
            ltp = rec.get("ltp", "")
            credits = rec.get("credits", "")
            m = re.match(r"^\(?([\d.]+-[\d.]+-[\d.]+)\)?\s*\(?([\d.]+)?\)?$", ltp)
            if m:
                ltp = m.group(1)
                credits = credits or (m.group(2) or "")
            rows.append(
                {
                    "department_code": tab,
                    "department": DEPARTMENTS.get(tab, tab),
                    "course_code": code,
                    "course_name": name,
                    "level": _level(code),
                    "ltp": ltp,
                    "credits": credits,
                    "instructor": rec.get("instructor", ""),
                    "slot": rec.get("slot", ""),
                    "category": rec.get("category", ""),
                    "offered_for": rec.get("offered_for", ""),
                    "remarks": rec.get("remarks", ""),
                    "semester": SEMESTER,
                    "source": COURSES_XLSX.name,
                }
            )
    return pd.DataFrame(rows)


def build_slots() -> pd.DataFrame:
    df = pd.read_excel(SLOTS_XLSX, sheet_name="Slot System", header=None)
    # Row 1 holds day names; theory slots sit in the day column, lab slots in the column after it
    day_cols = {j: _clean(v) for j, v in df.iloc[1].items() if _clean(v) in {"Mon", "Tue", "Wed", "Thu", "Fri"}}
    out = []
    for i in range(2, 13):
        time = _clean(df.iat[i, 0])
        if not time:
            continue
        for j, day in day_cols.items():
            for col, kind in ((j, "theory"), (j + 1, "lab")):
                slot = _clean(df.iat[i, col])
                # Only short slot codes (A, K, L3, M10); skip free-text cells
                if slot and re.fullmatch(r"[A-Z]{1,2}\d{0,2}", slot):
                    out.append({"slot": slot, "type": kind, "day": day, "time": time.replace("–", "-"),
                                "source": SLOTS_XLSX.name})
    return pd.DataFrame(out)


def _exam_sheet(path: Path, sheet, exam: str) -> list[dict]:
    """Parse an exam time table grid: (date, time window) -> slots examined."""
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    hdr = next(i for i in range(len(df)) if re.search(r"\d{2}:\d{2} [AP]M to", _clean(df.iat[i, 2])))
    times = {j: _clean(df.iat[hdr, j]) for j in range(2, df.shape[1]) if _clean(df.iat[hdr, j])}
    title = _clean(df.iat[hdr - 2, 1])
    out = []
    for i in range(hdr + 2, len(df)):
        # "26 November2026" -> "26 November 2026"
        date = re.sub(r"([a-z])(\d)", r"\1 \2", _clean(df.iat[i, 1]))
        if not re.match(r"\d{1,2} \w+ \d{4}", date):
            continue
        for j, time in times.items():
            for slot in re.split(r"\s*\+\s*", _clean(df.iat[i, j])):
                if re.fullmatch(r"[A-Z]{1,3}\d?", slot):
                    out.append({"exam": exam, "semester": SEMESTER, "date": date, "time": time, "slot": slot,
                                "status": "tentative", "source": path.name, "title": title})
    return out


def build_exam_schedule() -> pd.DataFrame:
    return pd.DataFrame(_exam_sheet(SLOTS_XLSX, "Examination", "Minor") + _exam_sheet(MAJOR_XLSX, 0, "Major"))


def _split_instructors(s: str) -> list[str]:
    s = s.replace("**", "")
    parts = re.split(r",|/|&|\band\b|\n|;", s)
    return [p.strip(" .") for p in parts if len(p.strip(" .")) > 2]


def _dummy_email(name: str, taken: set) -> str:
    base = re.sub(r"^(dr|prof)\.?\s+", "", name, flags=re.I)
    slug = ".".join(re.findall(r"[a-z]+", base.lower())) or "faculty"
    email, n = f"{slug}@{DUMMY_DOMAIN}", 2
    while email in taken:
        email, n = f"{slug}{n}@{DUMMY_DOMAIN}", n + 1
    taken.add(email)
    return email


def build_faculty(courses: pd.DataFrame) -> pd.DataFrame:
    seen, taken, rows = {}, set(), []
    for _, c in courses.iterrows():
        for name in _split_instructors(c["instructor"]):
            key = name.lower()
            if key in seen:
                seen[key]["courses"].add(c["course_code"] or c["course_name"])
                continue
            seen[key] = {"name": name, "department": c["department"], "courses": {c["course_code"] or c["course_name"]}}
    for i, (key, f) in enumerate(sorted(seen.items()), start=1):
        rows.append(
            {
                "instructor_id": f"F{i:04d}",
                "name": f["name"],
                "department": f["department"],
                "email": _dummy_email(f["name"], taken),
                "courses": ";".join(sorted(f["courses"])),
                "note": "email is a dummy value",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    courses = build_courses()
    slots = build_slots()
    faculty = build_faculty(courses)
    exams = build_exam_schedule()
    exams.to_csv(OUT / "exam_schedule.csv", index=False)
    courses.to_csv(OUT / "courses.csv", index=False)
    slots.to_csv(OUT / "slots.csv", index=False)
    faculty.to_csv(OUT / "faculty.csv", index=False)
    print(f"courses.csv: {len(courses)} rows across {courses.department_code.nunique()} departments")
    print(f"slots.csv:   {len(slots)} rows, {slots.slot.nunique()} distinct slots")
    print(f"exam_schedule.csv: {len(exams)} rows ({exams.date.nunique()} days)")
    print(f"faculty.csv: {len(faculty)} instructors (dummy emails @{DUMMY_DOMAIN})")


if __name__ == "__main__":
    sys.exit(main())
