"""Reports v2 (institution/issue-type/severity links), evidence, media pipeline,
duplicates (PRD §9, §7, §11, §12, §13).

Revision ID: 0015_reports_v2
Revises: 0014_categories_issue_types
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0015_reports_v2"
down_revision: str | None = "0014_categories_issue_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("institution_id", sa.Uuid(), nullable=True))
    op.add_column("reports", sa.Column("issue_type_id", sa.Uuid(), nullable=True))
    op.add_column("reports", sa.Column("severity", sa.String(length=16), nullable=True))
    op.add_column(
        "reports",
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"),
    )
    op.add_column("reports", sa.Column("source", sa.String(length=32), nullable=True))
    op.create_foreign_key(
        "fk_reports_institution_id",
        "reports",
        "institutions",
        ["institution_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_reports_issue_type",
        "reports",
        "issue_types",
        ["issue_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_reports_institution_id", "reports", ["institution_id"])
    op.create_index("ix_reports_issue_type_id", "reports", ["issue_type_id"])
    op.create_index("ix_reports_severity_status", "reports", ["severity", "status"])
    op.create_check_constraint(
        "ck_reports_severity",
        "reports",
        "severity IN ('low', 'medium', 'high', 'critical') OR severity IS NULL",
    )
    op.create_check_constraint(
        "ck_reports_visibility",
        "reports",
        "visibility IN ('public', 'private', 'unlisted')",
    )

    op.create_table(
        "report_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("media_object_id", sa.Uuid(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("structured", postgresql.JSONB(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "moderation_status", sa.String(length=16), nullable=False, server_default="pending"
        ),
        sa.Column(
            "verification_status", sa.String(length=16), nullable=False, server_default="unreviewed"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('image', 'video', 'document', 'url', 'structured')",
            name="ck_report_evidence_kind",
        ),
        sa.CheckConstraint(
            "moderation_status IN ('pending', 'approved', 'flagged', 'removed')",
            name="ck_report_evidence_moderation",
        ),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_report_evidence_report"), "report_evidence", ["report_id"])

    op.create_table(
        "media_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_object_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="UPLOADED"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('UPLOADED', 'PROCESSING', 'PROCESSED', 'FAILED', "
            "'QUARANTINED', 'REJECTED')",
            name="ck_media_processing_status",
        ),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_media_processing_jobs_status"),
        "media_processing_jobs",
        ["status", "created_at"],
    )

    op.create_table(
        "report_duplicates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_report_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="possible"),
        sa.Column("similarity", sa.Numeric(5, 4), nullable=True),
        sa.Column("detection_method", sa.String(length=32), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('possible', 'confirmed', 'rejected')",
            name="ck_report_duplicates_status",
        ),
        sa.CheckConstraint(
            "report_id <> candidate_report_id", name="ck_report_duplicates_not_self"
        ),
        sa.ForeignKeyConstraint(["candidate_report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_report_duplicates_lookup"),
        "report_duplicates",
        ["report_id", "status"],
    )
    op.create_index(
        op.f("ix_report_duplicates_candidate"),
        "report_duplicates",
        ["candidate_report_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_duplicates_candidate"), table_name="report_duplicates")
    op.drop_index(op.f("ix_report_duplicates_lookup"), table_name="report_duplicates")
    op.drop_table("report_duplicates")
    op.drop_index(op.f("ix_media_processing_jobs_status"), table_name="media_processing_jobs")
    op.drop_table("media_processing_jobs")
    op.drop_index(op.f("ix_report_evidence_report"), table_name="report_evidence")
    op.drop_table("report_evidence")
    op.drop_index("ix_reports_severity_status", table_name="reports")
    op.drop_index("ix_reports_issue_type_id", table_name="reports")
    op.drop_index("ix_reports_institution_id", table_name="reports")
    op.drop_constraint("fk_reports_issue_type", "reports", type_="foreignkey")
    op.drop_constraint("fk_reports_institution_id", "reports", type_="foreignkey")
    op.drop_column("reports", "source")
    op.drop_column("reports", "visibility")
    op.drop_column("reports", "severity")
    op.drop_column("reports", "issue_type_id")
    op.drop_column("reports", "institution_id")
