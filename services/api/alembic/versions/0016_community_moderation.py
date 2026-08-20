"""Community + moderation (PRD §8, §15, §20).

Revision ID: 0016_community_moderation
Revises: 0015_reports_v2
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_community_moderation"
down_revision: str | None = "0015_reports_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("comment_id", sa.Uuid(), nullable=True),
        sa.Column("post_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "kind IN ('like', 'helpful', 'confirm', 'celebrate', 'flag')",
            name="ck_reactions_kind",
        ),
        sa.CheckConstraint(
            "((report_id IS NOT NULL)::int + (comment_id IS NOT NULL)::int + "
            "(post_id IS NOT NULL)::int + (institution_id IS NOT NULL)::int) = 1",
            name="ck_reactions_single_target",
        ),
        sa.ForeignKeyConstraint(["comment_id"], ["report_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "uq_reactions_report_user", "reactions", ["report_id", "user_id", "kind"], unique=True
    )
    op.create_index(
        "uq_reactions_comment_user", "reactions", ["comment_id", "user_id", "kind"], unique=True
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("geography_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("post_type", sa.String(length=32), nullable=False, server_default="update"),
        sa.Column("visibility", sa.String(length=16), nullable=False, server_default="public"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_posts_geo_created"), "posts", ["geography_id", "created_at"])

    op.create_table(
        "institution_followers",
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("institution_id", "user_id"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "geography_followers",
        sa.Column("geography_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("geography_id", "user_id"),
        sa.ForeignKeyConstraint(["geography_id"], ["geographies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "((report_id IS NOT NULL)::int + (institution_id IS NOT NULL)::int) = 1",
            name="ck_bookmarks_single_target",
        ),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("uq_bookmarks_report_user", "bookmarks", ["report_id", "user_id"], unique=True)

    op.create_table(
        "content_reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'actioned', 'dismissed', 'appealed')",
            name="ck_content_reports_status",
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_content_reports_status_created"), "content_reports", ["status", "created_at"]
    )
    op.create_index(
        "uq_content_reports_one",
        "content_reports",
        ["content_type", "content_id", "reporter_id"],
        unique=True,
    )

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("moderator_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "action IN ('warn', 'hide', 'remove', 'strike', 'restore')",
            name="ck_moderation_actions_action",
        ),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_moderation_actions_content"), "moderation_actions", ["content_type", "content_id"]
    )
    op.create_table(
        "moderation_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("moderation_action_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "decision IN ('upheld', 'overturned', 'expired')",
            name="ck_moderation_decisions_decision",
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["moderation_action_id"], ["moderation_actions.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "moderation_appeals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("moderation_action_id", sa.Uuid(), nullable=False),
        sa.Column("appealant_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('open', 'upheld', 'rejected')", name="ck_moderation_appeals_status"
        ),
        sa.ForeignKeyConstraint(["appealant_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["moderation_action_id"], ["moderation_actions.id"], ondelete="RESTRICT"
        ),
    )


def downgrade() -> None:
    op.drop_table("moderation_appeals")
    op.drop_table("moderation_decisions")
    op.drop_index(op.f("ix_moderation_actions_content"), table_name="moderation_actions")
    op.drop_table("moderation_actions")
    op.drop_index("uq_content_reports_one", table_name="content_reports")
    op.drop_index(op.f("ix_content_reports_status_created"), table_name="content_reports")
    op.drop_table("content_reports")
    op.drop_index("uq_bookmarks_report_user", table_name="bookmarks")
    op.drop_table("bookmarks")
    op.drop_table("geography_followers")
    op.drop_table("institution_followers")
    op.drop_index(op.f("ix_posts_geo_created"), table_name="posts")
    op.drop_table("posts")
    op.drop_index("uq_reactions_comment_user", table_name="reactions")
    op.drop_index("uq_reactions_report_user", table_name="reactions")
    op.drop_table("reactions")
