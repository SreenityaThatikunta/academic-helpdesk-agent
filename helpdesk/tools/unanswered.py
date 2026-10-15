"""Log questions the helpdesk could not answer, for a human to follow up."""

import json
import uuid
from datetime import datetime

from helpdesk import config


def log_unanswered_question(question: str, reason: str) -> dict:
    """Record a question the helpdesk cannot answer so a human can follow up.
    Call this whenever you tell the student you don't know.

    Args:
        question: The student's question, as asked.
        reason: Why it couldn't be answered, e.g. "out of scope: campus dining" or
            "in scope but not found in the documents".

    Returns:
        status "logged" and a ticket id for the student.
    """
    entry = {
        "id": uuid.uuid4().hex[:8],
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "question": question.strip(),
        "reason": reason.strip(),
        "status": "open",
    }
    config.UNANSWERED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with config.UNANSWERED_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return {"status": "logged", "ticket_id": entry["id"], "message": "Forwarded to the academic office for a human answer."}


def read_unanswered(status: str = "open") -> list[dict]:
    """All logged questions with the given status (for humans / reports, not an agent tool)."""
    if not config.UNANSWERED_LOG.exists():
        return []
    rows = [json.loads(line) for line in config.UNANSWERED_LOG.read_text().splitlines() if line.strip()]
    return [r for r in rows if not status or r["status"] == status]
