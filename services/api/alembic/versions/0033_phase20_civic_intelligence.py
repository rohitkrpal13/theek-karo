"""Phase 20 national civic intelligence platform.

Adds the civic-intelligence data model: a reusable signal model (every
detection carries evidence + sources + confidence), issue clusters, trend
snapshots, anomaly events, deterministic forecasts with a model registry,
an audited human review queue, and reproducible intelligence reports.

Design principles (docs/CIVIC-INTELLIGENCE.md):

* AI assists humans — it never makes consequential decisions on its own.
* Every signal is a review trigger, never an accusation.
* Every signal carries provenance: evidence rows, source rows, the
  deterministic analytics that produced it, and its confidence.
* Forecasts are only produced when sufficient historical data exists, and
  always carry uncertainty ranges + the model version used.

* ``civic_signals`` — one row per detected signal (TREND, ANOMALY, CLUSTER,
  RECURRING_ISSUE, RESOURCE_GAP, DATA_GAP, SLOW_RESOLUTION, IMPROVEMENT,
  DECLINE, SUDDEN_CHANGE, DATA_CONFLICT, STALE_DATA, EARLY_WARNING). State
  machine: NEW → UNDER_REVIEW → CONFIRMED_SIGNAL | DISMISSED | MONITORING →
  RESOLVED.
* ``signal_evidence`` — evidence rows supporting a signal (report counts,
  case rows, dataset metrics, discrepancies, forecast points…).
* ``signal_sources`` — data sources behind a signal (community, official
  dataset, platform aggregate…), with dataset version + retrieval time.
* ``issue_clusters`` — related-report groups (never deletes reports).
* ``trend_snapshots`` — append-only deterministic trend calculations.
* ``anomaly_events`` — deterministic anomaly detections with expected range.
* ``forecast_runs`` + ``forecast_results`` — deterministic forecasts with
  uncertainty bands, training window, model version + evaluation metrics.
* ``intelligence_reviews`` — append-only human review decisions.
* ``intelligence_reports`` — reproducible report documents (filters,
  methodology, dataset + model versions stored with each run).
* ``model_versions`` — registry of analytics/forecast model versions.

Pure additive; downgrade drops the tables.

Revision ID: 0033_phase20_civic_intelligence
Revises: 0032_phase19_integrations
Create Date: 2026-08-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0033_phase20_civic_intelligence"
down_revision: str | None = "0032_phase19_integrations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SIGNAL_TYPES = (
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

_SIGNAL_STATUSES = (
    "NEW",
    "UNDER_REVIEW",
    "CONFIRMED_SIGNAL",
    "DISMISSED",
    "MONITORING",
    "RESOLVED",
)

_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
_CONFIDENCES = ("LOW", "MEDIUM", "HIGH")
_VISIBILITIES = ("PUBLIC", "COMMUNITY", "DEPARTMENT", "ADMIN", "RESTRICTED")

_REVIEW_ACTIONS = (
    "CONFIRM",
    "DISMISS",
    "REQUEST_MORE_DATA",
    "MONITOR",
    "ESCALATE",
    "MARK_RESOLVED",
)


def upgrade() -> None:
    op.create_table(
        "civic_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category_slug", sa.String(length=64), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column(
            "severity",
            sa.String(length=16),
            nullable=False,
            server_default="MEDIUM",
        ),
        sa.Column(
            "confidence",
            sa.String(length=16),
            nullable=False,
            server_default="MEDIUM",
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column(
            "visibility",
            sa.String(length=16),
            nullable=False,
            server_default="PUBLIC",
        ),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observation_period", sa.JSON(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("explanation", sa.JSON(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "signal_type IN ('TREND', 'ANOMALY', 'CLUSTER', 'RECURRING_ISSUE', "
            "'RESOURCE_GAP', 'DATA_GAP', 'SLOW_RESOLUTION', 'IMPROVEMENT', 'DECLINE', "
            "'SUDDEN_CHANGE', 'DATA_CONFLICT', 'STALE_DATA', 'EARLY_WARNING')",
            name="ck_civic_signals_signal_type",
        ),
        sa.CheckConstraint(
            "status IN ('NEW', 'UNDER_REVIEW', 'CONFIRMED_SIGNAL', 'DISMISSED', "
            "'MONITORING', 'RESOLVED')",
            name="ck_civic_signals_status",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_civic_signals_severity",
        ),
        sa.CheckConstraint(
            "confidence IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_civic_signals_confidence"
        ),
        sa.CheckConstraint(
            "visibility IN ('PUBLIC', 'COMMUNITY', 'DEPARTMENT', 'ADMIN', 'RESTRICTED')",
            name="ck_civic_signals_visibility",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_civic_signals_status_detected", "civic_signals", ["status", "detected_at"])
    op.create_index("ix_civic_signals_geo_type", "civic_signals", ["geography_id", "signal_type"])
    op.create_index("ix_civic_signals_institution", "civic_signals", ["institution_id"])

    op.create_table(
        "signal_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["signal_id"], ["civic_signals.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_signal_evidence_signal", "signal_evidence", ["signal_id"])

    op.create_table(
        "signal_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("dataset_version", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "source_kind IN ('COMMUNITY', 'OFFICIAL', 'PUBLIC_DATASET', 'PLATFORM', "
            "'GEOGRAPHY', 'INSTITUTION', 'EXTERNAL')",
            name="ck_signal_sources_source_kind",
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["civic_signals.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_signal_sources_signal", "signal_sources", ["signal_id"])

    op.create_table(
        "issue_clusters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cluster_key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("category_slug", sa.String(length=64), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("report_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'under_review', 'confirmed', 'archived')",
            name="ck_issue_clusters_status",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_issue_clusters_status", "issue_clusters", ["status"])
    op.create_index("ix_issue_clusters_geo", "issue_clusters", ["geography_id"])

    op.create_table(
        "trend_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("category_slug", sa.String(length=64), nullable=True),
        sa.Column("period", sa.JSON(), nullable=True),
        sa.Column("interval", sa.String(length=8), nullable=True),
        sa.Column("series", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("change_count", sa.Integer(), nullable=True),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column(
            "direction",
            sa.String(length=24),
            nullable=False,
            server_default="insufficient_data",
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "direction IN ('increasing', 'decreasing', 'stable', 'insufficient_data')",
            name="ck_trend_snapshots_direction",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_trend_snapshots_geo_metric", "trend_snapshots", ["geography_id", "metric"])

    op.create_table(
        "anomaly_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("category_slug", sa.String(length=64), nullable=True),
        sa.Column("observed_value", sa.Float(), nullable=False),
        sa.Column("expected_low", sa.Float(), nullable=True),
        sa.Column("expected_high", sa.Float(), nullable=True),
        sa.Column("deviation_pct", sa.Float(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="NEW",
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('NEW', 'UNDER_REVIEW', 'CONFIRMED', 'DISMISSED')",
            name="ck_anomaly_events_status",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_anomaly_events_status_detected", "anomaly_events", ["status", "detected_at"]
    )

    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("category_slug", sa.String(length=64), nullable=True),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=True),
        sa.Column("training_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("min_points", sa.Integer(), nullable=True),
        sa.Column("method", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            nullable=False,
            server_default="completed",
        ),
        sa.Column("eval_metrics", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'insufficient_data')",
            name="ck_forecast_runs_status",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_forecast_runs_metric", "forecast_runs", ["metric", "created_at"])

    op.create_table(
        "forecast_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("point", sa.DateTime(timezone=True), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("point_value", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["forecast_runs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_forecast_results_run", "forecast_results", ["run_id", "point"])

    op.create_table(
        "intelligence_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "action IN ('CONFIRM', 'DISMISS', 'REQUEST_MORE_DATA', 'MONITOR', "
            "'ESCALATE', 'MARK_RESOLVED')",
            name="ck_intelligence_reviews_action",
        ),
        sa.ForeignKeyConstraint(["signal_id"], ["civic_signals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_intelligence_reviews_signal", "intelligence_reviews", ["signal_id"])

    op.create_table(
        "intelligence_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="PUBLIC"),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("format", sa.String(length=8), nullable=False, server_default="json"),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("file_key", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("methodology", sa.JSON(), nullable=True),
        sa.Column("dataset_versions", sa.JSON(), nullable=True),
        sa.Column("model_versions", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "scope IN ('PUBLIC', 'COMMUNITY', 'DEPARTMENT', 'ADMIN', 'RESTRICTED')",
            name="ck_intelligence_reports_scope",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'generating', 'ready', 'failed')",
            name="ck_intelligence_reports_status",
        ),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("training_data_ref", sa.Text(), nullable=True),
        sa.Column("feature_definition", sa.JSON(), nullable=True),
        sa.Column("evaluation_metrics", sa.JSON(), nullable=True),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_name", "version", name="uq_model_versions_name_version"),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'retired')", name="ck_model_versions_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("model_versions")
    op.drop_table("intelligence_reports")
    op.drop_index("ix_intelligence_reviews_signal", table_name="intelligence_reviews")
    op.drop_table("intelligence_reviews")
    op.drop_index("ix_forecast_results_run", table_name="forecast_results")
    op.drop_table("forecast_results")
    op.drop_index("ix_forecast_runs_metric", table_name="forecast_runs")
    op.drop_table("forecast_runs")
    op.drop_index("ix_anomaly_events_status_detected", table_name="anomaly_events")
    op.drop_table("anomaly_events")
    op.drop_index("ix_trend_snapshots_geo_metric", table_name="trend_snapshots")
    op.drop_table("trend_snapshots")
    op.drop_index("ix_issue_clusters_geo", table_name="issue_clusters")
    op.drop_index("ix_issue_clusters_status", table_name="issue_clusters")
    op.drop_table("issue_clusters")
    op.drop_index("ix_signal_sources_signal", table_name="signal_sources")
    op.drop_table("signal_sources")
    op.drop_index("ix_signal_evidence_signal", table_name="signal_evidence")
    op.drop_table("signal_evidence")
    op.drop_index("ix_civic_signals_institution", table_name="civic_signals")
    op.drop_index("ix_civic_signals_geo_type", table_name="civic_signals")
    op.drop_index("ix_civic_signals_status_detected", table_name="civic_signals")
    op.drop_table("civic_signals")
