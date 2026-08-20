"""Government workflow models (Phase 25).

Extends the existing department/case/SLA architecture with:
- Routing rules (category/geography → department mapping)
- Case routing records (recommended + accepted departments)
- Case handoffs (department-to-department transfers)
- Official responses (versioned, with source tracking)
- Workflow definitions (configurable state machines per category)
- Government integration adapter
- Sync runs (external system synchronization tracking)

Design invariants:
- Every official action comes from verified authorized representatives.
- Theek Karo never impersonates government departments.
- Routing recommendations require human/system validation.
- Handoffs are never silent — both departments must acknowledge.
- Official responses are versioned, never silently overwritten.
- External system statuses are mapped explicitly, never assumed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------


class RoutingRule(Base):
    """Data-driven mapping: category + geography + institution type → department.

    Rules are configuration, never hard-coded per department. The most specific
    rule wins (department + category + geography beats a category-only rule).
    """

    __tablename__ = "routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("categories.id", ondelete="SET NULL")
    )
    issue_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("issue_types.id", ondelete="SET NULL")
    )
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("geographies.id", ondelete="SET NULL")
    )
    institution_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("institution_types.id", ondelete="SET NULL")
    )
    target_department_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    secondary_department_ids: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    priority_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Case Routes (routing decisions)
# ---------------------------------------------------------------------------


class CaseRoute(Base):
    """Records a routing decision for a case: recommended department, confidence,
    reason, and whether the routing was accepted.

    Every routing decision is audited. AI recommendations are clearly marked
    as recommendations — human validation required before official routing.
    """

    __tablename__ = "case_routes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    routing_rule_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routing_rules.id", ondelete="SET NULL")
    )
    recommended_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT")
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    reason: Mapped[str | None] = mapped_column(Text)
    routing_source: Mapped[str] = mapped_column(
        String(16), default="rule_based"
    )  # rule_based | ai_recommended | manual
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "routing_source IN ('rule_based', 'ai_recommended', 'manual')",
            name="ck_case_routes_source",
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_case_routes_confidence",
        ),
    )


# ---------------------------------------------------------------------------
# Case Handoffs
# ---------------------------------------------------------------------------


class CaseHandoff(Base):
    """Department-to-department transfer. Both departments must participate:
    from_department initiates, to_department accepts/rejects.

    Never silently move ownership.
    """

    __tablename__ = "case_handoffs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    from_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT")
    )
    to_department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    initiated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_case_handoffs_status",
        ),
    )


# ---------------------------------------------------------------------------
# Official Responses (versioned)
# ---------------------------------------------------------------------------


class OfficialResponse(Base):
    """An official response from a department representative.

    Official responses are versioned — edits create new versions, never
    silently overwrite. Each version preserves the original with timestamp,
    author, and change reason.
    """

    __tablename__ = "official_responses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT")
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text)
    current_status: Mapped[str | None] = mapped_column(Text)
    next_step: Mapped[str | None] = mapped_column(Text)
    estimated_completion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_reference_id: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="platform")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("official_responses.id", ondelete="SET NULL")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_reason: Mapped[str | None] = mapped_column(Text)
    withdrawn: Mapped[bool] = mapped_column(Boolean, default=False)
    withdrawn_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "source IN ('platform', 'external_api', 'imported')",
            name="ck_official_responses_source",
        ),
    )


# ---------------------------------------------------------------------------
# Workflow Definitions (configurable state machines)
# ---------------------------------------------------------------------------


class WorkflowDefinition(Base):
    """Configurable workflow per category/department. Different categories can
    use different workflows. The state transitions are validated at runtime.

    Avoids hard-coded state transitions throughout the application.
    """

    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    states: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    transitions: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    required_roles: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class WorkflowTransition(Base):
    """Audit trail for workflow state transitions. Every transition must verify
    current state, role, permission, jurisdiction, and required data.
    """

    __tablename__ = "workflow_transitions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_definitions.id", ondelete="SET NULL")
    )
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_workflow_transitions_case", "case_id", "created_at"),)


# ---------------------------------------------------------------------------
# Government Integration Adapter
# ---------------------------------------------------------------------------


class GovernmentIntegration(Base):
    """Abstraction for external government system integrations.

    Capabilities: submit case, get case status, retrieve reference,
    retrieve response, synchronize status. Only implemented for APIs
    that actually exist and are authorized.

    Uses adapter pattern: GovernmentIntegrationProvider
     ├── ProviderA
     ├── ProviderB
     └── FutureProvider
    """

    __tablename__ = "government_integrations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    provider_type: Mapped[str] = mapped_column(String(32))
    endpoint_url: Mapped[str | None] = mapped_column(Text)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="inactive")
    auth_type: Mapped[str] = mapped_column(String(32), default="none")
    config: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    capabilities: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(16))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    status_mapping: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'degraded', 'error')",
            name="ck_gov_integrations_status",
        ),
        CheckConstraint(
            "auth_type IN ('none', 'api_key', 'oauth2', 'jwt', 'service_account')",
            name="ck_gov_integrations_auth_type",
        ),
    )


# ---------------------------------------------------------------------------
# External Case References
# ---------------------------------------------------------------------------


class ExternalCaseReference(Base):
    """Maps a Theek Karo case to an external government system reference.

    Stores: external_reference_id, source, status mapping, last sync.
    Never invents official reference numbers.
    """

    __tablename__ = "external_case_references"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cases.id", ondelete="CASCADE"), index=True
    )
    integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("government_integrations.id", ondelete="RESTRICT"), index=True
    )
    external_reference_id: Mapped[str] = mapped_column(Text)
    external_status: Mapped[str | None] = mapped_column(String(32))
    mapped_status: Mapped[str | None] = mapped_column(String(32))
    external_data: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submission_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "submission_status IN ('pending', 'submitted', 'synced', 'failed', 'conflict')",
            name="ck_external_refs_submission_status",
        ),
        UniqueConstraint("case_id", "integration_id", name="uq_external_case_ref_once"),
    )


# ---------------------------------------------------------------------------
# Sync Runs
# ---------------------------------------------------------------------------


class SyncRun(Base):
    """Tracks external system synchronization jobs: what happened, when,
    how many records, errors. Never trust HTTP 200 = case resolved.
    """

    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("government_integrations.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(8))  # outbound | inbound
    status: Mapped[str] = mapped_column(String(16), default="running")
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    external_version: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "direction IN ('outbound', 'inbound')",
            name="ck_sync_runs_direction",
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'partial')",
            name="ck_sync_runs_status",
        ),
    )


# ---------------------------------------------------------------------------
# Bulk Operation Audit
# ---------------------------------------------------------------------------


class BulkOperationLog(Base):
    """Audit log for bulk operations: user, operation, count, filters, timestamp."""

    __tablename__ = "bulk_operation_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    operation: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    filters: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    result_summary: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
