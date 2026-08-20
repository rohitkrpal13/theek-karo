"""Schema drift detection (Phase 19, spec §72-§73).

When an external source changes its schema the pipeline must detect it, alert,
and stop unsafe processing rather than silently importing malformed data.

``schema_fingerprint`` on ``integration_connectors`` stores the canonical
fingerprint of the last *successful* import. A sync whose payload produces a
different fingerprint is flagged (``gov_import_jobs.schema_drift_flagged``)
and — unless the operator explicitly forces it — the import is stopped so a
human reviews the connector before resuming.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.integrations import registry

# How many records we sample to build the fingerprint (avoids reading an
# arbitrarily large payload into memory).
_FINGERPRINT_SAMPLE = 200


def compute_fingerprint(records: list[dict[str, Any]]) -> str:
    """Canonical schema fingerprint: sorted union of field names + value types
    observed in the sampled records."""
    keys: set[str] = set()
    types: set[tuple[str, str]] = set()
    for rec in records[:_FINGERPRINT_SAMPLE]:
        if not isinstance(rec, dict):
            continue
        for key, value in rec.items():
            keys.add(key)
            types.add((key, _value_type(value)))
    payload = json.dumps(
        {"keys": sorted(keys), "types": sorted(types)}, sort_keys=True, default=str
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def _value_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


async def check_schema_drift(
    session: AsyncSession,
    *,
    connector_code: str,
    records: list[dict[str, Any]],
    force: bool = False,
) -> tuple[bool, str]:
    """Compare the payload fingerprint against the connector's stored one.

    Returns ``(drifted, fingerprint)``. ``force=True`` (operator override)
    always accepts the payload and updates the stored fingerprint. A brand-new
    connector (no stored fingerprint) is not considered drifted.
    """
    fingerprint = compute_fingerprint(records)
    conn = await registry.get_connector_row(session, connector_code)
    if conn is None:
        # Connector not in the registry yet (legacy dataset / first import):
        # cannot judge drift — treat as no drift so the import can run, but
        # record the fingerprint on the next successful sync.
        return False, fingerprint

    previous = conn.schema_fingerprint
    if force or previous is None or previous == fingerprint:
        if previous != fingerprint:
            await registry.record_schema_fingerprint(session, connector_code, fingerprint)
        return False, fingerprint
    return True, fingerprint
