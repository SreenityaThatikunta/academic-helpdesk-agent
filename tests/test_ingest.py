"""Unit tests for the ingestion / retrieval helpers (no Ollama or Chroma needed)."""

from helpdesk.ingest import CHUNK_CHARS, _HTMLText, mask_emails, split_text
from helpdesk.rag import BM25, tokenize


def test_split_text_short_is_single_chunk():
    assert split_text("hello world") == ["hello world"]


def test_split_text_respects_size_and_overlaps():
    paras = [f"Paragraph {i}. " + "word " * 60 for i in range(40)]
    text = "\n\n".join(paras)
    chunks = split_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= CHUNK_CHARS for c in chunks)
    # consecutive chunks share some text (overlap)
    assert any(chunks[i][-50:].split()[-1] in chunks[i + 1] for i in range(len(chunks) - 1))
    # nothing lost: every paragraph label appears somewhere
    assert all(f"Paragraph {i}." in text and any(f"Paragraph {i}." in c for c in chunks) for i in range(40))


def test_html_tables_become_pipe_rows():
    p = _HTMLText()
    p.feed(
        "<html><nav>Menu</nav><script>x=1</script>"
        "<table><tr><th>Type</th><th>Credits</th></tr><tr><td>Open Electives (OE)</td><td>10.0</td></tr></table>"
        "</html>"
    )
    text = p.text()
    assert "Menu" not in text and "x=1" not in text
    assert "Open Electives (OE) | 10.0" in text


def test_mask_emails_keeps_office_addresses_only():
    out = mask_emails("Write to examhelp@iitj.ac.in or gharit@iitj.ac.in")
    assert "examhelp@iitj.ac.in" in out
    assert "gharit@iitj.ac.in" not in out


def test_tokenize_keeps_course_codes():
    assert "lal4070" in tokenize("What is LAL4070 about?")
    assert "what" not in tokenize("What is LAL4070 about?")


def test_bm25_prefers_exact_code_match():
    bm = BM25(
        ["a", "b", "c"],
        [
            "Health Economics LAL4070 syllabus and objectives",
            "Economics of development and growth",
            "Introduction to sociology",
        ],
    )
    assert bm.top("LAL4070 syllabus", 3)[0] == "a"


def test_amendment_marks_old_passage_superseded(tmp_path, monkeypatch):
    import pandas as pd

    from helpdesk import ingest

    doc = tmp_path / "docs" / "regs.txt"
    doc.parent.mkdir()
    doc.write_text("4.1.9 Attendance. Even below 75% the student will be allowed to appear for the exams.\n\n"
                   + "Unrelated grading text. " * 200)
    monkeypatch.setattr(ingest, "DATA", tmp_path)
    row = pd.Series({"doc_id": "D01", "filename": "docs/regs.txt", "title": "Regs", "category": "regulations",
                     "date": "2019", "source": "x", "status": "current"})
    amend = pd.DataFrame([{"doc_id": "D01", "match": "allowed to appear for the exams", "superseded_by": "D02",
                           "note": "replaced"}])
    chunks = ingest.chunk_document(row, amend, {"D02": "Circular 51"})
    hit = [c for c in chunks if "allowed to appear" in c.text]
    assert hit and all(c.meta["status"] == "superseded" and "SUPERSEDED by Circular 51" in c.text for c in hit)
    assert any(c.meta["status"] == "current" for c in chunks)
