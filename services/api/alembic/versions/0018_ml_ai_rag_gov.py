"""Content translations, AI outputs/feedback/evaluations, RAG documents,
government datasets (PRD §22, §23, §24, §25).

pgvector note (ADR-042): `rag_chunks` is created without the vector column —
the compose PostGIS image has no `vector` extension; once the platform runs on
an instance with it (RDS ships pgvector natively), a follow-up migration adds
`embedding vector(1536)` + an HNSW index behind the same chunk id.

Revision ID: 0018_ml_ai_rag_gov
Revises: 0017_resolution_reputation
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0018_ml_ai_rag_gov"
down_revision: str | None = "0017_resolution_reputation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_translations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("original_language", sa.String(length=8), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("translation_source", sa.String(length=16), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_type", "content_id", "locale"),
        sa.CheckConstraint(
            "translation_source IN ('ai', 'community', 'official', 'system')",
            name="ck_content_translations_source",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewed', 'approved', 'rejected')",
            name="ck_content_translations_status",
        ),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_content_translations_locale"), "content_translations", ["locale", "status"]
    )

    op.create_table(
        "ai_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("output", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="succeeded"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["run_id"], ["ai_runs.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_ai_outputs_run"), "ai_outputs", ["run_id"])

    op.create_table(
        "ai_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_output_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_ai_feedback_rating"),
        sa.ForeignKeyConstraint(["ai_output_id"], ["ai_outputs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_ai_feedback_output"), "ai_feedback", ["ai_output_id"])

    op.create_table(
        "ai_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("eval_name", sa.String(length=64), nullable=False),
        sa.Column("capability", sa.String(length=64), nullable=False),
        sa.Column("dataset_ref", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_ai_evaluations_name", "eval_name", "run_at"),
    )

    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("geo_applicability", postgresql.JSONB(), nullable=True),
        sa.Column("active_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "rag_document_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_ref", sa.Text(), nullable=True),
        sa.Column(
            "chunk_strategy", sa.String(length=32), nullable=False, server_default="paragraph"
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "version"),
        sa.ForeignKeyConstraint(["document_id"], ["rag_documents.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_version_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column(
            "embedding_status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_version_id", "chunk_index"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["rag_document_versions.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(op.f("ix_rag_chunks_status"), "rag_chunks", ["embedding_status"])

    op.create_table(
        "gov_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_source_id", "version"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "gov_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_total", sa.Integer(), nullable=True),
        sa.Column("rows_imported", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["gov_datasets.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_gov_import_jobs_dataset"), "gov_import_jobs", ["dataset_id"])
    op.create_table(
        "gov_dataset_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=True),
        sa.Column("external_key", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "validation_status", sa.String(length=32), nullable=False, server_default="validated"
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "import_job_id", "external_key"),
        sa.ForeignKeyConstraint(["dataset_id"], ["gov_datasets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_job_id"], ["gov_import_jobs.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_gov_records_valid"), "gov_dataset_records", ["valid_to"])


def downgrade() -> None:
    op.drop_index(op.f("ix_gov_records_valid"), table_name="gov_dataset_records")
    op.drop_table("gov_dataset_records")
    op.drop_index(op.f("ix_gov_import_jobs_dataset"), table_name="gov_import_jobs")
    op.drop_table("gov_import_jobs")
    op.drop_table("gov_datasets")
    op.drop_index(op.f("ix_rag_chunks_status"), table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_table("rag_document_versions")
    op.drop_table("rag_documents")
    op.drop_table("ai_evaluations")
    op.drop_index(op.f("ix_ai_feedback_output"), table_name="ai_feedback")
    op.drop_table("ai_feedback")
    op.drop_index(op.f("ix_ai_outputs_run"), table_name="ai_outputs")
    op.drop_table("ai_outputs")
    op.drop_index(op.f("ix_content_translations_locale"), table_name="content_translations")
    op.drop_table("content_translations")
