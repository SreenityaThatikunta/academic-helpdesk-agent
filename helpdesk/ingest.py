"""Load documents -> chunk -> embed with Ollama -> store in ChromaDB.

Every document listed in data/manifest.csv is loaded page by page so chunks
can be cited as "<title>, p. N" (for spreadsheets the "page" is the sheet name).

Usage:
    .venv/bin/python -m helpdesk.ingest            # add/update
    .venv/bin/python -m helpdesk.ingest --reset    # rebuild the collection
"""

import argparse
import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

import chromadb
import ollama
import pandas as pd
import pymupdf

from helpdesk import config

DATA = config.ROOT / "data"
MANIFEST = DATA / "manifest.csv"
AMENDMENTS = DATA / "amendments.csv"
OCR_DIR = DATA / "ocr"

CHUNK_CHARS = 1800  # ~450 tokens
OVERLAP_CHARS = 250
MIN_CHUNK_CHARS = 80
# Short documents (circulars, notices) are kept as one chunk so e.g. a "revised policy"
# is never separated from the "existing policy" it replaces
WHOLE_DOC_CHARS = 3200
EMBED_BATCH = 32
# nomic-embed-text is trained with task prefixes
DOC_PREFIX, QUERY_PREFIX = "search_document: ", "search_query: "

# Sheets that hold personal contact data or nothing a student would ask about
SKIP_SHEETS = {"Time Table Committee Members", "List of MinorSpecialization Coo", "Classroom Allocation"}

