"""GIS, map viewport, spatial proximity, and geocoding endpoints (API.md §8, PRD §8)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from tk_api.api.deps import DbSession
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.gis import geocoding as geocode_service
from tk_api.gis import service as gis_service
from tk_api.gis.schemas import (
    BoundingBoxQuery,
    GeocodeResponse,
    HeatmapPoint,
    MapInstitutionItem,
    MapReportItem,
    MapSummaryRead,
    TimelineResponse,
)

gis_router = APIRouter(prefix="/api/v1/gis", tags=["gis"])


async def gis_read_limiter(request: Request) -> None:
    await rate_limit(
        request, bucket="gis_read", key=f"ip:{client_ip(request)}", limit=60, window_seconds=60
    )


GisReadLimiter = Annotated[None, Depends(gis_read_limiter)]


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


def _validate_bbox(
    min_lon: float, min_lat: float, max_lon: float, max_lat: float
) -> BoundingBoxQuery:
    if min_lon > max_lon:
        raise ApiError("min_lon must be <= max_lon", 422, "invalid_bbox")
    if min_lat > max_lat:
        raise ApiError("min_lat must be <= max_lat", 422, "invalid_bbox")
    width = max_lon - min_lon
    height = max_lat - min_lat
    if width * height > 25.0:
        raise ApiError(
            f"bounding box area ({width * height:.2f} deg^2) exceeds maximum allowed (25.0 deg^2)",
            422,
            "invalid_bbox",
        )
    return BoundingBoxQuery(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)


# -----------------------------------------------------------------------------
# 1. Map Viewport Bounding-Box Endpoints (Phase 9)
# -----------------------------------------------------------------------------


@gis_router.get(
    "/map/institutions",
    response_model=list[MapInstitutionItem],
    summary="Institutions in map viewport bounding box",
    dependencies=[Depends(gis_read_limiter)],
)
async def map_institutions(
    session: DbSession,
    min_lon: Annotated[float, Query(ge=-180, le=180, description="West longitude")],
    min_lat: Annotated[float, Query(ge=-90, le=90, description="South latitude")],
    max_lon: Annotated[float, Query(ge=-180, le=180, description="East longitude")],
    max_lat: Annotated[float, Query(ge=-90, le=90, description="North latitude")],
    type_id: Annotated[uuid.UUID | None, Query(description="Filter by institution type ID")] = None,
    operational_status: Annotated[
        str | None, Query(description="Filter by operational status")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum items returned")] = 100,
) -> list[MapInstitutionItem]:
    """Retrieve institutions located inside the client map viewport."""
    bbox = _validate_bbox(min_lon, min_lat, max_lon, max_lat)
    return await gis_service.query_institutions_bbox(
        session,
        min_lon=bbox.min_lon,
        min_lat=bbox.min_lat,
        max_lon=bbox.max_lon,
        max_lat=bbox.max_lat,
        type_id=type_id,
        operational_status=operational_status,
        limit=limit,
    )


@gis_router.get(
    "/map/reports",
    response_model=list[MapReportItem],
    summary="Civic reports in map viewport bounding box",
    dependencies=[Depends(gis_read_limiter)],
)
async def map_reports(
    session: DbSession,
    min_lon: Annotated[float, Query(ge=-180, le=180, description="West longitude")],
    min_lat: Annotated[float, Query(ge=-90, le=90, description="South latitude")],
    max_lon: Annotated[float, Query(ge=-180, le=180, description="East longitude")],
    max_lat: Annotated[float, Query(ge=-90, le=90, description="North latitude")],
    category_slug: Annotated[str | None, Query(description="Filter by category slug")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    severity: Annotated[str | None, Query(description="Filter by severity")] = None,
    limit: Annotated[int, Query(ge=1, le=200, description="Maximum items returned")] = 100,
) -> list[MapReportItem]:
    """Retrieve public civic reports located inside the client map viewport."""
    bbox = _validate_bbox(min_lon, min_lat, max_lon, max_lat)
    return await gis_service.query_reports_bbox(
        session,
        min_lon=bbox.min_lon,
        min_lat=bbox.min_lat,
        max_lon=bbox.max_lon,
        max_lat=bbox.max_lat,
        category_slug=category_slug,
        status=status,
        severity=severity,
        limit=limit,
    )


# -----------------------------------------------------------------------------
# 2. Nearby Spatial Radius Search (Phase 9)
# -----------------------------------------------------------------------------


@gis_router.get(
    "/map/nearby",
    summary="Find institutions and reports within radius of coordinates",
    dependencies=[Depends(gis_read_limiter)],
)
async def map_nearby(
    session: DbSession,
    lat: Annotated[float, Query(ge=-90, le=90, description="Center latitude")],
    lng: Annotated[float, Query(ge=-180, le=180, description="Center longitude")],
    radius_m: Annotated[int, Query(ge=10, le=100000, description="Radius in metres")] = 5000,
    domain: Annotated[str, Query(description="Domain: all, institutions, reports")] = "all",
    category_slug: Annotated[str | None, Query(description="Filter by category slug")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum items returned")] = 50,
) -> dict[str, Any]:
    """Query nearby civic resources around a point using PostGIS distance."""
    return await gis_service.query_nearby(
        session,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        domain=domain,
        category_slug=category_slug,
        status=status,
        limit=limit,
    )


# -----------------------------------------------------------------------------
# 3. Map Summary & Geographic Aggregates (Phase 9)
# -----------------------------------------------------------------------------


@gis_router.get(
    "/map/summary",
    response_model=MapSummaryRead,
    summary="Civic intelligence summary for a geography node",
    dependencies=[Depends(gis_read_limiter)],
)
async def map_summary(
    session: DbSession,
    geography_id: Annotated[uuid.UUID | None, Query(description="Geography registry ID")] = None,
    boundary_id: Annotated[uuid.UUID | None, Query(description="GIS boundary ID")] = None,
) -> MapSummaryRead:
    """Retrieve aggregated civic statistics, severity breakdown, and data coverage."""
    return await gis_service.get_map_summary(
        session,
        geography_id=geography_id,
        boundary_id=boundary_id,
    )


# -----------------------------------------------------------------------------
# 4. Geocoding Abstraction (Phase 9)
# -----------------------------------------------------------------------------


@gis_router.get(
    "/geocode/forward",
    response_model=GeocodeResponse,
    summary="Forward geocode a place, institution, or coordinate",
    dependencies=[Depends(gis_read_limiter)],
)
async def forward_geocode(
    session: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=120, description="Query text or coordinates")],
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> GeocodeResponse:
    """Resolve text query or coordinates to structured location items."""
    return await geocode_service.forward_geocode(session, query=q, limit=limit)


# -----------------------------------------------------------------------------
# 5. Core Boundaries & Proximity Endpoints
# -----------------------------------------------------------------------------


@gis_router.get(
    "/boundaries",
    summary="Boundary tree (kind / parent / point filters)",
    dependencies=[Depends(gis_read_limiter)],
)
async def list_boundaries(
    session: DbSession,
    kind: str | None = None,
    parent_id: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any]:
    parsed_parent = (
        _parse_id(parent_id, kind="boundary", error_kind="invalid_boundary_id")
        if parent_id
        else None
    )
    return await gis_service.tree(session, kind=kind, parent_id=parsed_parent, lat=lat, lng=lng)


@gis_router.get(
    "/boundaries/{boundary_id}",
    summary="Boundary detail: GeoJSON + provenance",
    dependencies=[Depends(gis_read_limiter)],
)
async def boundary_detail(
    boundary_id: str,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(boundary_id, kind="boundary", error_kind="invalid_boundary_id")
    return await gis_service.boundary_detail(session, parsed)


@gis_router.get(
    "/reverse-geocode",
    summary="Address hint + boundary ids for a point",
    dependencies=[Depends(gis_read_limiter)],
)
async def reverse_geocode(
    session: DbSession,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
) -> dict[str, Any]:
    return await gis_service.reverse_geocode(session, lon=lng, lat=lat)


@gis_router.get(
    "/proximity",
    summary="Reports near a point (metres, geography cast)",
    dependencies=[Depends(gis_read_limiter)],
)
async def proximity(
    session: DbSession,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_m: int = Query(default=1000, ge=1, le=100_000),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    return await gis_service.proximity(session, lon=lng, lat=lat, radius_m=radius_m, limit=limit)


# -----------------------------------------------------------------------------
# 6. Heatmap Data Points (Phase 5 — Maps v2)
# -----------------------------------------------------------------------------


@gis_router.get(
    "/map/heatmap",
    response_model=list[HeatmapPoint],
    summary="Weighted density heatmap points for a viewport",
    dependencies=[Depends(gis_read_limiter)],
)
async def map_heatmap(
    session: DbSession,
    min_lon: Annotated[float, Query(ge=-180, le=180)],
    min_lat: Annotated[float, Query(ge=-90, le=90)],
    max_lon: Annotated[float, Query(ge=-180, le=180)],
    max_lat: Annotated[float, Query(ge=-90, le=90)],
    category_slug: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    severity: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
) -> list[HeatmapPoint]:
    """Return weighted points for client-side density heatmap rendering."""
    bbox = _validate_bbox(min_lon, min_lat, max_lon, max_lat)
    points = await gis_service.get_heatmap_points(
        session,
        min_lon=bbox.min_lon,
        min_lat=bbox.min_lat,
        max_lon=bbox.max_lon,
        max_lat=bbox.max_lat,
        category_slug=category_slug,
        status=status,
        severity=severity,
        limit=limit,
    )
    return [HeatmapPoint(**p) for p in points]


# -----------------------------------------------------------------------------
# 7. Timeline Data (Phase 5 — Maps v2)
# -----------------------------------------------------------------------------


@gis_router.get(
    "/map/timeline",
    response_model=TimelineResponse,
    summary="Time-series data for map timeline scrub",
    dependencies=[Depends(gis_read_limiter)],
)
async def map_timeline(
    session: DbSession,
    geography_id: Annotated[uuid.UUID | None, Query()] = None,
    category_slug: Annotated[str | None, Query()] = None,
    interval: Annotated[str, Query(pattern=r"^(day|week|month)$")] = "month",
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> TimelineResponse:
    """Return time-series data for timeline scrub on the map."""
    data = await gis_service.get_timeline_data(
        session,
        geography_id=geography_id,
        category_slug=category_slug,
        interval=interval,
        limit=limit,
    )
    return TimelineResponse(**data)
