"""Extend the media status CHECK with async 'pending_scan' (Phase 8 worker)

Revision ID: 0009_media_pending_scan
Revises: 0008_notifications
Create Date: 2026-08-15

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_media_pending_scan"
down_revision: str | None = "0008_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = "status IN ('uploading', 'available', 'failed', 'deleted')"
_NEW = "status IN ('uploading', 'pending_scan', 'available', 'failed', 'deleted')"


def upgrade() -> None:
    op.drop_constraint("ck_media_objects_status", "media_objects", type_="check")
    op.create_check_constraint("ck_media_objects_status", "media_objects", _NEW)


def downgrade() -> None:
    op.drop_constraint("ck_media_objects_status", "media_objects", type_="check")
    op.create_check_constraint("ck_media_objects_status", "media_objects", _OLD)
