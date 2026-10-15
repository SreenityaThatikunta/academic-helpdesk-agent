"""search_documents tool: hybrid search over the regulations, curricula, circulars, calendars."""

from helpdesk import config
from helpdesk.rag import search


def search_documents(query: str, top_k: int = config.TOP_K, document: str = "") -> dict:
    """Search IIT Jodhpur academic documents (regulations, curricula, course syllabi,
    circulars/office orders, academic calendars, exam guidelines) for passages relevant
    to a question.

    Args:
        query: The question or keywords to search for.
        top_k: Number of passages to return (default 5).
        document: Leave EMPTY (search everything) unless the student has told you their programme and
            you need that programme's curriculum, e.g. "CSE Curriculum", "AIDE Curriculum", "EE Curriculum".
            Never use it for rules/regulations questions: amendments live in separate circulars.

    Returns:
        found: False if nothing relevant exists (then say you don't know).
        results: passages, each with `citation` (document title + page to cite),
            `date` (newer documents override older ones), and `status`
            ("superseded" documents are older versions of a rule).
    """
    res = search(query, k=max(1, min(int(top_k), 10)), document=document)
    return {
        "found": res["found"],
        "query": query,
        **({"message": res["message"]} if "message" in res else {}),
        "results": [
            {k: r[k] for k in ("citation", "date", "status", "text")} for r in res["results"]
        ],
    }
