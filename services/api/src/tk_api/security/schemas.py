"""Security API schemas (Phase 28)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Incident Schemas
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    severity: str = Field("medium", pattern="^(low|medium|high|critical)$")
    category: str = Field("other")
    affected_components: list[str] | None = None
    impact_description: str | None = None


class IncidentUpdate(BaseModel):
    status: str | None = Field(
        None, pattern="^(detected|investigating|contained|eradicated|recovered|closed)$"
    )
    assigned_to: uuid.UUID | None = None
    containment_actions: str | None = None
    resolution: str | None = None


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    severity: str
    category: str
    status: str
    detected_at: datetime
    assigned_to: uuid.UUID | None = None
    affected_components: list[str] | None = None
    impact_description: str | None = None
    containment_actions: str | None = None
    resolution: str | None = None
    closed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Abuse Score Schemas
# ---------------------------------------------------------------------------


class AbuseScoreResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    ip_address: str | None = None
    abuse_type: str
    score: float
    evidence: dict[str, Any] | None = None
    action_taken: str | None = None
    created_at: datetime
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# IP Block Schemas
# ---------------------------------------------------------------------------


class IPBlockCreate(BaseModel):
    ip_address: str = Field(..., min_length=1, max_length=45)
    reason: str = Field(..., pattern="^(brute_force|scraping|api_abuse|malicious_requests|manual)$")
    description: str | None = None
    duration_hours: int = Field(24, ge=1, le=720)  # 1 hour to 30 days


class IPBlockResponse(BaseModel):
    id: uuid.UUID
    ip_address: str
    reason: str
    description: str | None = None
    blocked_by: uuid.UUID | None = None
    blocked_at: datetime
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Security Audit Schemas
# ---------------------------------------------------------------------------


class SecurityAuditEntryResponse(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    result: str
    risk_level: str
    ip_address: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SecuritySummaryResponse(BaseModel):
    period_hours: int
    risk_level_counts: dict[str, int]
    denied_actions: int
    active_incidents: int


# ---------------------------------------------------------------------------
# Security Policy Schemas
# ---------------------------------------------------------------------------


class SecurityPolicyResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    config: dict[str, Any]
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Data Classification Schemas
# ---------------------------------------------------------------------------


class DataClassificationResponse(BaseModel):
    entity_type: str
    classification: str
    can_access: bool | None = None


# ---------------------------------------------------------------------------
# Security Health Schemas
# ---------------------------------------------------------------------------


class SecurityHealthResponse(BaseModel):
    status: str
    checks: dict[str, str]
    last_incident: datetime | None = None
    active_blocks: int = 0
    recent_deny_count: int = 0


# ---------------------------------------------------------------------------
# Input Validation Schemas
# ---------------------------------------------------------------------------


class InputValidationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000)


class InputValidationResponse(BaseModel):
    is_safe: bool
    findings: list[str]
    recommendation: str
