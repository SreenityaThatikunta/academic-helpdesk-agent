"""Cached access to the structured CSVs in data/csv/."""

import re
from functools import lru_cache

import pandas as pd

from helpdesk import config

CODE_RE = re.compile(r"\b([A-Za-z]{2,4})\s?-?(\d{3,5}[A-Za-z]?)\b")


@lru_cache(maxsize=None)
def table(name: str) -> pd.DataFrame:
    return pd.read_csv(config.CSV_DIR / f"{name}.csv", dtype=str).fillna("")


def normalize_code(text: str) -> str | None:
    """'csl 7650' / 'CSL-7650' / 'CSL7650' -> 'CSL7650'; None if no code-like token."""
    m = CODE_RE.search(text or "")
    return f"{m.group(1)}{m.group(2)}".upper() if m else None


def source_of(df: pd.DataFrame) -> list[str]:
    return sorted(set(df["source"])) if "source" in df and len(df) else []
