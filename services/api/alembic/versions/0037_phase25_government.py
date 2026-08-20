"""Phase 25 — Government & Department Workflow tables.

Revision ID: 0037_phase25_gov
Revises: 0036_phase24_identity
Create Date: 2026-08-18

Tables created:
- routing_rules
- case_routes
- case_handoffs
- official_responses
- workflow_definitions
- workflow_transitions
- government_integrations
- external_case_references
- sync_runs
- bulk_operation_logs
"""

from __future__ import annotations

import uuid as _uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0037_phase25_gov"
down_revision: str | None = "0036_phase24_identity"
branch_labels: str | None = None
depends_on: str | None = None


def _utcnow() -> sa.sql.elements.GenericFunction:
    return sa.func.now()


def upgrade() -> None:
    op.create_table(
        "routing_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column(
            "issue_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("issue_types.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "geography_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geographies.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "institution_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("institution_types.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "target_department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("secondary_department_ids", JSONB(), server_default="[]"),
        sa.Column("priority_order", sa.Integer(), server_default="100"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
    )

    op.create_table(
        "case_routes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "routing_rule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("routing_rules.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "recommended_department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Numeric(5, 4),
            server_default="0.0",
        ),
        sa.Column("reason", sa.Text()),
        sa.Column(
            "routing_source",
            sa.String(16),
            server_default="rule_based",
        ),
        sa.Column("accepted", sa.Boolean(), server_default="false"),
        sa.Column(
            "accepted_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.CheckConstraint(
            "routing_source IN ('rule_based', 'ai_recommended', 'manual')",
            name="ck_case_routes_source",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_case_routes_confidence",
        ),
    )

    op.create_table(
        "case_handoffs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "from_department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "to_department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "initiated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default="pending",
        ),
        sa.Column(
            "accepted_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'cancelled')",
            name="ck_case_handoffs_status",
        ),
    )

    op.create_table(
        "official_responses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("action_taken", sa.Text()),
        sa.Column("current_status", sa.Text()),
        sa.Column("next_step", sa.Text()),
        sa.Column("estimated_completion", sa.DateTime(timezone=True)),
        sa.Column("external_reference_id", sa.Text()),
        sa.Column(
            "source",
            sa.String(16),
            server_default="platform",
        ),
        sa.Column("is_current", sa.Boolean(), server_default="true"),
        sa.Column(
            "superseded_by",
            UUID(as_uuid=True),
            sa.ForeignKey("official_responses.id", ondelete="SET NULL"),
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.Column("superseded_reason", sa.Text()),
        sa.Column("withdrawn", sa.Boolean(), server_default="false"),
        sa.Column(
            "withdrawn_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True)),
        sa.Column("withdrawn_reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.CheckConstraint(
            "source IN ('platform', 'external_api', 'imported')",
            name="ck_official_responses_source",
        ),
    )

    op.create_table(
        "workflow_definitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
        ),
        sa.Column("states", JSONB(), server_default="[]"),
        sa.Column("transitions", JSONB(), server_default="{}"),
        sa.Column("required_roles", JSONB(), server_default="{}"),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
    )

    op.create_table(
        "workflow_transitions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workflow_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_definitions.id", ondelete="SET NULL"),
        ),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column(
            "actor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_required", sa.Boolean(), server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
    )
    op.create_index(
        "ix_workflow_transitions_case",
        "workflow_transitions",
        ["case_id", "created_at"],
    )

    op.create_table(
        "government_integrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("endpoint_url", sa.Text()),
        sa.Column(
            "department_id",
            UUID(as_uuid=True),
            sa.ForeignKey("departments.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column(
            "status",
            sa.String(16),
            server_default="inactive",
        ),
        sa.Column(
            "auth_type",
            sa.String(32),
            server_default="none",
        ),
        sa.Column("config", JSONB(), server_default="{}"),
        sa.Column("capabilities", JSONB(), server_default="[]"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True)),
        sa.Column("last_sync_status", sa.String(16)),
        sa.Column("last_error", sa.Text()),
        sa.Column("consecutive_failures", sa.Integer(), server_default="0"),
        sa.Column("status_mapping", JSONB(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'degraded', 'error')",
            name="ck_gov_integrations_status",
        ),
        sa.CheckConstraint(
            "auth_type IN ('none', 'api_key', 'oauth2', 'jwt', 'service_account')",
            name="ck_gov_integrations_auth_type",
        ),
    )

    op.create_table(
        "external_case_references",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "integration_id",
            UUID(as_uuid=True),
            sa.ForeignKey("government_integrations.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("external_reference_id", sa.Text(), nullable=False),
        sa.Column("external_status", sa.String(32)),
        sa.Column("mapped_status", sa.String(32)),
        sa.Column("external_data", JSONB(), server_default="{}"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column(
            "submission_status",
            sa.String(16),
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.CheckConstraint(
            "submission_status IN ('pending', 'submitted', 'synced', 'failed', 'conflict')",
            name="ck_external_refs_submission_status",
        ),
        sa.UniqueConstraint("case_id", "integration_id", name="uq_external_case_ref_once"),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "integration_id",
            UUID(as_uuid=True),
            sa.ForeignKey("government_integrations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            server_default="running",
        ),
        sa.Column("records_processed", sa.Integer(), server_default="0"),
        sa.Column("records_succeeded", sa.Integer(), server_default="0"),
        sa.Column("records_failed", sa.Integer(), server_default="0"),
        sa.Column("errors", JSONB(), server_default="[]"),
        sa.Column("external_version", sa.Text()),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "direction IN ('outbound', 'inbound')",
            name="ck_sync_runs_direction",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'partial')",
            name="ck_sync_runs_status",
        ),
    )

    op.create_table(
        "bulk_operation_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column(
            "actor_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("case_count", sa.Integer(), server_default="0"),
        sa.Column("filters", JSONB(), server_default="{}"),
        sa.Column("result_summary", JSONB(), server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=_utcnow(),
        ),
    )


def downgrade() -> None:
    op.drop_table("bulk_operation_logs")
    op.drop_table("sync_runs")
    op.drop_table("external_case_references")
    op.drop_table("government_integrations")
    op.drop_index("ix_workflow_transitions_case", table_name="workflow_transitions")
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_definitions")
    op.drop_table("official_responses")
    op.drop_table("case_handoffs")
    op.drop_table("case_routes")
    op.drop_table("routing_rules")
