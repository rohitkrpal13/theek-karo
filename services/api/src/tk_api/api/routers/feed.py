"""Phase 13 public feed endpoints (API.md §10, PRD §8).

The feed is explainable by design: every ranked item carries a
``score_explanation`` (recency, relevance, follow, verification, engagement)
and human-readable ``reasons``. Engagement is capped so it can never outweigh
freshness — the platform does not optimize for outrage.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from tk_api.api.deps import CurrentUser, DbSession, require_active
from tk_api.community import service as community_service
from tk_api.community.schemas import FEED_TABS
from tk_api.core.errors import ApiError

feed_router = APIRouter(prefix="/api/v1/feed", tags=["feed"])

ActiveUser = Annotated[Any, Depends(require_active())]


@feed_router.get("", summary="Public feed (for_you | following | trending | latest | geography)")
async def get_feed(
    request: Request,
    user: CurrentUser,
    session: DbSession,
    tab: str = Query(default="for_you"),
    boundary_id: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=50),
) -> dict[str, Any]:
    if tab not in FEED_TABS:
        raise ApiError(f"tab must be one of {FEED_TABS}", 422, "invalid_feed_tab")
    boundary: Any = None
    if boundary_id is not None:
        try:
            import uuid

            boundary = uuid.UUID(boundary_id)
        except ValueError as exc:
            raise ApiError("invalid boundary_id", 422, "invalid_boundary_id") from exc
    storage = getattr(request.app.state, "storage", None)
    return await community_service.list_feed(
        session,
        viewer=user,
        tab=tab,
        boundary_id=boundary,
        cursor=cursor,
        limit=limit,
        storage=storage,
    )
