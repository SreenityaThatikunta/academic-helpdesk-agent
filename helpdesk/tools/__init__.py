"""Agent tools. Each is a plain function with type hints + docstring, as ADK expects."""

from helpdesk.tools.email_draft import draft_email
from helpdesk.tools.faculty import get_instructor_email
from helpdesk.tools.retrieval import search_documents
from helpdesk.tools.timetable import get_slot, list_courses, lookup_course
from helpdesk.tools.unanswered import log_unanswered_question

ALL_TOOLS = [
    search_documents,
    lookup_course,
    get_slot,
    list_courses,
    get_instructor_email,
    draft_email,
    log_unanswered_question,
]

__all__ = [t.__name__ for t in ALL_TOOLS] + ["ALL_TOOLS"]
