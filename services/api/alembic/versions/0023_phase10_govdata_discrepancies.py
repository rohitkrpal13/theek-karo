"""Phase 10: Government data payloads, entity matching review, and institution discrepancies.

Revision ID: 0023_phase10_govdata_discrepancies
Revises: 0022_phase8_reporting_enhancements
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0023_phase10_govdata_discrepancies"
down_revision: str | None = "0022_phase8_reporting_enhancements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DISCREPANCY_STATES = (
    "discrepancy_state IN ('NO_DISCREPANCY_DETECTED', 'POSSIBLE_DISCREPANCY', "
    "'CONFLICTING_DATA', 'OUTDATED_OFFICIAL_DATA', 'INSUFFICIENT_DATA', "
    "'UNDER_REVIEW', 'RESOLVED')"
)

_MATCH_STATUSES = "match_status IN ('MATCHED', 'POSSIBLE_MATCH', 'CONFLICT', 'UNMATCHED')"

_REVIEW_STATUSES = "review_status IN ('pending', 'confirmed', 'rejected', 'created_new')"


def upgrade() -> None:
    # 1. Raw Payloads
    op.create_table(
        "gov_raw_payloads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("checksum_sha256", sa.Text(), nullable=True),
        sa.Column(
            "mime_type", sa.String(length=64), nullable=False, server_default="application/json"
        ),
        sa.Column("byte_size", sa.Integer(), nullable=True),
        sa.Column("raw_content", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="stored"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["dataset_id"], ["gov_datasets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_job_id"], ["gov_import_jobs.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_gov_raw_payloads_dataset"), "gov_raw_payloads", ["dataset_id"])

    # 2. Entity Match Reviews
    op.create_table(
        "entity_match_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=True),
        sa.Column("external_key", sa.Text(), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_institution_id", sa.Uuid(), nullable=True),
        sa.Column("match_confidence", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column(
            "match_status", sa.String(length=32), nullable=False, server_default="POSSIBLE_MATCH"
        ),
        sa.Column("match_signals", postgresql.JSONB(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_MATCH_STATUSES, name="ck_entity_matches_status"),
        sa.CheckConstraint(_REVIEW_STATUSES, name="ck_entity_matches_review"),
        sa.ForeignKeyConstraint(["dataset_id"], ["gov_datasets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["import_job_id"], ["gov_import_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["candidate_institution_id"], ["institutions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_entity_matches_dataset"), "entity_match_reviews", ["dataset_id"])
    op.create_index(
        op.f("ix_entity_matches_candidate"), "entity_match_reviews", ["candidate_institution_id"]
    )
    op.create_index(op.f("ix_entity_matches_status"), "entity_match_reviews", ["review_status"])

    # 3. Institution Discrepancies
    op.create_table(
        "institution_discrepancies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("resource_key", sa.String(length=64), nullable=False),
        sa.Column(
            "discrepancy_state",
            sa.String(length=32),
            nullable=False,
            server_default="NO_DISCREPANCY_DETECTED",
        ),
        sa.Column("official_value", postgresql.JSONB(), nullable=True),
        sa.Column("citizen_summary", sa.Text(), nullable=True),
        sa.Column("ai_finding", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False, server_default="0.5"),
        sa.Column("rule_code", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(_DISCREPANCY_STATES, name="ck_discrepancies_state"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_discrepancies_inst"), "institution_discrepancies", ["institution_id"])
    op.create_index(
        op.f("ix_discrepancies_state"), "institution_discrepancies", ["discrepancy_state"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_discrepancies_state"), table_name="institution_discrepancies")
    op.drop_index(op.f("ix_discrepancies_inst"), table_name="institution_discrepancies")
    op.drop_table("institution_discrepancies")

    op.drop_index(op.f("ix_entity_matches_status"), table_name="entity_match_reviews")
    op.drop_index(op.f("ix_entity_matches_candidate"), table_name="entity_match_reviews")
    op.drop_index(op.f("ix_entity_matches_dataset"), table_name="entity_match_reviews")
    op.drop_table("entity_match_reviews")

    op.drop_index(op.f("ix_gov_raw_payloads_dataset"), table_name="gov_raw_payloads")
    op.drop_table("gov_raw_payloads")
