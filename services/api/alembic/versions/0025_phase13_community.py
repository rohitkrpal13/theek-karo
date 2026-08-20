"""Phase 13 community: comment moderation, follows, blocks, notification
grouping + seeds (PRD §8, §15, §20, API.md §9, DATABASE.md §3.8).

* report_comments: edit + moderation lifecycle columns
* new: user_follows, category_followers, user_blocks
* notifications: group_key for grouped delivery ("12 new comments")
* notification_preferences: locked flag (security events are not disableable)
* seeds: community templates (hi/en) + community/security/system prefs

Revision ID: 0025_phase13_community
Revises: 0024_phase11_ai_rag_enhancements
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0025_phase13_community"
down_revision: str | None = "0024_phase11_ai_rag_enhancements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEMPLATES = [
    ("community.reply", "in_app", "en", "New reply to your comment on {ticket_no}"),
    ("community.reply", "in_app", "hi", "आपकी टिप्पणी पर {ticket_no} में नया उत्तर"),
    ("community.mention", "in_app", "en", "You were mentioned on {ticket_no}"),
    ("community.mention", "in_app", "hi", "{ticket_no} पर आपका उल्लेख हुआ"),
    ("community.reaction", "in_app", "en", "Someone reacted to your report {ticket_no}"),
    ("community.reaction", "in_app", "hi", "किसी ने आपकी रिपोर्ट {ticket_no} पर प्रतिक्रिया दी"),
    ("community.follow", "in_app", "en", "New follower for you"),
    ("community.follow", "in_app", "hi", "आपका नया अनुयायी"),
]


def upgrade() -> None:
    # -- report_comments: edit + moderation lifecycle -------------------------
    op.add_column(
        "report_comments",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_comments",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "report_comments",
        sa.Column("is_removed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "report_comments",
        sa.Column("removed_by", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "report_comments",
        sa.Column("removal_reason", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_comments_removed_by",
        "report_comments",
        "users",
        ["removed_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_report_comments_parent_id"), "report_comments", ["parent_id"])

    # -- user follows ----------------------------------------------------------
    op.create_table(
        "user_follows",
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("following_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("follower_id", "following_id"),
        sa.CheckConstraint("follower_id <> following_id", name="ck_user_follows_not_self"),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["following_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_follows_following"), "user_follows", ["following_id"])

    # -- category follows -------------------------------------------------------
    op.create_table(
        "category_followers",
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("category_id", "user_id"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )

    # -- user blocks ------------------------------------------------------------
    op.create_table(
        "user_blocks",
        sa.Column("blocker_id", sa.Uuid(), nullable=False),
        sa.Column("blocked_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("blocker_id", "blocked_id"),
        sa.CheckConstraint("blocker_id <> blocked_id", name="ck_user_blocks_not_self"),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(op.f("ix_user_blocks_blocked"), "user_blocks", ["blocked_id"])

    # -- notifications: grouping support ----------------------------------------
    op.add_column(
        "notifications",
        sa.Column("group_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        op.f("ix_notifications_user_group"), "notifications", ["user_id", "group_key", "read_at"]
    )
    op.add_column(
        "notification_queue",
        sa.Column("group_key", sa.String(length=128), nullable=True),
    )

    # -- preferences: locked rows (security events cannot be disabled) ----------
    op.add_column(
        "notification_preferences",
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # -- seeds -------------------------------------------------------------------
    events = sa.table(
        "notification_templates",
        sa.column("id", sa.Uuid()),
        sa.column("event", sa.String()),
        sa.column("channel", sa.String()),
        sa.column("locale", sa.String()),
        sa.column("subject_key", sa.Text()),
        sa.column("body_text", sa.Text()),
        sa.column("created_at", sa.DateTime()),
    )
    for event, channel, locale, body in _TEMPLATES:
        op.execute(
            events.insert().from_select(
                ["id", "event", "channel", "locale", "subject_key", "body_text", "created_at"],
                sa.select(
                    sa.func.gen_random_uuid(),
                    sa.literal(event),
                    sa.literal(channel),
                    sa.literal(locale),
                    sa.literal(f"notification.{event}.{channel}.{locale}"),
                    sa.literal(body),
                    sa.func.now(),
                ).where(
                    ~sa.exists(
                        sa.select(sa.literal(1)).where(
                            events.c.event == event,
                            events.c.channel == channel,
                            events.c.locale == locale,
                        )
                    )
                ),
            )
        )

    # community + system prefs (default on); security prefs default on + locked
    op.execute(
        sa.text(
            "INSERT INTO notification_preferences (user_id, channel, event_group, enabled, locked) "
            "SELECT u.id, ch.channel, e.group_, true, e.locked "
            "FROM users u "
            "CROSS JOIN (VALUES ('in_app'), ('sms'), ('email')) AS ch(channel) "
            "CROSS JOIN (VALUES ('community', false), ('system', false), ('security', true)) "
            "AS e(group_, locked) "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM notification_preferences "
            "WHERE event_group IN ('community', 'system', 'security')"
        )
    )
    op.execute(sa.text("DELETE FROM notification_templates WHERE event LIKE 'community.%'"))
    op.drop_column("notification_preferences", "locked")
    op.drop_index(op.f("ix_notifications_user_group"), table_name="notifications")
    op.drop_column("notifications", "group_key")
    op.drop_column("notification_queue", "group_key")
    op.drop_index(op.f("ix_user_blocks_blocked"), table_name="user_blocks")
    op.drop_table("user_blocks")
    op.drop_table("category_followers")
    op.drop_index(op.f("ix_user_follows_following"), table_name="user_follows")
    op.drop_table("user_follows")
    op.drop_index(op.f("ix_report_comments_parent_id"), table_name="report_comments")
    op.drop_constraint("fk_report_comments_removed_by", "report_comments", type_="foreignkey")
    op.drop_column("report_comments", "removal_reason")
    op.drop_column("report_comments", "removed_by")
    op.drop_column("report_comments", "is_removed")
    op.drop_column("report_comments", "edited_at")
    op.drop_column("report_comments", "updated_at")
