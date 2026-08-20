"""Pydantic schemas for the civic case API (Phase 14)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CaseCreateRequest(BaseModel):
    report_id: uuid.UUID
    department_id: uuid.UUID | None = None
    severity: str | None = Field(default=None, pattern="^(low|medium|high|critical)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


class CaseTransitionRequest(BaseModel):
    to_status: str = Field(min_length=1)
    reason: str | None = None


class CaseAssignRequest(BaseModel):
    department_id: uuid.UUID
    assignee_user_id: uuid.UUID | None = None
    geography_id: uuid.UUID | None = None
    reason: str | None = None


class CaseResponseCreate(BaseModel):
    kind: str = Field(pattern="^(acknowledgement|public_response|internal_note|progress_update)$")
    visibility: str = Field(default="public", pattern="^(public|internal)$")
    body: str = Field(min_length=1)


class CaseActionCreate(BaseModel):
    title: str = Field(min_length=1)
    description: str | None = None
    responsible_team: str | None = None
    target_date: datetime | None = None


class CaseActionUpdate(BaseModel):
    status: str | None = Field(
        default=None, pattern="^(planned|in_progress|completed|cancelled|blocked)$"
    )
    notes: str | None = None


class CaseReopenRequestCreate(BaseModel):
    reason: str = Field(min_length=1)
    evidence: str | None = None


class CaseReopenReview(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    note: str | None = None


class SlaPauseRequest(BaseModel):
    reason: str = Field(min_length=1)
    expected_resume_condition: str | None = None


class CaseEscalateRequest(BaseModel):
    level: int = Field(ge=1, le=5)
    reason: str = Field(min_length=1)
