"""Cross-dialect text similarity for duplicate matching (ADR-030).

MVP uses a Jaccard overlap on word bigrams computed in Python so every
environment (SQLite unit tests, Postgres live) behaves identically. The
documented scale-up replaces this scorer with Postgres pg_trgm similarity or
pgvector cosine over ``report_embeddings`` (DATABASE.md §3.6) without touching
the review-queue contract.
"""

from __future__ import annotations

import re
from functools import lru_cache
from itertools import pairwise

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_'-]*")


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(pairwise(tokens)) | {(t, "·") for t in tokens}


def _grams(text: str) -> set[tuple[str, str]]:
    return _bigrams(_tokens(text))


@lru_cache(maxsize=4096)
def _cached_grams(text: str) -> frozenset[tuple[str, str]]:
    return frozenset(_grams(text))


def similarity(a: str, b: str) -> float:
    """Jaccard(grams(a), grams(b)); 1.0 for identical text, 0.0 for disjoint."""
    ga = _cached_grams(a)
    gb = _cached_grams(b)
    if not ga and not gb:
        return 1.0
    union = ga | gb
    if not union:
        return 0.0
    return len(ga & gb) / len(union)
