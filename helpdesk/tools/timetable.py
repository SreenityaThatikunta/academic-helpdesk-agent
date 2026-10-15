"""Course, slot and exam-schedule lookups over data/csv/ (Semester I, AY 2026-27)."""

import difflib
import re

import pandas as pd

from helpdesk.tools._data import normalize_code, source_of, table

# Words students use for a department -> department_code in courses.csv
DEPT_ALIASES = {
    "SoLA": ["humanities", "hss", "liberal arts", "sola", "social science", "economics", "digital humanities", " ih "],
    "CSE": ["cse", "computer science", "cs department"],
    "AIDE": ["aide", "artificial intelligence", "data science", "ai department"],
    "EE": ["electrical", "ee "],
    "ECE": ["electronics", "ece"],
    "ME": ["mechanical"],
    "CIE": ["civil"],
    "Chemical": ["chemical engineering"],
    "Chemistry": ["chemistry"],
    "Physics": ["physics"],
    "Math": ["math", "mathematics"],
    "MT": ["materials", "metallurgy", "metallurgical"],
    "BSBE": ["bioscience", "bioengineering", "biology"],
    "SME": ["management", "sme", "mba"],
    "SOD": ["design", "sod"],
    "MedTech": ["medical tech"],
}


def _offerings(rows: pd.DataFrame) -> list[dict]:
    """Collapse multiple sections of the same course into one record."""
    out = []
    for code, g in rows.groupby("course_code", sort=False):
        first = g.iloc[0]

        def uniq(col):
            return sorted({v for v in g[col] if v})

        out.append(
            {
                "course_code": code,
                "course_name": first["course_name"],
                "department": first["department"],
                "level": first["level"],
                "ltp": first["ltp"],
                "credits": first["credits"],
                "instructors": uniq("instructor"),
                "slots": uniq("slot"),
                "slot_codes": uniq("slot_code"),
                "classrooms": uniq("classroom"),
                "category": first["category"],
                "ih_group": first["ih_group"],
                "sections": len(g),
            }
        )
    return out


def _suggest(query: str, n: int = 3) -> list[dict]:
    courses = table("courses")
    code = normalize_code(query)
    if code:
        codes = sorted(set(courses["course_code"]) - {""})
        prefix = re.match(r"[A-Z]+", code).group()
        close = difflib.get_close_matches(code, codes, n=10, cutoff=0.6)
        # Same department prefix first (CSL7570 -> CSL..., before MTL7570)
        close.sort(key=lambda c: (not c.startswith(prefix), -difflib.SequenceMatcher(None, code, c).ratio()))
        hits = close[:n]
    else:
        names = sorted(set(courses["course_name"]))
        matched = difflib.get_close_matches(query, names, n=n, cutoff=0.5)
        hits = list(dict.fromkeys(courses[courses["course_name"].isin(matched)]["course_code"]))[:n]
    rows = courses[courses["course_code"].isin(hits)].drop_duplicates("course_code").set_index("course_code")
    return [{"course_code": c, "course_name": rows.loc[c, "course_name"]} for c in hits if c in rows.index]


def find_courses(query: str) -> pd.DataFrame:
    """Rows of courses.csv matching a course code or (part of) a course name."""
    courses = table("courses")
    code = normalize_code(query)
    if code:
        return courses[courses["course_code"] == code]
    q = query.strip().lower()
    hit = courses[courses["course_name"].str.lower().str.contains(re.escape(q), regex=True)]
    if hit.empty:
        words = [w for w in re.findall(r"[a-z]+", q) if len(w) > 2]
        if words:
            mask = pd.Series(True, index=courses.index)
            for w in words:
                mask &= courses["course_name"].str.lower().str.contains(w)
            hit = courses[mask]
    return hit


def lookup_course(course: str) -> dict:
    """Look up a course offered in Semester I, AY 2026-27 by course code or course name.

    Args:
        course: A course code such as "CSL7650" or a course name such as "Autonomous Systems".

    Returns:
        found: whether the course is offered this semester.
        courses: code, name, department, credits, L-T-P, instructors, slot, classroom.
        suggestions: closest course codes/names when not found ("did you mean").
        source: document the data came from (cite it).
    """
    rows = find_courses(course)
    if rows.empty:
        return {
            "found": False,
            "query": course,
            "message": f"No course matching '{course}' is offered in Semester I, AY 2026-27.",
            "suggestions": _suggest(course),
        }
    return {"found": True, "query": course, "courses": _offerings(rows), "source": source_of(rows)}


def get_slot(course: str) -> dict:
    """Get the time-table slot, weekly class timings, classroom, and minor/major exam
    dates for a course in Semester I, AY 2026-27.

    Args:
        course: A course code such as "CSL7650" or a course name such as "Autonomous Systems".

    Returns:
        For each matching course: slot, weekly class times (day + time), classroom,
        and exam schedule entries; plus the source documents to cite.
    """
    found = lookup_course(course)
    if not found["found"]:
        return found
    slots, exams = table("slots"), table("exam_schedule")
    sources = set(found["source"])
    for c in found["courses"]:
        times = slots[(slots["slot"].isin(c["slot_codes"])) & (slots["type"] == "theory")]
        c["weekly_schedule"] = [f"{r.day} {r.time}" for r in times.itertuples()]
        ex = exams[exams["slot"].isin(c["slot_codes"])]
        c["exams"] = [
            {"exam": r.exam, "date": r.date, "time": r.time, "status": r.status} for r in ex.itertuples()
        ]
        sources |= set(source_of(times)) | set(source_of(ex))
    found["source"] = sorted(sources)
    return found


def _match_department(department: str) -> list[str]:
    d = f" {department.strip().lower()} "
    codes = [code for code, words in DEPT_ALIASES.items() if any(w in d for w in words) or code.lower() == d.strip()]
    if codes:
        return codes
    courses = table("courses")
    hit = courses[courses["department"].str.lower().str.contains(re.escape(department.strip().lower()))]
    return sorted(set(hit["department_code"]))


def list_courses(department: str = "", level: str = "") -> dict:
    """List and count the courses offered (floated) in Semester I, AY 2026-27,
    filtered by department and/or course level.

    Args:
        department: Department or school, e.g. "Humanities" (= Institute Humanities / IH courses,
            including IH bouquet courses taught by AIDE), "CSE", "Mathematics". Empty for all.
        level: Course level, e.g. "400" or "4" for 400-level (course number 4xxx). Empty for all.

    Returns:
        count: number of distinct courses matching the filters.
        courses: code, name, department, IH group, slot, instructors for each.
        source: document to cite.
    """
    df = table("courses")
    applied = {}
    if department:
        codes = _match_department(department)
        mask = df["department_code"].isin(codes)
        if "SoLA" in codes:
            # "Humanities" means Institute Humanities (IH): SoLA courses plus the IH2/IH3
            # bouquet courses taught by other departments (e.g. AIDE economics)
            mask |= df["ih_group"] != ""
            applied["department"] = "Humanities (IH): SoLA courses + IH2/IH3 bouquet courses from other departments"
        else:
            applied["department"] = codes or f"no department matches '{department}'"
        df = df[mask]
    if level:
        m = re.search(r"\d", str(level))
        if m:
            df = df[df["level"] == f"{m.group()}00"]
            applied["level"] = f"{m.group()}00-level (course numbers {m.group()}xxx)"
    offerings = _offerings(df)
    return {
        "count": len(offerings),
        "filters": applied,
        "courses": [
            {k: o[k] for k in ("course_code", "course_name", "department", "ih_group", "slots", "instructors")}
            for o in offerings
        ],
        "source": source_of(df),
    }
