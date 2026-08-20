"""Change detection for external datasets (Phase 19, spec §15).

Every sync diffs the incoming records against the current ``gov_dataset_records``
for the dataset (idempotent: a re-run of the same payload yields
added=removed=modified=0). Counts feed ``gov_import_jobs``
(rows_added/removed/modified/unchanged/rejected) and the admin sync report.

Checksums are computed on the *normalized* canonical payload with sorted keys,
so the same logical record from two deliveries hashes identically.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.govdata.models import GovDatasetRecord

# Hard cap on how many existing keys we load into memory per dataset — datasets
# larger than this are still diffed via the DB (counts + targeted queries are
# batched by the caller). Keeps the common case O(n) in memory.
_MAX_EXISTING_KEYS = 200_000


@dataclass
class DatasetDiff:
    added: list[dict[str, Any]]  # records not seen before
    removed: list[str]  # external keys present before, missing now
    modified: list[dict[str, Any]]  # records with a changed checksum
    unchanged: list[str]  # external keys with identical checksum
    rejected: list[dict[str, Any]]  # records without a stable external key

    @property
    def summary(self) -> dict[str, int]:
        return {
            "rows_added": len(self.added),
            "rows_removed": len(self.removed),
            "rows_modified": len(self.modified),
            "rows_unchanged": len(self.unchanged),
            "rows_rejected": len(self.rejected),
        }

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.modified)


def record_checksum(normalized: dict[str, Any]) -> str:
    """Deterministic checksum of a normalized record (sorted keys)."""
    payload = json.dumps(normalized, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def compute_diff(
    session: AsyncSession,
    *,
    dataset_id: Any,
    incoming: list[dict[str, Any]],
    existing: Sequence[GovDatasetRecord] | None = None,
) -> DatasetDiff:
    """Diff incoming normalized records against the dataset's current rows.

    ``incoming`` entries are normalized dicts that must carry ``external_key``
    (the connector's stable source key). Entries without one are rejected — an
    idempotent import cannot key them.
    """
    if existing is None:
        existing = (
            (
                await session.execute(
                    select(GovDatasetRecord).where(GovDatasetRecord.dataset_id == dataset_id)
                )
            )
            .scalars()
            .all()
        )
    existing = existing[:_MAX_EXISTING_KEYS]

    current: dict[str, str] = {}
    for rec in existing:
        if rec.external_key:
            current[rec.external_key] = record_checksum(rec.data)

    diff = DatasetDiff(added=[], removed=[], modified=[], unchanged=[], rejected=[])
    seen: set[str] = set()

    for record in incoming:
        key = record.get("external_key")
        if not key:
            diff.rejected.append(record)
            continue
        key = str(key)
        seen.add(key)
        checksum = record_checksum(record.get("canonical_data", record))
        if key not in current:
            diff.added.append(record)
        elif current[key] != checksum:
            diff.modified.append(record)
        else:
            diff.unchanged.append(key)

    diff.removed = [k for k in current if k not in seen]
    return diff
