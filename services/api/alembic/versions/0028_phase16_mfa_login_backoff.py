"""Phase 16 auth hardening: TOTP MFA state + per-account login backoff.

New table: user_mfa (base32 TOTP secret + enabled_at per user).
Extended: users.mfa_enabled (boolean mirror of user_mfa.enabled_at so the
authorization MFA gate needs no join).

Login backoff itself is ephemeral (Redis/in-memory, see
core/login_throttle.py) and needs no schema; the durable audit trail is the
existing security_events LOGIN_FAILURE rows.

Revision ID: 0028_phase16_mfa_login_backoff
Revises: 0027_phase15_public_data
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0028_phase16_mfa_login_backoff"
down_revision: str | None = "0027_phase15_public_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_mfa",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("secret", sa.Text(), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", name="uq_user_mfa_user_id"),
    )
    op.create_index(op.f("ix_user_mfa_user_id"), "user_mfa", ["user_id"])

    op.add_column(
        "users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade() -> None:
    op.drop_column("users", "mfa_enabled")
    op.drop_index(op.f("ix_user_mfa_user_id"), table_name="user_mfa")
    op.drop_table("user_mfa")
