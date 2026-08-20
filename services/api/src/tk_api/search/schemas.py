"""Search schemas (API.md §10, PRD §8)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

SearchDomain = Literal["all", "reports", "institutions", "geography", "categories"]


class SearchResultItem(BaseModel):
    id: uuid.UUID
    domain: str
    title: str
    subtitle: str | None = None
    snippet: str | None = None
    score: float = 1.0
    meta: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    total: int
    items: list[SearchResultItem]
