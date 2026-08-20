"""Phase 15 community confirmation on resolved cases (PRD §B.2).

Adds the citizen follow-up layer over independently-reviewed resolutions:

* ``resolution_followups`` — one citizen signal per case ("I observed the
  improvement" / "Issue still exists"); unique per (case, user) so a user
  cannot signal twice; status lifecycle ``pending -> confirmed | escalated |
  dismissed``.
* **Two-confirmer gate** — when N distinct citizens confirm the improvement
  (default 2; the reporter counts), the confirmations are marked ``confirmed``
  and ``cases.community_confirmed_at`` is set. The resolution reviewer then
  closes the case through the existing ``resolved -> closed`` transition.
* **Reopen signal** — when N distinct citizens report the issue persists
  (default 3), the followups are escalated and a ``resolution_reopen_signals``
  row is created for the department/reviewer queue. Approving it reopens the
  case through the existing reopen-request machinery (never auto-reopens).

Also seeds the hi/en notification templates for the three new events.

Pure additive; the downgrade drops the tables/column/templates.

Revision ID: 0031_phase15_community_confirmation
Revises: 0030_step9_indexes_pool
Create Date: 2026-08-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0031_phase15_community_confirmation"
down_revision: str | None = "0030_step9_indexes_pool"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEMPLATES = [
    (
        "resolution.followup_confirmed",
        "in_app",
        "en",
        "Community confirmed the resolution on case {case_no} — ready to close",
    ),
    (
        "resolution.followup_confirmed",
        "in_app",
        "hi",
        "केस {case_no} के समाधान की सामुदायिक पुष्टि हुई — बंद करने हेतु तैयार",
    ),
    (
        "resolution.reopen_signal",
        "in_app",
        "en",
        "{count} citizens report the issue still exists on case {case_no}",
    ),
    (
        "resolution.reopen_signal",
        "in_app",
        "hi",
        "{count} नागरिकों ने बताया कि केस {case_no} में समस्या अब भी बनी हुई है",
    ),
    (
        "resolution.reopen_approved",
        "in_app",
        "en",
        "Case {case_no} was reopened after community follow-up",
    ),
    (
        "resolution.reopen_approved",
        "in_app",
        "hi",
        "सामुदायिक अनुवर्तन के बाद केस {case_no} फिर से खोला गया",
    ),
]


def upgrade() -> None:
    op.create_table(
        "resolution_followups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("report_id", sa.Uuid(), nullable=False),
        sa.Column("resolution_submission_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("signal", sa.String(length=24), nullable=False),
        sa.Column("observation", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "user_id", name="uq_resolution_followups_case_user"),
        sa.CheckConstraint(
            "signal IN ('observed_improvement', 'issue_still_exists')",
            name="ck_resolution_followups_signal",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'escalated', 'dismissed')",
            name="ck_resolution_followups_status",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["resolution_submission_id"], ["resolution_submissions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_resolution_followups_report_created"),
        "resolution_followups",
        ["report_id", "created_at"],
    )
    op.create_index(
        op.f("ix_resolution_followups_case_status"),
        "resolution_followups",
        ["case_id", "status"],
    )

    op.create_table(
        "resolution_reopen_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.Column("raised_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'dismissed')",
            name="ck_resolution_reopen_signals_status",
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["raised_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        op.f("ix_resolution_reopen_signals_status_created"),
        "resolution_reopen_signals",
        ["status", "created_at"],
    )

    op.add_column(
        "cases",
        sa.Column("community_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- notification template seeds (hi/en) -----------------------------------
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


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM notification_templates "
            "WHERE event IN ('resolution.followup_confirmed', 'resolution.reopen_signal', "
            "'resolution.reopen_approved')"
        )
    )
    op.drop_column("cases", "community_confirmed_at")
    op.drop_index(
        op.f("ix_resolution_reopen_signals_status_created"),
        table_name="resolution_reopen_signals",
    )
    op.drop_table("resolution_reopen_signals")
    op.drop_index(op.f("ix_resolution_followups_case_status"), table_name="resolution_followups")
    op.drop_index(op.f("ix_resolution_followups_report_created"), table_name="resolution_followups")
    op.drop_table("resolution_followups")
