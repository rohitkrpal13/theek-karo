"""Fix versioned-key uniqueness for time-travel correctness.

source_records: versions of the same external key must coexist; uniqueness is
now (source_id, external_key, source_version_id).
gov_dataset_records: per-import-job versions; uniqueness is now
(dataset_id, import_job_id, external_key).

Revision ID: 0020_fix_versioning_uniques
Revises: 0019_analytics
Create Date: 2026-08-16

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0020_fix_versioning_uniques"
down_revision: str | None = "0019_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_if_exists(table: str, names: list[str]) -> None:
    """Constraint names vary between fresh (edited) and upgraded paths —
    drop whichever exists, then recreate canonical names."""
    for name in names:
        # DDL helper — table and constraint names are hardcoded at call sites;
        # migrations never interpolate user input.
        # nosemgrep
        op.execute(f'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS "{name}"')


def upgrade() -> None:
    _drop_if_exists(
        "source_records",
        [
            "source_records_source_id_external_key_key",
            "source_records_source_id_external_key_source_version_id_key",
            "uq_source_records_versioned_key",
        ],
    )
    op.create_unique_constraint(
        "uq_source_records_versioned_key",
        "source_records",
        ["source_id", "external_key", "source_version_id"],
    )
    _drop_if_exists(
        "gov_dataset_records",
        [
            "gov_dataset_records_dataset_id_external_key_key",
            "uq_gov_records_job_key",
        ],
    )
    op.create_unique_constraint(
        "uq_gov_records_job_key",
        "gov_dataset_records",
        ["dataset_id", "import_job_id", "external_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_gov_records_job_key", "gov_dataset_records", type_="unique")
    op.create_unique_constraint(
        "gov_dataset_records_dataset_id_external_key_key",
        "gov_dataset_records",
        ["dataset_id", "external_key"],
    )
    op.drop_constraint("uq_source_records_versioned_key", "source_records", type_="unique")
    op.create_unique_constraint(
        "source_records_source_id_external_key_key",
        "source_records",
        ["source_id", "external_key"],
    )
