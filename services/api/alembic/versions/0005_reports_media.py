"""reports, media, and campaign-scope tables

Revision ID: 0005_reports_media
Revises: 0004_postgis_gis
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_reports_media"
down_revision: str | None = "0004_postgis_gis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIERS = (
    "OFFICIAL_DATA",
    "CITIZEN_REPORT",
    "COMMUNITY_VERIFIED",
    "AI_ANALYSIS",
    "UNVERIFIED_INFORMATION",
)


def upgrade() -> None:
    op.create_table(
        "campaign_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("boundary_id", sa.Uuid(), nullable=True),
        sa.Column("district", sa.Text(), nullable=True),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["boundary_id"], ["gis_boundaries.id"], ondelete="RESTRICT"),
    )
    op.create_index(op.f("ix_campaign_scopes_campaign_id"), "campaign_scopes", ["campaign_id"])
    op.create_index(op.f("ix_campaign_scopes_boundary_id"), "campaign_scopes", ["boundary_id"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticket_no", sa.Text(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location", Geometry(geometry_type="POINT", srid=4326), nullable=False),
        sa.Column("location_accuracy_m", sa.Numeric(), nullable=False),
        sa.Column("address_hint", sa.Text(), nullable=True),
        sa.Column("boundary_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="submitted"),
        sa.Column("priority", sa.Text(), nullable=True),
        sa.Column(
            "info_class", sa.String(length=32), nullable=False, server_default="CITIZEN_REPORT"
        ),
        sa.Column("trust_score", sa.Numeric(4, 3), nullable=False, server_default="0"),
        sa.Column("duplicate_of", sa.Uuid(), nullable=True),
        sa.Column("merged_by_ai", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fields", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_no"),
        sa.ForeignKeyConstraint(["boundary_id"], ["gis_boundaries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["duplicate_of"], ["reports.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "info_class IN ('" + "', '".join(_TIERS) + "')", name="ck_reports_info_class"
        ),
    )
    op.create_index(op.f("ix_reports_category_status"), "reports", ["category_id", "status"])
    op.create_index(op.f("ix_reports_campaign_id"), "reports", ["campaign_id"])
    op.create_index(op.f("ix_reports_boundary_id"), "reports", ["boundary_id"])
    op.create_index(op.f("ix_reports_created_at"), "reports", ["created_at"])
    op.create_index(
        op.f("ix_reports_duplicate_of"),
        "reports",
        ["duplicate_of"],
        postgresql_where=sa.text("duplicate_of IS NOT NULL"),
    )

    op.create_table(
        "report_strings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "info_class", sa.String(length=32), nullable=False, server_default="COMMUNITY_VERIFIED"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_id", "locale"),
        sa.ForeignKeyConstraint(["locale"], ["locales.code"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "info_class IN ('" + "', '".join(_TIERS) + "')", name="ck_report_strings_info_class"
        ),
    )
    op.create_index(
        op.f("ix_report_strings_report_locale"),
        "report_strings",
        ["report_id", "locale"],
        unique=True,
    )

    op.create_table(
        "report_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_report_status_history_report_id"), "report_status_history", ["report_id"]
    )
    op.create_index(
        op.f("ix_report_status_history_actor_id"), "report_status_history", ["actor_id"]
    )

    op.create_table(
        "report_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("verifier_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column(
            "location_independent", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["verifier_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("kind IN ('confirm', 'refute')", name="ck_report_verifications_kind"),
    )
    op.create_index(
        op.f("ix_report_verifications_report"), "report_verifications", ["report_id", "created_at"]
    )
    op.create_index(
        op.f("ix_report_verifications_verifier"), "report_verifications", ["verifier_id"]
    )

    op.create_table(
        "report_collaborations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("contributor_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contributor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_report_collaborations_report_id"), "report_collaborations", ["report_id"]
    )

    op.create_table(
        "report_followers",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notify_level", sa.String(length=32), nullable=False, server_default="all"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "user_id"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )

    op.create_table(
        "report_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_id"], ["report_comments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_report_comments_report_id"), "report_comments", ["report_id"])

    op.create_table(
        "media_objects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("scan_status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="uploading"),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket", "object_key"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "scan_status IN ('pending', 'clean', 'infected', 'error')", name="ck_media_objects_scan"
        ),
        sa.CheckConstraint(
            "status IN ('uploading', 'available', 'failed', 'deleted')",
            name="ck_media_objects_status",
        ),
    )
    op.create_index(op.f("ix_media_objects_uploaded_by"), "media_objects", ["uploaded_by"])

    op.create_table(
        "report_media",
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("media_object_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "media_object_id"),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "kind IN ('evidence', 'resolution', 'verification')", name="ck_report_media_kind"
        ),
    )


def downgrade() -> None:
    op.drop_table("report_media")
    op.drop_index(op.f("ix_media_objects_uploaded_by"), table_name="media_objects")
    op.drop_table("media_objects")
    op.drop_index(op.f("ix_report_comments_report_id"), table_name="report_comments")
    op.drop_table("report_comments")
    op.drop_table("report_followers")
    op.drop_index(op.f("ix_report_collaborations_report_id"), table_name="report_collaborations")
    op.drop_table("report_collaborations")
    op.drop_index(op.f("ix_report_verifications_verifier"), table_name="report_verifications")
    op.drop_index(op.f("ix_report_verifications_report"), table_name="report_verifications")
    op.drop_table("report_verifications")
    op.drop_index(op.f("ix_report_status_history_actor_id"), table_name="report_status_history")
    op.drop_index(op.f("ix_report_status_history_report_id"), table_name="report_status_history")
    op.drop_table("report_status_history")
    op.drop_index(op.f("ix_report_strings_report_locale"), table_name="report_strings")
    op.drop_table("report_strings")
    op.drop_index(op.f("ix_reports_duplicate_of"), table_name="reports")
    op.drop_index(op.f("ix_reports_created_at"), table_name="reports")
    op.drop_index(op.f("ix_reports_boundary_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_campaign_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_category_status"), table_name="reports")
    op.drop_table("reports")
    op.drop_index(op.f("ix_campaign_scopes_boundary_id"), table_name="campaign_scopes")
    op.drop_index(op.f("ix_campaign_scopes_campaign_id"), table_name="campaign_scopes")
    op.drop_table("campaign_scopes")
