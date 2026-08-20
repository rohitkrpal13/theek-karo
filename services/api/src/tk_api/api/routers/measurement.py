"""Measurement endpoints (API.md §10)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter

from tk_api.api.deps import DbSession
from tk_api.core.errors import ApiError
from tk_api.measurement import service as measurement_service

measurement_router = APIRouter(prefix="/api/v1/measurement", tags=["measurement"])


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


@measurement_router.get("/overview", summary="Category/campaign aggregates (live)")
async def overview(session: DbSession) -> dict[str, Any]:
    return await measurement_service.overview(session)


@measurement_router.get("/campaign/{campaign_id}", summary="Campaign trend snapshots")
async def campaign_trend(campaign_id: str, session: DbSession) -> dict[str, Any]:
    parsed = _parse_id(campaign_id, kind="campaign", error_kind="invalid_campaign_id")
    return await measurement_service.campaign_trend(session, parsed)
