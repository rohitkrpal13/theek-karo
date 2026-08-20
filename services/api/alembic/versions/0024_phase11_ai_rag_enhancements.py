"""Phase 11: AI intelligence, RAG enhancements, and conversation sessions.

Revision ID: 0024_phase11_ai_rag_enhancements
Revises: 0023_phase10_govdata_discrepancies
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0024_phase11_ai_rag_enhancements"
down_revision: str | None = "0023_phase10_govdata_discrepancies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update ai_runs with cost & token tracking
    op.add_column("ai_runs", sa.Column("tokens_in", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("tokens_out", sa.Integer(), nullable=True))
    op.add_column("ai_runs", sa.Column("cost_usd", sa.Numeric(8, 6), nullable=True))
    op.add_column("ai_runs", sa.Column("prompt_version", sa.String(length=64), nullable=True))

    # 2. Update rag_chunks with metadata payload & access control
    op.add_column("rag_chunks", sa.Column("metadata_payload", postgresql.JSONB(), nullable=True))
    op.add_column(
        "rag_chunks",
        sa.Column("access_level", sa.String(length=32), nullable=False, server_default="PUBLIC"),
    )

    # 3. Create ai_conversations table
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_ai_conversations_user", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_session", "ai_conversations", ["session_id"])

    # 4. Create ai_messages table
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_messages_conversation", "ai_messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_messages_conversation", table_name="ai_messages")
    op.drop_table("ai_messages")

    op.drop_index("ix_ai_conversations_session", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_user", table_name="ai_conversations")
    op.drop_table("ai_conversations")

    op.drop_column("rag_chunks", "access_level")
    op.drop_column("rag_chunks", "metadata_payload")

    op.drop_column("ai_runs", "prompt_version")
    op.drop_column("ai_runs", "cost_usd")
    op.drop_column("ai_runs", "tokens_out")
    op.drop_column("ai_runs", "tokens_in")
