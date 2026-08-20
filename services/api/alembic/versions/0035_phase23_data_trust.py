"""Phase 23 — Data Trust, Provenance, Verification & Open Data layer.

Establishes the unified trust layer across the Theek Karo ecosystem:
evidence registry, verification records, data quality engine, conflict
detection/resolution, dispute management, change history, publication
snapshots, metric definitions, data quarantine, and source health tracking.

New tables: ``evidence_registry``, ``verification_records``,
``data_quality_results``, ``data_conflicts``, ``dispute_records``,
``data_change_history``, ``data_publication_snapshots``,
``metric_definitions``, ``data_quarantine_records``,
``source_health_snapshots``.

Pure additive; downgrade drops all tables.

Revision ID: 0035_phase23_data_trust
Revises: 0034_phase21_civic_action
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0035_phase23_data_trust"
down_revision: str | None = "0034_phase21_civic_action"


def upgrade() -> None:
    # -- Evidence Registry (spec §14) ----------------------------------------
    op.create_table(
        "evidence_registry",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "uploader_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "media_id",
            sa.Uuid(),
            sa.ForeignKey("media_objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column(
            "location",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="SUBMITTED"),
        sa.Column(
            "verification_status", sa.String(24), nullable=False, server_default="NOT_REVIEWED"
        ),
        sa.Column("verification_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("language", sa.String(16), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("translated_text", sa.Text(), nullable=True),
        sa.Column("translation_language", sa.String(16), nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("chain_hash", sa.String(64), nullable=True),
        sa.Column(
            "meta",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "evidence_type IN ('image','video','document','audio','text','official_record','external_reference')",
            name="ck_evidence_registry_type",
        ),
        sa.CheckConstraint(
            "status IN ('SUBMITTED','PROCESSING','UNDER_REVIEW','VERIFIED','PARTIALLY_VERIFIED','REJECTED','EXPIRED','SUPERSEDED')",
            name="ck_evidence_registry_status",
        ),
        sa.CheckConstraint(
            "verification_status IN ('NOT_REVIEWED','REVIEWED','VERIFIED','PARTIALLY_VERIFIED','DISPUTED','REJECTED')",
            name="ck_evidence_registry_verification",
        ),
        sa.CheckConstraint(
            "source_type IN ('CITIZEN','COMMUNITY','ORGANIZATION','INSTITUTION','OFFICIAL_GOVERNMENT','PUBLIC_DATASET','OPEN_DATA','PARTNER','INTERNAL','AI_GENERATED','DERIVED_ANALYTICS')",
            name="ck_evidence_registry_source_type",
        ),
    )
    op.create_index("ix_evidence_registry_source_id", "evidence_registry", ["source_id"])
    op.create_index("ix_evidence_registry_uploader_id", "evidence_registry", ["uploader_id"])
    op.create_index("ix_evidence_registry_media_id", "evidence_registry", ["media_id"])
    op.create_index(
        "ix_evidence_registry_entity", "evidence_registry", ["entity_type", "entity_id"]
    )

    # -- Verification Records (spec §17–§18) ---------------------------------
    op.create_table(
        "verification_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reviewer_type", sa.String(32), nullable=False, server_default="human"),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("method", sa.String(64), nullable=False),
        sa.Column(
            "evidence_refs",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("ai_model", sa.String(64), nullable=True),
        sa.Column("ai_model_version", sa.String(32), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("chain_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "decision IN ('NOT_REVIEWED','REVIEWED','VERIFIED','PARTIALLY_VERIFIED','DISPUTED','REJECTED')",
            name="ck_verification_records_decision",
        ),
        sa.CheckConstraint(
            "method IN ('human_review','official_source_confirmation','cross_source_consistency','location_validation','timestamp_validation','document_verification','duplicate_analysis','structured_data_validation','ai_assisted')",
            name="ck_verification_records_method",
        ),
        sa.CheckConstraint(
            "reviewer_type IN ('human', 'ai_assisted')",
            name="ck_verification_records_reviewer_type",
        ),
    )
    op.create_index("ix_verification_records_reviewer_id", "verification_records", ["reviewer_id"])
    op.create_index("ix_verification_entity", "verification_records", ["entity_type", "entity_id"])

    # -- Data Quality Results (spec §26–§28) ---------------------------------
    op.create_table(
        "data_quality_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("gov_datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("dimension", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "details",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "missing_fields",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "invalid_fields",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("overall_status", sa.String(24), nullable=False, server_default="UNVERIFIED"),
        sa.Column("ai_assisted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("ai_reasoning", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "dimension IN ('completeness','validity','consistency','uniqueness','freshness','coverage','referential_integrity')",
            name="ck_data_quality_dimension",
        ),
        sa.CheckConstraint(
            "status IN ('VALID','PARTIALLY_VALID','INVALID','INCOMPLETE','STALE','CONFLICTING','DUPLICATE','UNVERIFIED')",
            name="ck_data_quality_status",
        ),
        sa.CheckConstraint(
            "overall_status IN ('VALID','PARTIALLY_VALID','INVALID','INCOMPLETE','STALE','CONFLICTING','DUPLICATE','UNVERIFIED')",
            name="ck_data_quality_overall",
        ),
    )
    op.create_index(
        "ix_data_quality_results_entity", "data_quality_results", ["entity_type", "entity_id"]
    )
    op.create_index("ix_data_quality_results_source_id", "data_quality_results", ["source_id"])
    op.create_index("ix_data_quality_results_dataset_id", "data_quality_results", ["dataset_id"])

    # -- Data Conflicts (spec §29–§30) ---------------------------------------
    op.create_table(
        "data_conflicts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column(
            "source_a_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_a_value",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("source_a_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "source_b_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_b_value",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("source_b_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="DETECTED"),
        sa.Column(
            "resolved_value",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "resolved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="MEDIUM"),
        sa.Column(
            "meta",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('DETECTED','UNDER_REVIEW','RESOLVED_SELECT_SOURCE','RESOLVED_MERGED','RESOLVED_UNRESOLVED','DISMISSED')",
            name="ck_data_conflicts_status",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')",
            name="ck_data_conflicts_severity",
        ),
    )
    op.create_index("ix_data_conflicts_entity", "data_conflicts", ["entity_type", "entity_id"])

    # -- Dispute Records (spec §67–§69) --------------------------------------
    op.create_table(
        "dispute_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dispute_target_type", sa.String(32), nullable=False),
        sa.Column("dispute_target_id", sa.Text(), nullable=False),
        sa.Column(
            "filed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column(
            "evidence_refs",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("status", sa.String(24), nullable=False, server_default="OPEN"),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("decision", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_banner", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('OPEN','UNDER_REVIEW','RESOLVED','REJECTED','WITHDRAWN')",
            name="ck_dispute_records_status",
        ),
        sa.CheckConstraint(
            "dispute_target_type IN ('report','evidence','dataset','institution','metric','public_data')",
            name="ck_dispute_records_target",
        ),
    )
    op.create_index("ix_dispute_records_filed_by", "dispute_records", ["filed_by"])

    # -- Data Change History (spec §56) --------------------------------------
    op.create_table(
        "data_change_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(128), nullable=False),
        sa.Column(
            "old_value",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "new_value",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("change_source", sa.String(32), nullable=False),
        sa.Column(
            "changed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("previous_hash", sa.String(64), nullable=True),
        sa.Column("chain_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "change_source IN ('user','system','import','ai','correction','dispute')",
            name="ck_change_history_source",
        ),
    )
    op.create_index("ix_change_history_entity", "data_change_history", ["entity_type", "entity_id"])
    op.create_index("ix_change_history_changed_by", "data_change_history", ["changed_by"])

    # -- Data Publication Snapshots (spec §10, §83–§84) ----------------------
    op.create_table(
        "data_publication_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("gov_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("completeness_pct", sa.Float(), nullable=True),
        sa.Column("freshness_pct", sa.Float(), nullable=True),
        sa.Column("consistency_pct", sa.Float(), nullable=True),
        sa.Column("coverage_pct", sa.Float(), nullable=True),
        sa.Column("verification_pct", sa.Float(), nullable=True),
        sa.Column("conflict_count", sa.Integer(), nullable=True),
        sa.Column("duplicate_count", sa.Integer(), nullable=True),
        sa.Column("record_count", sa.Integer(), nullable=True),
        sa.Column("methodology", sa.Text(), nullable=True),
        sa.Column("snapshot_key", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_pub_snapshots_dataset", "data_publication_snapshots", ["dataset_id", "created_at"]
    )

    # -- Metric Definitions (spec §61–§62) -----------------------------------
    op.create_table(
        "metric_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("metric_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_hi", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("definition", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("previous_version_id", sa.Uuid(), nullable=True),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="PUBLIC"),
        sa.Column("required_role", sa.String(32), nullable=True),
        sa.Column("coverage", sa.Text(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("period", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'deprecated')",
            name="ck_metric_definitions_status",
        ),
        sa.CheckConstraint(
            "visibility IN ('PUBLIC', 'COMMUNITY', 'DEPARTMENT', 'ADMIN', 'RESTRICTED')",
            name="ck_metric_definitions_visibility",
        ),
    )

    # -- Data Quarantine (spec §88) ------------------------------------------
    op.create_table(
        "data_quarantine_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("gov_datasets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "import_job_id",
            sa.Uuid(),
            sa.ForeignKey("gov_import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_key", sa.Text(), nullable=True),
        sa.Column(
            "raw_data",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "rejection_reasons",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="RECEIVED"),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('RECEIVED','VALIDATING','QUARANTINED','APPROVED','REJECTED')",
            name="ck_quarantine_status",
        ),
    )
    op.create_index("ix_data_quarantine_dataset_id", "data_quarantine_records", ["dataset_id"])

    # -- Source Health Snapshots (spec §34, §85) ------------------------------
    op.create_table(
        "source_health_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_id",
            sa.Uuid(),
            sa.ForeignKey("data_sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("records_received", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_accepted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_duplicated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_conflicting", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("schema_changed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('HEALTHY', 'DEGRADED', 'FAILED')",
            name="ck_source_health_status",
        ),
    )
    op.create_index("ix_source_health_source_id", "source_health_snapshots", ["source_id"])
    op.create_index(
        "ix_source_health_source_time", "source_health_snapshots", ["source_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("source_health_snapshots")
    op.drop_table("data_quarantine_records")
    op.drop_table("metric_definitions")
    op.drop_table("data_publication_snapshots")
    op.drop_table("data_change_history")
    op.drop_table("dispute_records")
    op.drop_table("data_conflicts")
    op.drop_table("data_quality_results")
    op.drop_table("verification_records")
    op.drop_table("evidence_registry")
