"""Hybrid search over the ingested documents.

Dense (nomic-embed-text via Chroma) and sparse (BM25) rankings are merged with
reciprocal rank fusion. BM25 catches exact tokens the embedding model blurs:
course codes (LAL4070), category abbreviations (IH2, PE, OE), slot letters.
"""

import math
import re
from collections import Counter
from functools import lru_cache

import chromadb
import ollama

from helpdesk import config
from helpdesk.ingest import QUERY_PREFIX

RRF_K = 60  # standard RRF constant
CANDIDATES = 30  # per-retriever pool before fusion
MAX_PER_DOC = 2  # keep one long document (e.g. a programme curriculum) from filling every slot
SUPERSEDED_WEIGHT = 0.5  # older versions of a rule still answer some questions, but rank below current ones
STOPWORDS = set(
    "a an the of to in on for and or is are was be by with as at from that this it i my me do does can what which "
    "how when where who whom why will would should could there their them they you your we our not no if than then "
    "so such any all have has had am".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOPWORDS and len(t) > 1]


@lru_cache(maxsize=1)
def _collection():
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    return client.get_collection(config.CHROMA_COLLECTION)


class BM25:
    def __init__(self, ids: list[str], texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.ids, self.k1, self.b = ids, k1, b
        self.docs = [Counter(tokenize(t)) for t in texts]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = sum(self.lens) / max(1, len(self.lens))
        df = Counter(tok for d in self.docs for tok in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def top(self, query: str, k: int) -> list[str]:
        q = tokenize(query)
        scores = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in d:
                    tf = d[t]
                    s += self.idf[t] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg))
            if s > 0:
                scores.append((s, self.ids[i]))
        return [i for _, i in sorted(scores, reverse=True)[:k]]


@lru_cache(maxsize=1)
def _bm25() -> BM25:
    data = _collection().get(include=["documents"])
    return BM25(data["ids"], data["documents"])


def embed_query(text: str) -> list[float]:
    return ollama.embed(model=config.EMBED_MODEL, input=QUERY_PREFIX + text)["embeddings"][0]


def _citation(meta: dict) -> str:
    page = str(meta["page"])
    where = f"p. {page}" if page.isdigit() else (f"pp. {page}" if re.fullmatch(r"\d+-\d+", page) else f"sheet '{page}'")
    return f"{meta['title']}, {where}"


@lru_cache(maxsize=1)
def _titles() -> dict[str, str]:
    data = _collection().get(include=["metadatas"])
    return {m["doc_id"]: m["title"] for m in data["metadatas"]}


def search(query: str, k: int = config.TOP_K, max_distance: float = config.MAX_DISTANCE, document: str = "") -> dict:
    """Return the top-k chunks for `query` with citation metadata.

    `found` is False when even the closest chunk by embedding is farther than
    `max_distance`; the agent then has nothing to build an answer from.
    `document` restricts the search to documents whose title contains every word of it
    (e.g. "CSE Curriculum").
    """
    col = _collection()
    where, allowed = None, None
    if document.strip():
        words = document.lower().split()
        allowed = {d for d, t in _titles().items() if all(w in t.lower() for w in words)}
        if not allowed:
            return {"found": False, "query": query, "best_distance": None, "results": [],
                    "message": f"No document title matches '{document}'"}
        where = {"doc_id": {"$in": sorted(allowed)}}
    dense = col.query(query_embeddings=[embed_query(query)], n_results=CANDIDATES, include=["distances"], where=where)
    dense_ids, dists = dense["ids"][0], dict(zip(dense["ids"][0], dense["distances"][0]))
    # The distance guard detects off-topic questions across the whole collection; once the
    # agent has picked a document it would only hide that document's tables
    if not dense_ids or (not allowed and dists[dense_ids[0]] > max_distance):
        return {"found": False, "query": query, "best_distance": round(dists[dense_ids[0]], 4) if dense_ids else None,
                "results": []}

    fused = Counter()
    sparse = _bm25().top(query, CANDIDATES * 10 if allowed else CANDIDATES)
    if allowed:
        sparse = [cid for cid in sparse if cid.split("-")[0] in allowed][:CANDIDATES]
    for ranking in (dense_ids, sparse):
        for rank, cid in enumerate(ranking):
            fused[cid] += 1 / (RRF_K + rank + 1)
    pool = col.get(ids=list(fused), include=["metadatas"])
    doc_of = {}
    for cid, meta in zip(pool["ids"], pool["metadatas"]):
        doc_of[cid] = meta["doc_id"]
        if meta.get("status") == "superseded":
            fused[cid] *= SUPERSEDED_WEIGHT
    top_ids, per_doc = [], Counter()
    for cid, _ in fused.most_common():
        if allowed or per_doc[doc_of[cid]] < MAX_PER_DOC:
            top_ids.append(cid)
            per_doc[doc_of[cid]] += 1
        if len(top_ids) == k:
            break

    got = col.get(ids=top_ids, include=["documents", "metadatas"])
    by_id = {i: (doc, meta) for i, doc, meta in zip(got["ids"], got["documents"], got["metadatas"])}
    hits = []
    for cid in top_ids:
        text, meta = by_id[cid]
        hits.append(
            {
                "text": text,
                "citation": _citation(meta),
                "doc_id": meta["doc_id"],
                "title": meta["title"],
                "page": meta["page"],
                "date": meta["date"],
                "status": meta.get("status", "current"),
                "distance": round(dists[cid], 4) if cid in dists else None,
            }
        )
    return {"found": True, "query": query, "best_distance": round(dists[dense_ids[0]], 4), "results": hits}
