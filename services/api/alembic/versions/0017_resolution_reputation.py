"""Resolution, reputation, subscriptions, notifications devices (PRD S16-S19, S21).

Revision ID: 0017_resolution_reputation
Revises: 0016_community_moderation
Create Date: 2026-08-16

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "0017_resolution_reputation"
down_revision: str | None = "0016_community_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resolution_submissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("responsible_party", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', 'rejected', 'disputed')",
            name="ck_resolution_submissions_status",
        ),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_resolution_submissions_report"), "resolution_submissions", ["report_id", "status"]
    )
    op.create_table(
        "resolution_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resolution_submission_id", sa.Uuid(), nullable=False),
        sa.Column("media_object_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('before', 'after', 'document', 'other')", name="ck_resolution_evidence_kind"
        ),
        sa.ForeignKeyConstraint(["media_object_id"], ["media_objects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["resolution_submission_id"], ["resolution_submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "resolution_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resolution_submission_id", sa.Uuid(), nullable=False),
        sa.Column("verifier_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "decision IN ('confirm', 'refute')", name="ck_resolution_verifications_decision"
        ),
        sa.ForeignKeyConstraint(
            ["resolution_submission_id"], ["resolution_submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["verifier_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "uq_resolution_verifications_one",
        "resolution_verifications",
        ["resolution_submission_id", "verifier_id"],
        unique=True,
    )
    op.create_table(
        "resolution_disputes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("resolution_submission_id", sa.Uuid(), nullable=False),
        sa.Column("raised_by", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("resolved_by", sa.Uuid(), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'upheld', 'rejected')", name="ck_resolution_disputes_status"
        ),
        sa.ForeignKeyConstraint(["raised_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["resolution_submission_id"], ["resolution_submissions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
    )

    op.create_table(
        "reputation_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_kind"),
    )
    op.create_table(
        "reputation_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=True),
        sa.Column("content_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_reputation_events_user_created"), "reputation_events", ["user_id", "created_at"]
    )
    op.bulk_insert(
        sa.table(
            "reputation_policies",
            sa.column("id", sa.Uuid()),
            sa.column("event_kind", sa.String()),
            sa.column("delta", sa.Integer()),
            sa.column("description", sa.Text()),
            sa.column("created_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "id": uuid.uuid4(),
                "event_kind": kind,
                "delta": delta,
                "description": desc,
                "created_at": datetime.now(UTC),
            }
            for kind, delta, desc in [
                ("valid_report", 10, "report later verified"),
                ("useful_evidence", 5, "evidence accepted"),
                ("helpful_verification", 3, "verification voted correct"),
                ("constructive_comment", 1, "comment kept by moderation"),
                ("confirmed_duplicate", 2, "helped merge duplicates"),
                ("false_report", -8, "report rejected as false"),
                ("abuse", -20, "moderation strike"),
                ("spam", -15, "spam content removed"),
            ]
        ],
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("subscriber_kind", sa.String(length=16), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "subscriber_kind IN ('report', 'institution', 'geography', 'category', 'campaign')",
            name="ck_subscriptions_kind",
        ),
        sa.CheckConstraint(
            "((report_id IS NOT NULL)::int + (institution_id IS NOT NULL)::int + "
            "(geography_id IS NOT NULL)::int + (category_id IS NOT NULL)::int + "
            "(campaign_id IS NOT NULL)::int) = 1",
            name="ck_subscriptions_single_target",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_subscriptions_target",
        "subscriptions",
        [
            "user_id",
            "subscriber_kind",
            "report_id",
            "institution_id",
            "geography_id",
            "category_id",
            "campaign_id",
        ],
        unique=True,
    )

    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_devices_user"), "devices", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_devices_user"), table_name="devices")
    op.drop_table("devices")
    op.drop_index("uq_subscriptions_target", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("reputation_policies")
    op.drop_index(op.f("ix_reputation_events_user_created"), table_name="reputation_events")
    op.drop_table("reputation_events")
    op.drop_table("resolution_disputes")
    op.drop_index("uq_resolution_verifications_one", table_name="resolution_verifications")
    op.drop_table("resolution_verifications")
    op.drop_table("resolution_evidence")
    op.drop_index(op.f("ix_resolution_submissions_report"), table_name="resolution_submissions")
    op.drop_table("resolution_submissions")
