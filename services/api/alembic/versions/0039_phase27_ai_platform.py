"""Phase 27 — AI Platform tables.

Revision ID: 0039_phase27_ai
Revises: 0038_phase26_comm
Create Date: 2026-08-18

Tables created:
- ai_agent_registry
- ai_agent_runs
- ai_tool_executions
- ai_trace_spans
- ai_cost_records
- ai_prompt_versions
- ai_skills
- ai_evaluations
"""

from __future__ import annotations

import uuid as _uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "0039_phase27_ai"
down_revision: str | None = "0038_phase26_comm"
branch_labels: str | None = None
depends_on: str | None = None


def _utcnow() -> sa.sql.elements.GenericFunction:
    return sa.func.now()


def upgrade() -> None:
    # ai_agent_registry
    op.create_table(
        "ai_agent_registry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("risk_level", sa.String(16), server_default="low"),
        sa.Column("allowed_tools", JSONB(), server_default="[]"),
        sa.Column("allowed_data", JSONB(), server_default="[]"),
        sa.Column("model_policy", JSONB(), server_default="{}"),
        sa.Column("max_execution_time_s", sa.Integer(), server_default="30"),
        sa.Column("max_tool_calls", sa.Integer(), server_default="10"),
        sa.Column("max_tokens", sa.Integer(), server_default="4000"),
        sa.Column("cost_budget_usd", sa.Float(), server_default="1.0"),
        sa.Column("permissions", JSONB(), server_default="[]"),
        sa.Column("input_schema", JSONB()),
        sa.Column("output_schema", JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "status IN ('active','deprecated','disabled')", name="ck_ai_agent_registry_status"
        ),
        sa.CheckConstraint(
            "risk_level IN ('low','medium','high','critical')", name="ck_ai_agent_registry_risk"
        ),
    )

    # ai_agent_runs
    op.create_table(
        "ai_agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("trace_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("agent_code", sa.String(64), nullable=False, index=True),
        sa.Column("agent_version", sa.Integer(), server_default="1"),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column("task", sa.String(64), nullable=False),
        sa.Column("input_data", JSONB(), server_default="{}"),
        sa.Column("output_data", JSONB(), server_default="{}"),
        sa.Column("tools_called", JSONB(), server_default="[]"),
        sa.Column("model_calls", sa.Integer(), server_default="0"),
        sa.Column("model_ids", JSONB(), server_default="[]"),
        sa.Column("tokens_in", sa.Integer(), server_default="0"),
        sa.Column("tokens_out", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Float(), server_default="0.0"),
        sa.Column("latency_ms", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(16), server_default="created"),
        sa.Column("error", sa.Text()),
        sa.Column("risk_level", sa.String(16), server_default="low"),
        sa.Column("requires_approval", sa.Boolean(), server_default="false"),
        sa.Column(
            "approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approval_status", sa.String(16), server_default="none"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('created','running','waiting_for_tool','waiting_for_approval','completed','failed','cancelled')",
            name="ck_ai_agent_runs_status",
        ),
        sa.CheckConstraint(
            "approval_status IN ('none','pending','approved','rejected','modified')",
            name="ck_ai_agent_runs_approval",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low','medium','high','critical')",
            name="ck_ai_agent_runs_risk",
        ),
    )

    # ai_tool_executions
    op.create_table(
        "ai_tool_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column(
            "agent_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ai_agent_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("tool_name", sa.String(64), nullable=False, index=True),
        sa.Column("input_params", JSONB(), server_default="{}"),
        sa.Column("output_result", JSONB(), server_default="{}"),
        sa.Column("status", sa.String(16), server_default="success"),
        sa.Column("latency_ms", sa.Integer(), server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
    )

    # ai_trace_spans
    op.create_table(
        "ai_trace_spans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("trace_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("parent_span_id", UUID(as_uuid=True)),
        sa.Column("span_type", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), server_default="ok"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("latency_ms", sa.Integer(), server_default="0"),
        sa.Column("span_metadata", JSONB(), server_default="{}"),
    )
    op.create_index("ix_ai_trace_spans_trace", "ai_trace_spans", ["trace_id", "started_at"])

    # ai_cost_records
    op.create_table(
        "ai_cost_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("agent_code", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0"),
        sa.Column("tokens_in", sa.Integer(), server_default="0"),
        sa.Column("tokens_out", sa.Integer(), server_default="0"),
        sa.Column("cost_usd", sa.Float(), server_default="0.0"),
        sa.Column("avg_latency_ms", sa.Float(), server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.UniqueConstraint("date", "agent_code", "model_id", "provider", name="uq_ai_cost_daily"),
    )

    # ai_prompt_versions
    op.create_table(
        "ai_prompt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), nullable=False, index=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(16), server_default="draft"),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text()),
        sa.Column("variables", JSONB(), server_default="[]"),
        sa.Column("agent_code", sa.String(64)),
        sa.Column("model_id", sa.String(64)),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.UniqueConstraint("code", "version", name="uq_prompt_version"),
        sa.CheckConstraint(
            "status IN ('draft','testing','approved','deprecated')",
            name="ck_ai_prompt_versions_status",
        ),
    )

    # ai_skills
    op.create_table(
        "ai_skills",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("status", sa.String(16), server_default="active"),
        sa.Column("inputs", JSONB(), server_default="{}"),
        sa.Column("outputs", JSONB(), server_default="{}"),
        sa.Column("tools", JSONB(), server_default="[]"),
        sa.Column("required_permissions", JSONB(), server_default="[]"),
        sa.Column("risk_level", sa.String(16), server_default="low"),
        sa.Column("model_requirements", JSONB(), server_default="{}"),
        sa.Column("prompt_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "status IN ('active','deprecated','disabled')", name="ck_ai_skills_status"
        ),
    )

    # ai_eval_results
    op.create_table(
        "ai_eval_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=_uuid.uuid4),
        sa.Column("eval_type", sa.String(32), nullable=False),
        sa.Column("target_code", sa.String(64), nullable=False),
        sa.Column("target_version", sa.Integer(), server_default="1"),
        sa.Column("test_case_id", sa.String(64)),
        sa.Column("input_data", JSONB(), server_default="{}"),
        sa.Column("expected_output", JSONB(), server_default="{}"),
        sa.Column("actual_output", JSONB(), server_default="{}"),
        sa.Column("passed", sa.Boolean(), server_default="false"),
        sa.Column("score", sa.Float()),
        sa.Column("metrics", JSONB(), server_default="{}"),
        sa.Column("error", sa.Text()),
        sa.Column("model_id", sa.String(64)),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_utcnow()),
        sa.CheckConstraint(
            "eval_type IN ('agent','tool','rag','safety','regression','red_team')",
            name="ck_ai_evaluations_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("ai_eval_results")
    op.drop_table("ai_skills")
    op.drop_table("ai_prompt_versions")
    op.drop_table("ai_cost_records")
    op.drop_table("ai_trace_spans")
    op.drop_table("ai_tool_executions")
    op.drop_table("ai_agent_runs")
    op.drop_table("ai_agent_registry")