# Office mailboxes are fine to keep; any other address is a person's and gets masked
OFFICE_EMAILS = {"examhelp@iitj.ac.in", "registration@iitj.ac.in", "erp@iitj.ac.in", "phc@iitj.ac.in",
                 "office_academics@iitj.ac.in", "acad@iitj.ac.in"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


@dataclass
class Page:
    text: str
    page: str  # page number or sheet name


@dataclass
class Chunk:
    id: str
    text: str
    meta: dict


# ---------- loaders ----------


def load_pdf(path: Path) -> list[Page]:
    ocr = OCR_DIR / f"{path.stem}.txt"
    if ocr.exists():
        return [Page(t, str(i + 1)) for i, t in enumerate(ocr.read_text().split("\f"))]
    with pymupdf.open(path) as d:
        return [Page(p.get_text(), str(i + 1)) for i, p in enumerate(d)]


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section", "table"}

    def __init__(self):
        super().__init__()
        self.skip, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag == "tr" or tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(re.sub(r"\s+", " ", data))

    def text(self) -> str:
        t = "".join(self.parts)
        t = re.sub(r"###\d+\$\$\$_RedirectToLoginPage_%%%\d+!!!", "", t)
        t = re.sub(r"[ \t]*\|[ \t]*(\|[ \t]*)+", " | ", t)
        t = re.sub(r"[ \t]+\n", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def load_html(path: Path) -> list[Page]:
    p = _HTMLText()
    p.feed(path.read_text(errors="ignore"))
    return [Page(p.text(), "1")]


def load_xlsx(path: Path) -> list[Page]:
    pages = []
    for name, df in pd.read_excel(path, sheet_name=None, header=None).items():
        if name in SKIP_SHEETS:
            continue
        df = df.dropna(how="all").dropna(axis=1, how="all")
        lines = []
        for _, row in df.iterrows():
            cells = [re.sub(r"\s+", " ", str(v)).strip() for v in row if pd.notna(v) and str(v).strip()]
            if cells:
                lines.append(" | ".join(cells))
        if lines:
            pages.append(Page("\n".join(lines), str(name)))
    return pages


def load_text(path: Path) -> list[Page]:
    return [Page(path.read_text(), "1")]


LOADERS = {".pdf": load_pdf, ".html": load_html, ".xlsx": load_xlsx, ".txt": load_text, ".md": load_text}


# ---------- chunking ----------


def mask_emails(text: str) -> str:
    return EMAIL_RE.sub(lambda m: m.group() if m.group().lower() in OFFICE_EMAILS else "[faculty email: use lookup]", text)


def clean(text: str) -> str:
    text = text.replace("​", "").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()


def split_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    """Greedy split on paragraph / line / sentence boundaries, with overlap."""
    if len(text) <= size:
        return [text]
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start:end]
            for sep in ("\n\n", "\n", ". ", " "):
                cut = window.rfind(sep)
                if cut > size * 0.5:
                    end = start + cut + len(sep)
                    break
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


def load_amendments() -> pd.DataFrame:
    if not AMENDMENTS.exists():
        return pd.DataFrame(columns=["doc_id", "match", "superseded_by", "note"])
    return pd.read_csv(AMENDMENTS, dtype=str).fillna("")


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def chunk_document(row: pd.Series, amendments: pd.DataFrame | None = None, titles: dict | None = None) -> list[Chunk]:
    path = DATA / row.filename
    pages = LOADERS[path.suffix.lower()](path)
    texts = [mask_emails(clean(pg.text)) for pg in pages]
    whole = sum(len(t) for t in texts) <= WHOLE_DOC_CHARS
    if whole and len(pages) > 1:
        pages = [Page("\n\n".join(texts), f"1-{len(pages)}")]
        texts = [pages[0].text]
    amends = amendments[amendments["doc_id"] == row.doc_id] if amendments is not None else []
    titles = titles or {}
    chunks = []
    for pg, text in zip(pages, texts):
        for i, piece in enumerate([text] if whole else split_text(text)):
            if len(piece) < MIN_CHUNK_CHARS:
                continue
            status = row.status or "current"
            note = ""
            for a in getattr(amends, "itertuples", lambda: [])():
                if _norm_ws(a.match) in _norm_ws(piece):
                    status = "superseded"
                    note = f" | SUPERSEDED by {titles.get(a.superseded_by, a.superseded_by)}: {a.note}"
            cid = hashlib.sha1(f"{row.doc_id}|{pg.page}|{i}|{piece}".encode()).hexdigest()[:16]
            # Contextual header: chunks rarely name their own document ("IH2", "PhD"),
            # so embed/index the title and date with every chunk
            where = f"page {pg.page}" if re.fullmatch(r"\d+(-\d+)?", pg.page) else f"sheet {pg.page}"
            header = f"[{row.title} | {row.date} | {where}{note}]"
            chunks.append(
                Chunk(
                    id=f"{row.doc_id}-{cid}",
                    text=f"{header}\n{piece}",
                    meta={
                        "doc_id": row.doc_id,
                        "title": row.title,
                        "filename": Path(row.filename).name,
                        "category": row.category,
                        "date": str(row.date),
                        "status": status,
                        "source": str(row.source),
                        "page": pg.page,
                        "chunk": i,
                    },
                )
            )
    return chunks


# ---------- embedding + store ----------


def embed(texts: list[str], prefix: str = DOC_PREFIX) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = [prefix + t for t in texts[i : i + EMBED_BATCH]]
        out.extend(ollama.embed(model=config.EMBED_MODEL, input=batch)["embeddings"])
    return out


def get_collection(reset: bool = False):
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    if reset:
        try:
            client.delete_collection(config.CHROMA_COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(config.CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})


def ingest(reset: bool = False) -> None:
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna("")
    amendments = load_amendments()
    titles = dict(zip(manifest.doc_id, manifest.title))
    col = get_collection(reset)
    total = 0
    for _, row in manifest.iterrows():
        chunks = chunk_document(row, amendments, titles)
        # Drop stale chunks for this doc so re-ingesting an edited file doesn't leave duplicates
        col.delete(where={"doc_id": row.doc_id})
        if chunks:
            col.add(
                ids=[c.id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[c.meta for c in chunks],
                embeddings=embed([c.text for c in chunks]),
            )
        total += len(chunks)
        print(f"{row.doc_id} {len(chunks):4d} chunks  {row.title}")
    print(f"\n{total} chunks from {len(manifest)} documents -> {config.CHROMA_DIR}/{config.CHROMA_COLLECTION}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop and rebuild the collection")
    ingest(ap.parse_args().reset)
