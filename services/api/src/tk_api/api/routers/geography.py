"""Geography registry API endpoints (API.md §6, PRD §3)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from tk_api.api.deps import DbSession
from tk_api.core.pagination import PageParams, PageResponse
from tk_api.geography import service as geo_service
from tk_api.geography.schemas import (
    GeographyDetailRead,
    GeographyRead,
    GeographyTypeRead,
)

geography_router = APIRouter(prefix="/api/v1/geography", tags=["geography"])


@geography_router.get("/types", response_model=list[GeographyTypeRead])
async def list_types(session: DbSession) -> list[GeographyTypeRead]:
    """List all supported geographic hierarchy types."""
    return await geo_service.list_geography_types(session)


@geography_router.get("", response_model=PageResponse[GeographyRead])
async def list_geographies(
    session: DbSession,
    type_id: Annotated[uuid.UUID | None, Query(description="Filter by geography type ID")] = None,
    parent_id: Annotated[
        uuid.UUID | None, Query(description="Filter by parent geography ID")
    ] = None,
    country_code: Annotated[str | None, Query(description="Filter by ISO country code")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> PageResponse[GeographyRead]:
    """Browse geographies with filtering and pagination."""
    params = PageParams(page=page, limit=limit)
    return await geo_service.list_geographies(
        session,
        type_id=type_id,
        parent_id=parent_id,
        country_code=country_code,
        params=params,
    )


@geography_router.get("/search", response_model=list[GeographyRead])
async def search_geographies(
    session: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=100, description="Search term")],
    type_id: Annotated[uuid.UUID | None, Query(description="Filter by geography type ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[GeographyRead]:
    """Search geographies by normalized name."""
    return await geo_service.search_geographies(session, query=q, type_id=type_id, limit=limit)


@geography_router.get("/{geo_id}", response_model=GeographyDetailRead)
async def get_geography_detail(
    geo_id: uuid.UUID,
    session: DbSession,
) -> GeographyDetailRead:
    """Retrieve detailed geography info with translations and parent."""
    return await geo_service.get_geography_detail(session, geo_id=geo_id)


@geography_router.get("/{geo_id}/children", response_model=list[GeographyRead])
async def get_geography_children(
    geo_id: uuid.UUID,
    session: DbSession,
) -> list[GeographyRead]:
    """List immediate children nodes in the hierarchy."""
    return await geo_service.get_children(session, geo_id=geo_id)


@geography_router.get("/{geo_id}/ancestors", response_model=list[GeographyRead])
async def get_geography_ancestors(
    geo_id: uuid.UUID,
    session: DbSession,
) -> list[GeographyRead]:
    """List all ancestor nodes from parent up to country root."""
    return await geo_service.get_ancestors(session, geo_id=geo_id)
