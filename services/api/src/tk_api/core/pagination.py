"""Reusable pagination models and query builders (API.md §1).

Supports:
- Page-based pagination (page, limit, total, total_pages)
- Cursor-based pagination (opaque encoded cursors for scalable feeds)
"""

from __future__ import annotations

import base64
import math
from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class CursorParams(BaseModel):
    cursor: str | None = Field(
        default=None, description="Opaque cursor string from previous response"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Items to fetch (max 100)")


class PageResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int

    @classmethod
    def create(cls, items: Sequence[T], total: int, params: PageParams) -> PageResponse[T]:
        pages = math.ceil(total / params.limit) if params.limit > 0 else 1
        return cls(
            items=list(items),
            total=total,
            page=params.page,
            limit=params.limit,
            pages=pages,
        )


class CursorResponse[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
    limit: int
    has_more: bool = False


def encode_cursor(value: str) -> str:
    """Encode an arbitrary string value into a base64 URL-safe cursor."""
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8").rstrip("=")


def decode_cursor(cursor: str) -> str:
    """Decode a base64 URL-safe cursor into string."""
    padded = cursor + "=" * (-len(cursor) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
