"""Pydantic schemas for the government workflow API (Phase 25)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RoutingRuleCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    description: str | None = None
    category_id: uuid.UUID | None = None
    issue_type_id: uuid.UUID | None = None
    geography_id: uuid.UUID | None = None
    institution_type_id: uuid.UUID | None = None
    target_department_id: uuid.UUID
    secondary_department_ids: list[uuid.UUID] = Field(default_factory=list)
    priority_order: int = 100


class CaseRouteCreate(BaseModel):
    case_id: uuid.UUID
    recommended_department_id: uuid.UUID
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str | None = None
    routing_source: str = Field(
        default="rule_based", pattern="^(rule_based|ai_recommended|manual)$"
    )


class CaseRouteAccept(BaseModel):
    accepted: bool
    rejection_reason: str | None = None


class CaseHandoffCreate(BaseModel):
    case_id: uuid.UUID
    to_department_id: uuid.UUID
    reason: str = Field(min_length=1)


class CaseHandoffResponse(BaseModel):
    accepted: bool
    rejection_reason: str | None = None


class OfficialResponseCreate(BaseModel):
    case_id: uuid.UUID
    summary: str = Field(min_length=1)
    action_taken: str | None = None
    current_status: str | None = None
    next_step: str | None = None
    estimated_completion: datetime | None = None
    external_reference_id: str | None = None


class OfficialResponseUpdate(BaseModel):
    summary: str | None = None
    action_taken: str | None = None
    current_status: str | None = None
    next_step: str | None = None
    estimated_completion: datetime | None = None
    change_reason: str | None = None


class OfficialResponseWithdraw(BaseModel):
    reason: str = Field(min_length=1)


class WorkflowDefinitionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    description: str | None = None
    category_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    states: list[str] = Field(default_factory=list)
    transitions: dict[str, Any] = Field(default_factory=dict)
    required_roles: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class GovernmentIntegrationCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    provider_type: str = Field(min_length=1, max_length=32)
    endpoint_url: str | None = None
    department_id: uuid.UUID | None = None
    auth_type: str = Field(default="none")
    capabilities: list[str] = Field(default_factory=list)
    status_mapping: dict[str, Any] = Field(default_factory=dict)


class GovernmentIntegrationUpdate(BaseModel):
    name: str | None = None
    endpoint_url: str | None = None
    status: str | None = Field(default=None, pattern="^(active|inactive|degraded|error)$")
    capabilities: list[str] | None = None
    status_mapping: dict[str, Any] | None = None


class ExternalReferenceCreate(BaseModel):
    case_id: uuid.UUID
    integration_id: uuid.UUID
    external_reference_id: str = Field(min_length=1)
    external_status: str | None = None


class WorkflowTransitionRequest(BaseModel):
    to_state: str = Field(min_length=1)
    reason: str | None = None


class CaseBulkAssign(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
    department_id: uuid.UUID
    reason: str | None = None


class CaseBulkRoute(BaseModel):
    filters: dict[str, Any] = Field(default_factory=dict)
    department_id: uuid.UUID
    reason: str | None = None


class GovDashboardQuery(BaseModel):
    department_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
