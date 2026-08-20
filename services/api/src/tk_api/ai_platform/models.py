"""AI Platform models (Phase 27).

Tables:
- ai_agent_runs (agent execution tracking with traces)
- ai_tool_executions (per-tool call audit)
- ai_evaluations (evaluation results)
- ai_traces (distributed trace spans)
- ai_cost_records (per-request cost tracking)
- ai_prompt_versions (prompt registry with versioning)
- ai_skills (skill definitions)
- ai_agent_registry (agent registry with versions)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


# ---------------------------------------------------------------------------
# Agent Registry
# ---------------------------------------------------------------------------


class AiAgentRegistry(Base):
    """Registry of all registered AI agents with versions, permissions, and policies."""

    __tablename__ = "ai_agent_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    allowed_tools: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    allowed_data: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    model_policy: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    max_execution_time_s: Mapped[int] = mapped_column(Integer, default=30)
    max_tool_calls: Mapped[int] = mapped_column(Integer, default=10)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4000)
    cost_budget_usd: Mapped[float] = mapped_column(Float, default=1.0)
    permissions: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    input_schema: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    output_schema: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','deprecated','disabled')",
            name="ck_ai_agent_registry_status",
        ),
        CheckConstraint(
            "risk_level IN ('low','medium','high','critical')",
            name="ck_ai_agent_registry_risk",
        ),
    )


# ---------------------------------------------------------------------------
# Agent Execution Runs
# ---------------------------------------------------------------------------


class AiAgentRun(Base):
    """Tracks every agent execution with full trace, inputs, outputs, tools called,
    costs, and human approval status.
    """

    __tablename__ = "ai_agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    agent_code: Mapped[str] = mapped_column(String(64), index=True)
    agent_version: Mapped[int] = mapped_column(Integer, default=1)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    task: Mapped[str] = mapped_column(String(64))
    input_data: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    output_data: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    tools_called: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    model_calls: Mapped[int] = mapped_column(Integer, default=0)
    model_ids: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="created")
    error: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_status: Mapped[str] = mapped_column(String(16), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            (
                "status IN ('created','running','waiting_for_tool','waiting_for_approval',"
                " 'completed','failed','cancelled')"
            ),
            name="ck_ai_agent_runs_status",
        ),
        CheckConstraint(
            "approval_status IN ('none','pending','approved','rejected','modified')",
            name="ck_ai_agent_runs_approval",
        ),
        CheckConstraint(
            "risk_level IN ('low','medium','high','critical')",
            name="ck_ai_agent_runs_risk",
        ),
    )


# ---------------------------------------------------------------------------
# Tool Executions
# ---------------------------------------------------------------------------


class AiToolExecution(Base):
    """Audit log for every tool call made by an agent."""

    __tablename__ = "ai_tool_executions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_agent_runs.id", ondelete="CASCADE"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), index=True)
    input_params: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    output_result: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    status: Mapped[str] = mapped_column(String(16), default="success")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# ---------------------------------------------------------------------------
# Trace Spans
# ---------------------------------------------------------------------------


class AiTraceSpan(Base):
    """Distributed trace spans for AI requests. Each span tracks one unit of work
    (agent execution, model call, tool call, RAG retrieval).
    """

    __tablename__ = "ai_trace_spans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    span_type: Mapped[str] = mapped_column(String(32))  # agent|model|tool|rag|validation
    name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="ok")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    span_metadata: Mapped[dict[str, Any]] = mapped_column("span_metadata", _jsonb(), default=dict)

    __table_args__ = (Index("ix_ai_trace_spans_trace", "trace_id", "started_at"),)


# ---------------------------------------------------------------------------
# Cost Records
# ---------------------------------------------------------------------------


class AiCostRecord(Base):
    """Per-request cost tracking aggregated by day/agent/model/provider."""

    __tablename__ = "ai_cost_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    agent_code: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(32))
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("date", "agent_code", "model_id", "provider", name="uq_ai_cost_daily"),
    )


# ---------------------------------------------------------------------------
# Prompt Registry
# ---------------------------------------------------------------------------


class AiPromptVersion(Base):
    """Versioned prompt registry. Every production prompt has a version,
    status, and approval record.
    """

    __tablename__ = "ai_prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    prompt_text: Mapped[str] = mapped_column(Text)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    variables: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    agent_code: Mapped[str | None] = mapped_column(String(64))
    model_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_prompt_version"),
        CheckConstraint(
            "status IN ('draft','testing','approved','deprecated')",
            name="ck_ai_prompt_versions_status",
        ),
    )


# ---------------------------------------------------------------------------
# Skill Registry
# ---------------------------------------------------------------------------


class AiSkill(Base):
    """Reusable AI skill definitions. Skills compose tools and prompts
    into higher-level capabilities.
    """

    __tablename__ = "ai_skills"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")
    inputs: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    outputs: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    tools: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    required_permissions: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    risk_level: Mapped[str] = mapped_column(String(16), default="low")
    model_requirements: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    prompt_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','deprecated','disabled')",
            name="ck_ai_skills_status",
        ),
    )


# ---------------------------------------------------------------------------
# Evaluation Records
# ---------------------------------------------------------------------------


class AiEvalResult(Base):
    """Evaluation results for agents, tools, RAG, and safety tests."""

    __tablename__ = "ai_eval_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    eval_type: Mapped[str] = mapped_column(String(32))  # agent|tool|rag|safety|regression
    target_code: Mapped[str] = mapped_column(String(64))  # agent_code or tool_name
    target_version: Mapped[int] = mapped_column(Integer, default=1)
    test_case_id: Mapped[str | None] = mapped_column(String(64))
    input_data: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    expected_output: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    actual_output: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[float | None] = mapped_column(Float)
    metrics: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    model_id: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "eval_type IN ('agent','tool','rag','safety','regression','red_team')",
            name="ck_ai_evaluations_type",
        ),
    )
