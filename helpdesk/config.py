"""Environment-driven settings for the helpdesk."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _path(var: str, default: str) -> Path:
    p = Path(os.getenv(var, default))
    return p if p.is_absolute() else ROOT / p


MODEL = os.getenv("HELPDESK_MODEL", "ollama_chat/qwen3:8b")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

DOCS_DIR = _path("DOCS_DIR", "data/docs")
CSV_DIR = _path("CSV_DIR", "data/csv")
CHROMA_DIR = _path("CHROMA_DIR", "chroma_db")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "academic_docs")
UNANSWERED_LOG = _path("UNANSWERED_LOG", "logs/unanswered.jsonl")
DRAFTS_DIR = _path("DRAFTS_DIR", "drafts")

TOP_K = int(os.getenv("TOP_K", "5"))
MAX_DISTANCE = float(os.getenv("MAX_DISTANCE", "0.55"))

# LiteLLM reads this to reach Ollama
os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_API_BASE)
