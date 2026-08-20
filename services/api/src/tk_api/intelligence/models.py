"""Civic intelligence entities (Phase 20, docs/CIVIC-INTELLIGENCE.md).

The signal model is the core: every detection (trend, anomaly, cluster,
recurring issue, resource/data gap, improvement, early warning) is persisted
as a ``CivicSignal`` with linked ``SignalEvidence`` and ``SignalSource`` rows
so every signal carries provenance, confidence and a review state. Reviews
are append-only (``IntelligenceReview``), so the history of human decisions
is never rewritten.

Forecasts are deterministic and versioned: ``ForecastRun`` (training window,
model version, evaluation metrics, status incl. ``insufficient_data``) plus
per-point ``ForecastResult`` rows with uncertainty bands.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
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

SIGNAL_TYPES = (
    "TREND",
    "ANOMALY",
    "CLUSTER",
    "RECURRING_ISSUE",
    "RESOURCE_GAP",
    "DATA_GAP",
    "SLOW_RESOLUTION",
    "IMPROVEMENT",
    "DECLINE",
    "SUDDEN_CHANGE",
    "DATA_CONFLICT",
    "STALE_DATA",
    "EARLY_WARNING",
)

SIGNAL_STATUSES = ("NEW", "UNDER_REVIEW", "CONFIRMED_SIGNAL", "DISMISSED", "MONITORING", "RESOLVED")

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
CONFIDENCES = ("LOW", "MEDIUM", "HIGH")
VISIBILITIES = ("PUBLIC", "COMMUNITY", "DEPARTMENT", "ADMIN", "RESTRICTED")

REVIEW_ACTIONS = (
    "CONFIRM",
    "DISMISS",
    "REQUEST_MORE_DATA",
    "MONITOR",
    "ESCALATE",
    "MARK_RESOLVED",
)


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CivicSignal(Base):
    __tablename__ = "civic_signals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    signal_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category_slug: Mapped[str | None] = mapped_column(String(64))
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL"), index=True
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), index=True
    )
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    confidence: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(24), default="NEW")
    visibility: Mapped[str] = mapped_column(String(16), default="PUBLIC")
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    source_count: Mapped[int] = mapped_column(Integer, default=0)
    observation_period: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    payload: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    explanation: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "signal_type IN ('TREND', 'ANOMALY', 'CLUSTER', 'RECURRING_ISSUE', "
            "'RESOURCE_GAP', 'DATA_GAP', 'SLOW_RESOLUTION', 'IMPROVEMENT', 'DECLINE', "
            "'SUDDEN_CHANGE', 'DATA_CONFLICT', 'STALE_DATA', 'EARLY_WARNING')",
            name="ck_civic_signals_signal_type",
        ),
        CheckConstraint(
            "status IN ('NEW', 'UNDER_REVIEW', 'CONFIRMED_SIGNAL', 'DISMISSED', "
            "'MONITORING', 'RESOLVED')",
            name="ck_civic_signals_status",
        ),
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="ck_civic_signals_severity"
        ),
        CheckConstraint(
            "confidence IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_civic_signals_confidence"
        ),
        CheckConstraint(
            "visibility IN ('PUBLIC', 'COMMUNITY', 'DEPARTMENT', 'ADMIN', 'RESTRICTED')",
            name="ck_civic_signals_visibility",
        ),
    )


class SignalEvidence(Base):
    __tablename__ = "signal_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_signals.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32))
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    payload: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    source: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SignalSource(Base):
    __tablename__ = "signal_sources"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_signals.id", ondelete="CASCADE"), index=True
    )
    source_kind: Mapped[str] = mapped_column(String(32))
    source_name: Mapped[str | None] = mapped_column(Text)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    dataset_version: Mapped[str | None] = mapped_column(Text)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "source_kind IN ('COMMUNITY', 'OFFICIAL', 'PUBLIC_DATASET', 'PLATFORM', "
            "'GEOGRAPHY', 'INSTITUTION', 'EXTERNAL')",
            name="ck_signal_sources_source_kind",
        ),
    )


class IssueCluster(Base):
    __tablename__ = "issue_clusters"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cluster_key: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str | None] = mapped_column(Text)
    category_slug: Mapped[str | None] = mapped_column(String(64))
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL"), index=True
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL")
    )
    report_ids: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    report_count: Mapped[int] = mapped_column(Integer, default=0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'under_review', 'confirmed', 'archived')",
            name="ck_issue_clusters_status",
        ),
    )


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    metric: Mapped[str] = mapped_column(String(64))
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL"), index=True
    )
    category_slug: Mapped[str | None] = mapped_column(String(64))
    period: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    interval: Mapped[str | None] = mapped_column(String(8))
    series: Mapped[list[Any]] = mapped_column(_jsonb(), default=list)
    change_count: Mapped[int | None] = mapped_column(Integer)
    change_pct: Mapped[float | None] = mapped_column(Float)
    direction: Mapped[str] = mapped_column(String(24), default="insufficient_data")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AnomalyEvent(Base):
    __tablename__ = "anomaly_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    metric: Mapped[str] = mapped_column(String(64))
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL")
    )
    category_slug: Mapped[str | None] = mapped_column(String(64))
    observed_value: Mapped[float] = mapped_column(Float)
    expected_low: Mapped[float | None] = mapped_column(Float)
    expected_high: Mapped[float | None] = mapped_column(Float)
    deviation_pct: Mapped[float | None] = mapped_column(Float)
    method: Mapped[str | None] = mapped_column(String(64))
    explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="NEW")
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('NEW', 'UNDER_REVIEW', 'CONFIRMED', 'DISMISSED')",
            name="ck_anomaly_events_status",
        ),
    )


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    metric: Mapped[str] = mapped_column(String(64))
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL")
    )
    category_slug: Mapped[str | None] = mapped_column(String(64))
    horizon_days: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str | None] = mapped_column(String(64))
    training_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_points: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="completed")
    eval_metrics: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'insufficient_data')",
            name="ck_forecast_runs_status",
        ),
    )


class ForecastResult(Base):
    __tablename__ = "forecast_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"), index=True
    )
    point: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    low: Mapped[float] = mapped_column(Float)
    point_value: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IntelligenceReview(Base):
    """Append-only human review decision on a signal (audited via audit_logs too)."""

    __tablename__ = "intelligence_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    signal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_signals.id", ondelete="CASCADE"), index=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(32))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "action IN ('CONFIRM', 'DISMISS', 'REQUEST_MORE_DATA', 'MONITOR', "
            "'ESCALATE', 'MARK_RESOLVED')",
            name="ck_intelligence_reviews_action",
        ),
    )


class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(16), default="PUBLIC")
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL")
    )
    filters: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    status: Mapped[str] = mapped_column(String(16), default="pending")
    format: Mapped[str] = mapped_column(String(8), default="json")
    content: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    file_key: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    methodology: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    dataset_versions: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    model_versions: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "scope IN ('PUBLIC', 'COMMUNITY', 'DEPARTMENT', 'ADMIN', 'RESTRICTED')",
            name="ck_intelligence_reports_scope",
        ),
        CheckConstraint(
            "status IN ('pending', 'generating', 'ready', 'failed')",
            name="ck_intelligence_reports_status",
        ),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(32))
    model_type: Mapped[str] = mapped_column(String(32))
    training_data_ref: Mapped[str | None] = mapped_column(Text)
    feature_definition: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    evaluation_metrics: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_versions_name_version"),
        CheckConstraint(
            "status IN ('active', 'archived', 'retired')", name="ck_model_versions_status"
        ),
    )
