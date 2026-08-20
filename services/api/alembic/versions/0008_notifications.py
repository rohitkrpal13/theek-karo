"""Notification history + delivery receipts (API.md §9, DATABASE.md §3.8)

Adds the consumer-facing history tables and seeds the hi/en templates +
default preferences (the queue tables themselves live in `0006_ai_ops`).

Revision ID: 0008_notifications
Revises: 0007_ai_reviews
Create Date: 2026-08-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0008_notifications"
down_revision: str | None = "0007_ai_reviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEMPLATES = [
    ("report.status_change", "in_app", "en", "Your report {ticket_no} is now {status_label}"),
    ("report.status_change", "in_app", "hi", "आपकी रिपोर्ट {ticket_no} अब {status_label} है"),
    ("report.status_change", "sms", "en", "Theek Karo: report {ticket_no} is now {status_label}"),
    ("report.status_change", "sms", "hi", "ठीक करो: रिपोर्ट {ticket_no} अब {status_label} है"),
    (
        "report.status_change",
        "email",
        "en",
        "Theek Karo: your report {ticket_no} is now {status_label}",
    ),
    ("report.status_change", "email", "hi", "ठीक करो: आपकी रिपोर्ट {ticket_no} अब {status_label} है"),
    ("report.comment", "in_app", "en", "New comment on {ticket_no}"),
    ("report.comment", "in_app", "hi", "{ticket_no} पर नई टिप्पणी"),
    ("report.verification", "in_app", "en", "New verification on {ticket_no}"),
    ("report.verification", "in_app", "hi", "{ticket_no} पर नया सत्यापन"),
    ("ai.review", "in_app", "en", "AI suggested a duplicate for {ticket_no}"),
    ("ai.review", "in_app", "hi", "AI ने {ticket_no} के लिए डुप्लिकेट सुझाया"),
]


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_notifications_user_created"), "notifications", ["user_id", "created_at"]
    )

    op.create_table(
        "notification_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="sent"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["notification_id"], ["notifications.id"], ondelete="CASCADE"),
    )
    op.create_index(
        op.f("ix_notification_receipts_notification"), "notification_receipts", ["notification_id"]
    )

    # seed templates (idempotent; the table itself is from 0006)
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

    # default preferences for all users: enabled rows per channel + event group
    op.execute(
        sa.text(
            "INSERT INTO notification_preferences (user_id, channel, event_group, enabled) "
            "SELECT u.id, ch.channel, e.group_, true "
            "FROM users u CROSS JOIN (VALUES ('in_app'), ('sms'), ('email')) AS ch(channel) "
            "CROSS JOIN (VALUES ('status_change'), ('collaboration'), ('ai')) AS e(group_) "
            "ON CONFLICT DO NOTHING"
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_receipts_notification"), table_name="notification_receipts")
    op.drop_table("notification_receipts")
    op.drop_index(op.f("ix_notifications_user_created"), table_name="notifications")
    op.drop_table("notifications")
    op.execute(
        sa.text("DELETE FROM notification_preferences WHERE user_id IN (SELECT id FROM users)")
    )
