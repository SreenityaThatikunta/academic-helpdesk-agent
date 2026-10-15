"""Save an email draft for the student to review. Nothing is ever sent."""

import re
from datetime import datetime

from helpdesk import config

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def draft_email(to: str, subject: str, body: str, cc: str = "") -> dict:
    """Save an email draft (e.g. a leave request or make-up exam request) for the student
    to review. The email is NOT sent.

    Args:
        to: Recipient email address (from get_instructor_email).
        subject: Email subject line.
        body: Full email body, including greeting and sign-off.
        cc: Optional comma-separated CC addresses.

    Returns:
        status "draft_saved", the file path of the draft, and the draft text.
    """
    recipients = [a.strip() for a in [to, *cc.split(",")] if a.strip()]
    bad = [a for a in recipients if not EMAIL_RE.match(a)]
    if bad:
        return {"status": "error", "message": f"Invalid email address(es): {', '.join(bad)}"}
    if not subject.strip() or not body.strip():
        return {"status": "error", "message": "Subject and body must not be empty."}

    now = datetime.now()
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")[:40] or "draft"
    path = config.DRAFTS_DIR / f"{now:%Y%m%d-%H%M%S}_{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        f"To: {to.strip()}\n"
        + (f"Cc: {cc.strip()}\n" if cc.strip() else "")
        + f"Subject: {subject.strip()}\n\n{body.strip()}\n"
    )
    path.write_text(f"<!-- DRAFT created {now:%Y-%m-%d %H:%M} by Academic Helpdesk. NOT SENT. -->\n{text}")
    return {
        "status": "draft_saved",
        "sent": False,
        "path": str(path.relative_to(config.ROOT)),
        "draft": text,
        "note": "Review and send it yourself from your institute email; the helpdesk does not send emails.",
    }
