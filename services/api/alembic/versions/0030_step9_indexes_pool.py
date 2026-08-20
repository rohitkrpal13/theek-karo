"""Step 9 database hardening: hot-path composite indexes.

Adds indexes that the feed/list/notification/inbox queries and the media
visibility gate actually use (Step 9 index audit):

- reports: (visibility, deleted_at, created_at) for public feeds,
  (boundary_id, created_at) for the geography tab, plus single-column
  category_id/reporter_id (category filtering, my-reports).
- report_evidence.media_object_id — the media → evidence visibility lookup
  runs on every media/object read (Phase 16 IDOR gate).
- reactions (report_id, kind) — feed/verification aggregate counts.
- notifications (user_id, created_at) — inbox newest-first queries.

These match the ORM model declarations so fresh databases (create_all) and
migrated Postgres stay identical. All CREATE INDEX ... IF NOT EXISTS; the
downgrade drops them. Pure additive — safe to deploy while live.

Revision ID: 0030_step9_indexes_pool
Revises: 0029_phase18_community_layer
Create Date: 2026-08-18

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0030_step9_indexes_pool"
down_revision: str | None = "0029_phase18_community_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES: list[tuple[str, str, list[str]]] = [
    ("ix_reports_feed", "reports", ["visibility", "deleted_at", "created_at"]),
    ("ix_reports_boundary_created", "reports", ["boundary_id", "created_at"]),
    ("ix_reports_category_id", "reports", ["category_id"]),
    ("ix_reports_reporter_id", "reports", ["reporter_id"]),
    ("ix_report_evidence_media_object_id", "report_evidence", ["media_object_id"]),
    ("ix_reactions_report_kind", "reactions", ["report_id", "kind"]),
    ("ix_notifications_user_created", "notifications", ["user_id", "created_at"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    for name, table, columns in _INDEXES:
        if bind.dialect.name == "postgresql":
            # DDL migration: index/table/column names come from the module-level
            # _INDEXES constant; Postgres cannot bind identifiers — migrations
            # never interpolate user input.
            op.execute(
                sa.text(  # nosemgrep
                    f'CREATE INDEX IF NOT EXISTS "{name}" ON {table} ({", ".join(columns)})'
                )
            )
        else:
            op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _columns in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
