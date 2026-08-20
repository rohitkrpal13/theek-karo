"""Pydantic schemas for GIS, spatial viewport queries, and map summary (PRD §8, API.md §8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GeoJsonPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(
        ..., min_length=2, max_length=2, description="[longitude, latitude] in WGS84"
    )

    @model_validator(mode="after")
    def validate_coords(self) -> GeoJsonPoint:
        lon, lat = self.coordinates[0], self.coordinates[1]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"coordinates [{lon}, {lat}] out of WGS84 range")
        return self


class BoundingBoxQuery(BaseModel):
    min_lon: float = Field(..., ge=-180, le=180)
    min_lat: float = Field(..., ge=-90, le=90)
    max_lon: float = Field(..., ge=-180, le=180)
    max_lat: float = Field(..., ge=-90, le=90)


class MapNearbyQuery(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    radius_m: int = Field(default=5000, ge=10, le=100000)
    domain: Literal["all", "institutions", "reports"] = "all"
    category_slug: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class MapInstitutionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type_id: uuid.UUID
    type_code: str | None = None
    type_name: str | None = None
    location: dict[str, Any]
    operational_status: str
    geography_id: uuid.UUID | None = None
    open_reports_count: int = 0
    resolved_reports_count: int = 0


class MapReportItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_no: str
    title: str
    category_id: uuid.UUID
    category_slug: str | None = None
    institution_id: uuid.UUID | None = None
    location: dict[str, Any]
    status: str
    severity: str
    trust_score: float
    coordinate_source: str | None = None
    observed_at: datetime | None = None
    created_at: datetime


class MapSummaryRead(BaseModel):
    geography_id: uuid.UUID | None = None
    geography_name: str | None = None
    hierarchy_path: str | None = None
    boundary_id: uuid.UUID | None = None
    boundary_name: str | None = None
    institution_count: int = 0
    report_count: int = 0
    open_report_count: int = 0
    resolved_report_count: int = 0
    verified_report_count: int = 0
    category_breakdown: dict[str, int] = Field(default_factory=dict)
    severity_breakdown: dict[str, int] = Field(default_factory=dict)
    status_breakdown: dict[str, int] = Field(default_factory=dict)
    data_coverage_pct: float = 100.0


class GeocodeResultItem(BaseModel):
    label: str
    kind: str  # "geography", "institution", "landmark", "coordinate"
    lat: float
    lng: float
    id: str | None = None
    hierarchy_hint: str | None = None
    confidence: float = 1.0


class GeocodeResponse(BaseModel):
    query: str
    results: list[GeocodeResultItem] = Field(default_factory=list)


class HeatmapPoint(BaseModel):
    lon: float
    lat: float
    weight: float = 1.0
    severity: str | None = None
    category: str | None = None


class TimelinePeriod(BaseModel):
    period: str
    total: int = 0
    open: int = 0
    resolved: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class TimelineResponse(BaseModel):
    interval: str
    periods: list[TimelinePeriod] = Field(default_factory=list)
    total_reports: int = 0
