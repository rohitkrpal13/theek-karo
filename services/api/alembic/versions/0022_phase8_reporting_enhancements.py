"""Phase 8 reporting enhancements: observed_at and coordinate_source (PRD §7, §13).

Revision ID: 0022_phase8_reporting_enhancements
Revises: 0021_identity_roles_permissions
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_phase8_reporting_enhancements"
down_revision: str | None = "0021_identity_roles_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COORD_SOURCES = (
    "coordinate_source IN ('USER_SELECTED', 'DEVICE_LOCATION', "
    "'INSTITUTION_LOCATION', 'MAP_SELECTED', 'IMPORTED') OR coordinate_source IS NULL"
)


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "reports",
        sa.Column("coordinate_source", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_reports_observed_at", "reports", ["observed_at"])
    op.create_check_constraint("ck_reports_coordinate_source", "reports", _COORD_SOURCES)


def downgrade() -> None:
    op.drop_constraint("ck_reports_coordinate_source", "reports", type_="check")
    op.drop_index("ix_reports_observed_at", table_name="reports")
    op.drop_column("reports", "coordinate_source")
    op.drop_column("reports", "observed_at")
