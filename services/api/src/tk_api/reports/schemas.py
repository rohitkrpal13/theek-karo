"""Report, draft, evidence, verification, comment, and AI intake schemas (API.md §5, PRD §7-§14)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class GeoJsonPoint(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: list[float] = Field(min_length=2, max_length=3)


class DraftCreate(BaseModel):
    category_slug: str | None = None
    campaign_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    location: GeoJsonPoint | None = None
    location_accuracy_m: float | None = Field(default=None, gt=0, le=10000)
    coordinate_source: str | None = None
    observed_at: datetime | None = None
    address_hint: str | None = Field(default=None, max_length=500)
    severity: Literal["low", "medium", "high", "critical"] | None = None
    visibility: Literal["public", "private", "unlisted"] = "public"
    fields: dict[str, Any] = Field(default_factory=dict)


class DraftUpdate(BaseModel):
    category_slug: str | None = None
    institution_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=300)
    description: str | None = Field(default=None, max_length=8000)
    location: GeoJsonPoint | None = None
    location_accuracy_m: float | None = Field(default=None, gt=0, le=10000)
    coordinate_source: str | None = None
    observed_at: datetime | None = None
    address_hint: str | None = Field(default=None, max_length=500)
    severity: Literal["low", "medium", "high", "critical"] | None = None
    visibility: Literal["public", "private", "unlisted"] | None = None
    fields: dict[str, Any] | None = None


class DraftSubmitRequest(BaseModel):
    category_slug: str | None = None
    institution_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    title: str | None = None
    description: str | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    fields: dict[str, Any] | None = None


class ReportCreate(BaseModel):
    category_slug: str
    campaign_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    title: str = Field(min_length=5, max_length=300)
    description: str = Field(min_length=10, max_length=8000)
    location: GeoJsonPoint
    location_accuracy_m: float = Field(default=15.0, gt=0, le=10000)
    coordinate_source: str | None = None
    observed_at: datetime | None = None
    address_hint: str | None = Field(default=None, max_length=500)
    severity: Literal["low", "medium", "high", "critical"] | None = "medium"
    visibility: Literal["public", "private", "unlisted"] = "public"
    source: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    media_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_coords(self) -> ReportCreate:
        lon, lat = self.location.coordinates[0], self.location.coordinates[1]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("coordinates out of range (lon -180..180, lat -90..90)")
        return self


class ReportFieldsUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=300)
    description: str | None = Field(default=None, min_length=10, max_length=8000)
    address_hint: str | None = Field(default=None, max_length=500)
    institution_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    visibility: Literal["public", "private", "unlisted"] | None = None
    observed_at: datetime | None = None
    fields: dict[str, Any] | None = None


class VerificationCreate(BaseModel):
    kind: Literal["confirm", "refute", "needs_information"]
    evidence: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)
    location_independent: bool = False


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    parent_id: str | None = None
    mentions: list[str] | None = Field(
        default=None, description="Usernames to notify (Phase 13)", max_length=10
    )


class TransitionRequest(BaseModel):
    to_status: str
    reason: str | None = Field(default=None, max_length=2000)


class FollowRequest(BaseModel):
    notify_level: Literal["all", "status_only", "none"] = "all"


class ReportEvidenceUploadRequest(BaseModel):
    mime_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0, le=100 * 1024 * 1024)
    kind: Literal["image", "video", "document"] = "image"


class ReportEvidenceCompleteRequest(BaseModel):
    media_id: uuid.UUID
    checksum_sha256: str | None = None


class ReportEvidenceRead(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    kind: str
    media_object_id: uuid.UUID | None = None
    url: str | None = None
    thumbnail_url: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    moderation_status: str
    verification_status: str
    created_at: str


class DuplicateCandidateRead(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    candidate_report_id: uuid.UUID
    candidate_ticket_no: str
    candidate_title: str
    similarity_score: float
    confidence: str
    status: str
    suggested_by: str


class DuplicateLinkRequest(BaseModel):
    candidate_report_id: uuid.UUID
    status: Literal["possible", "confirmed", "rejected"] = "confirmed"


class AiIntakeSuggestRequest(BaseModel):
    description: str = Field(min_length=5, max_length=8000)
    title: str | None = None
    category_slug: str | None = None
    location: GeoJsonPoint | None = None


class AiIntakeSuggestResponse(BaseModel):
    category_suggestion: str | None = None
    issue_type_suggestion: str | None = None
    title_suggestion: str | None = None
    severity_suggestion: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = 0.8
    model_id: str = "gemini-2.5-flash"


class ReportStatusHistoryRead(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    from_status: str | None = None
    to_status: str
    actor_id: uuid.UUID | None = None
    reason: str | None = None
    created_at: str


class ReportRead(BaseModel):
    id: uuid.UUID
    ticket_no: str
    category_id: uuid.UUID
    category_slug: str | None = None
    campaign_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    reporter_id: uuid.UUID
    reporter_display: str | None = None
    title: str
    description: str
    location: dict[str, Any]
    location_accuracy_m: float
    coordinate_source: str | None = None
    observed_at: str | None = None
    address_hint: str | None = None
    status: str
    severity: str | None = None
    visibility: str = "public"
    info_class: str
    trust_score: float
    duplicate_of: uuid.UUID | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    evidence: list[ReportEvidenceRead] = Field(default_factory=list)
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class ReportDetailRead(ReportRead):
    timeline: list[ReportStatusHistoryRead] = Field(default_factory=list)
    verifications_count: int = 0
    confirmations_count: int = 0
    refutations_count: int = 0
