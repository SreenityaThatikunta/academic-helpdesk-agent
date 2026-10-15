"""Instructor contact lookup (emails in faculty.csv are dummy values)."""

import difflib

from helpdesk.tools._data import table
from helpdesk.tools.timetable import find_courses, lookup_course


def _faculty_for_course(code: str) -> list[dict]:
    fac = table("faculty")
    rows = fac[fac["courses"].str.split(";").apply(lambda cs: code in cs)]
    return rows[["name", "email", "department"]].to_dict("records")


def get_instructor_email(course_or_instructor: str) -> dict:
    """Find the instructor(s) and their email address for a course, or the email of a
    named instructor.

    Args:
        course_or_instructor: A course code ("CSL7650"), a course name ("Autonomous Systems"),
            or an instructor's name ("Gaurav Harit").

    Returns:
        found: whether a match was found.
        instructors: name, email, department (emails are dummy values for this project).
        course: the matched course, when looked up by course.
        suggestions: closest courses when a course code was not found.
    """
    rows = find_courses(course_or_instructor)
    if not rows.empty:
        course = lookup_course(course_or_instructor)["courses"][0]
        instructors = _faculty_for_course(course["course_code"])
        return {
            "found": bool(instructors),
            "course": {k: course[k] for k in ("course_code", "course_name", "department")},
            "instructors": instructors,
            "source": ["faculty.csv (dummy emails)", *sorted(set(rows["source"]))],
        }

    fac = table("faculty")
    names = fac["name"].tolist()
    q = course_or_instructor.strip().lower()
    hit = fac[fac["name"].str.lower().str.contains(q, regex=False)] if len(q) > 2 else fac.iloc[0:0]
    if hit.empty:
        close = difflib.get_close_matches(course_or_instructor, names, n=3, cutoff=0.75)
        hit = fac[fac["name"].isin(close)]
    if not hit.empty:
        return {
            "found": True,
            "instructors": hit[["name", "email", "department", "courses"]].to_dict("records"),
            "source": ["faculty.csv (dummy emails)"],
        }

    not_found = lookup_course(course_or_instructor)
    return {
        "found": False,
        "query": course_or_instructor,
        "message": f"No course or instructor matching '{course_or_instructor}' was found for Semester I, AY 2026-27.",
        "suggestions": not_found.get("suggestions", []),
    }
