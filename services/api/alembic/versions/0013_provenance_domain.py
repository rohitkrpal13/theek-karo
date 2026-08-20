"""Provenance domain: data sources, documents, records, versions, imports.

Every externally-sourced record is traceable (PRD §6, ARCHITECTURE §15).
Closes the loop with the Cycle-1 `external_sources` / `provenance_records`.

Revision ID: 0013_provenance_domain
Revises: 0012_institutions
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0013_provenance_domain"
down_revision: str | None = "0012_institutions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("retrieval_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dataset_identifier", sa.Text(), nullable=True),
        sa.Column("version", sa.Text(), nullable=True),
        sa.Column("geo_applicability", postgresql.JSONB(), nullable=True),
        sa.Column("confidence_base", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column(
            "verification_state", sa.String(length=32), nullable=False, server_default="unverified"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", "dataset_identifier"),
        sa.CheckConstraint(
            "source_type IN ('government_portal', 'official_dataset', 'public_report', "
            "'official_website', 'citizen_submission', 'community_verification', "
            "'third_party_public')",
            name="ck_data_sources_type",
        ),
    )
    op.create_table(
        "source_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(length=32), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "source_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "label"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "data_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("rows_total", sa.Integer(), nullable=True),
        sa.Column("rows_imported", sa.Integer(), nullable=True),
        sa.Column("rows_failed", sa.Integer(), nullable=True),
        sa.Column("run_by", sa.Text(), nullable=True),
        sa.Column("logs", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_data_imports_source"), "data_imports", ["source_id"])
    op.create_table(
        "source_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_version_id", sa.Uuid(), nullable=False),
        sa.Column("data_import_id", sa.Uuid(), nullable=True),
        sa.Column("external_key", sa.Text(), nullable=False),
        sa.Column("content", postgresql.JSONB(), nullable=False),
        sa.Column("content_checksum", sa.Text(), nullable=True),
        sa.Column(
            "validation_status", sa.String(length=32), nullable=False, server_default="validated"
        ),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_key", "source_version_id"),
        sa.ForeignKeyConstraint(["data_import_id"], ["data_imports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_source_records_source_version"),
        "source_records",
        ["source_id", "source_version_id"],
    )
    op.create_index(op.f("ix_source_records_valid_to"), "source_records", ["valid_to"])
    op.create_table(
        "provenance_records_v2",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("data_source_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_record_id", sa.Uuid(), nullable=True),
        sa.Column("extraction_meta", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_record_id"], ["source_records.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_provenance_v2_entity"), "provenance_records_v2", ["entity_type", "entity_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provenance_v2_entity"), table_name="provenance_records_v2")
    op.drop_table("provenance_records_v2")
    op.drop_index(op.f("ix_source_records_valid_to"), table_name="source_records")
    op.drop_index(op.f("ix_source_records_source_version"), table_name="source_records")
    op.drop_table("source_records")
    op.drop_index(op.f("ix_data_imports_source"), table_name="data_imports")
    op.drop_table("data_imports")
    op.drop_table("source_versions")
    op.drop_table("source_documents")
    op.drop_table("data_sources")
