"""Filtering and safe sorting utilities for SQLAlchemy queries.

Guards against SQL injection via dynamic sort fields by enforcing strict allowlists.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, asc, desc

from tk_api.core.errors import ApiError


class FilterError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status=422, kind="invalid_query_parameter")


def apply_sort(
    query: Any,
    sort_by: str | None,
    sort_dir: str | None,
    allowed_fields: dict[str, ColumnElement[Any]],
    default_column: ColumnElement[Any],
    default_dir: str = "desc",
) -> Any:
    """Apply safe sorting to a SQLAlchemy select statement based on an allowlist."""
    direction = (sort_dir or default_dir).lower()
    if direction not in ("asc", "desc"):
        raise FilterError(f"invalid sort_dir '{sort_dir}': must be 'asc' or 'desc'")

    if sort_by is None:
        return query.order_by(desc(default_column) if direction == "desc" else asc(default_column))

    col = allowed_fields.get(sort_by.lower())
    if col is None:
        valid_keys = ", ".join(sorted(allowed_fields.keys()))
        raise FilterError(f"invalid sort_by field '{sort_by}'; allowed: {valid_keys}")

    return query.order_by(desc(col) if direction == "desc" else asc(col))
