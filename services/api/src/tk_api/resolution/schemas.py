"""Pydantic schemas for the resolution workflow API (Phase 14)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResolutionEvidenceItem(BaseModel):
    kind: str = Field(default="after", pattern="^(before|after|document|other)$")
    media_object_id: uuid.UUID | None = None
    notes: str | None = None
    document_kind: str | None = None
    before_after: str | None = Field(default=None, pattern="^(before|after|neutral)$")
    captured_at: datetime | None = None
    checksum: str | None = None
    visibility: str = Field(default="public", pattern="^(public|internal)$")


class ResolutionSubmitRequest(BaseModel):
    case_id: uuid.UUID
    notes: str | None = None
    responsible_party: str | None = None
    explanation: str | None = None
    resolution_date: datetime | None = None
    reference_numbers: dict[str, Any] | None = None
    evidence: list[ResolutionEvidenceItem] = Field(min_length=1)


class ResolutionReviewRequest(BaseModel):
    decision: str = Field(pattern="^(verified|more_evidence_required|rejected|partially_verified)$")
    reason: str | None = None
    ai_assessment: dict[str, Any] | None = None


class ResolutionEvidenceAddRequest(BaseModel):
    items: list[ResolutionEvidenceItem] = Field(min_length=1)


class ResolutionFollowupCreate(BaseModel):
    """One citizen signal on a verified resolution (Phase 15, PRD §B.2)."""

    signal: str = Field(pattern="^(observed_improvement|issue_still_exists)$")
    observation: str | None = Field(default=None, max_length=1000)


class ReopenSignalReviewRequest(BaseModel):
    """Human decision on an aggregate "issue still exists" signal."""

    decision: str = Field(pattern="^(approved|dismissed)$")
    note: str | None = Field(default=None, max_length=1000)
