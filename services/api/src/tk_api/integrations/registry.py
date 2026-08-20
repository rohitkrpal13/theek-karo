"""Connector registry: health tracking, circuit breaker, and freshness.

Phase 19 (spec §36-§37, §80-§81): external failures must never cascade into
the core application. Every sync records health on ``IntegrationConnector``
and the breaker state is applied *before* a fetch is attempted:

- **HEALTHY** → a sync attempt starts.
- **DEGRADED** — ``consecutive_failures >= threshold`` but still under the
  cooldown window; new syncs are refused (fail fast) instead of hammering an
  unhealthy provider.
- **CIRCUIT_OPEN** — cooldown elapsed; a sync attempt opens the circuit in
  ``RECOVERING`` (half-open) and is allowed to probe.
- **RECOVERING** — success returns to HEALTHY; failure re-opens the circuit
  (CIRCUIT_OPEN) for another cooldown.

Freshness (spec §13) is derived from ``last_success_at`` vs the connector's
expected update frequency: FRESH / RECENT / STALE / UNKNOWN / UNAVAILABLE.
No secrets are ever stored on the row (ADR-057).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.integrations.models import IntegrationConnector

# Circuit breaker states
HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
CIRCUIT_OPEN = "CIRCUIT_OPEN"
RECOVERING = "RECOVERING"
UNKNOWN = "UNKNOWN"

# Freshness states (spec §13)
FRESH = "FRESH"
RECENT = "RECENT"
STALE = "STALE"
UNKNOWN_FRESHNESS = "UNKNOWN"
UNAVAILABLE = "UNAVAILABLE"

_CONNECTOR_NOT_FOUND = "connector_not_found"


class ConnectorError(Exception):
    """Raised for registry-level failures (unknown code, circuit open)."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """Normalize SQLite's naive datetimes to UTC-aware for comparisons."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def get_connector_row(
    session: AsyncSession, code: str, *, for_update: bool = False
) -> IntegrationConnector | None:
    """Fetch a connector row by registry code (the key in connectors.py).
    Returns ``None`` when the adapter has no registry row yet (legacy datasets,
    tests) — callers degrade gracefully instead of failing the import."""
    stmt = select(IntegrationConnector).where(IntegrationConnector.code == code)
    if for_update:
        stmt = stmt.with_for_update()
    row = await session.scalar(stmt)
    if row is not None and not isinstance(row, IntegrationConnector):  # pragma: no cover
        return None
    return row


def _update(conn: IntegrationConnector, **fields: Any) -> None:
    for key, value in fields.items():
        setattr(conn, key, value)
    conn.updated_at = _utcnow()


async def record_sync_start(session: AsyncSession, code: str) -> IntegrationConnector | None:
    """Validate the circuit allows a sync and mark the attempt.

    Raises :class:`ConnectorError` with a fail-fast message when the breaker
    is DEGRADED (within cooldown). In RECOVERING (half-open probe) or any
    other state the attempt proceeds. Returns ``None`` when the connector has
    no registry row (no breaker to consult — import proceeds).
    """
    conn = await get_connector_row(session, code, for_update=True)
    if conn is None:
        return None
    now = _utcnow()
    if conn.status == DEGRADED:
        from tk_api.core.config import get_settings

        if conn.last_failure_at is not None:
            cooldown_until = _aware(conn.last_failure_at) + timedelta(
                seconds=int(get_settings().connector_cooldown_seconds)
            )
            if now < cooldown_until:
                raise ConnectorError(
                    f"connector '{code}' is DEGRADED (circuit open); retry after "
                    f"{cooldown_until.isoformat()}",
                )
        # Cooldown elapsed -> half-open probe
        _update(conn, status=RECOVERING, last_error=None)
    elif conn.status == CIRCUIT_OPEN:
        _update(conn, status=RECOVERING, last_error=None)
    conn.last_sync_at = now
    await session.flush()
    return conn


async def record_sync_success(
    session: AsyncSession, code: str, *, records_imported: int, records_rejected: int
) -> IntegrationConnector | None:
    """Mark a successful sync: reset failures, close the circuit."""
    conn = await get_connector_row(session, code, for_update=True)
    if conn is None:
        return None
    now = _utcnow()
    _update(
        conn,
        status=HEALTHY,
        consecutive_failures=0,
        last_success_at=now,
        last_failure_at=None,
        last_error=None,
        records_imported=(conn.records_imported or 0) + max(records_imported, 0),
        records_rejected=(conn.records_rejected or 0) + max(records_rejected, 0),
    )
    await session.flush()
    return conn


async def record_sync_failure(
    session: AsyncSession,
    code: str,
    *,
    error: str,
    retry_after_until: datetime | None = None,
) -> IntegrationConnector | None:
    """Record a failure and move the circuit: HEALTHY → DEGRADED when the
    consecutive-failure threshold is crossed, DEGRADED → CIRCUIT_OPEN when
    cooldown is exhausted, RECOVERING (probe failure) → CIRCUIT_OPEN."""
    from tk_api.core.config import get_settings

    settings = get_settings()
    conn = await get_connector_row(session, code, for_update=True)
    if conn is None:
        return None
    now = _utcnow()
    conn.consecutive_failures = (conn.consecutive_failures or 0) + 1
    conn.last_failure_at = now
    conn.last_error = (error or "")[:2000]
    if retry_after_until is not None:
        conn.retry_after_until = retry_after_until
    if conn.consecutive_failures >= settings.connector_failure_threshold:
        conn.status = DEGRADED if conn.status != RECOVERING else CIRCUIT_OPEN
    _update(conn, status=conn.status)  # bumps updated_at
    await session.flush()
    return conn


async def health_of(session: AsyncSession, code: str) -> dict[str, Any]:
    """Compute the health summary for one connector (admin /health view)."""
    conn = await get_connector_row(session, code)
    if conn is None:
        return {"code": code, "name": code, "status": UNKNOWN, "freshness": UNKNOWN_FRESHNESS}
    return connector_health_dict(conn)


async def list_connectors(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        (await session.execute(select(IntegrationConnector).order_by(IntegrationConnector.code)))
        .scalars()
        .all()
    )
    return [connector_health_dict(c) for c in rows]


def connector_health_dict(conn: IntegrationConnector) -> dict[str, Any]:
    """Public-safe health/freshness summary for a connector row."""
    now = _utcnow()
    freq_h = conn.sync_frequency_hours or 24
    freshness = _freshness(conn, now, freq_h)
    return {
        "code": conn.code,
        "name": conn.name,
        "provider": conn.provider,
        "category": conn.category,
        "auth_type": conn.auth_type,
        "endpoint": conn.endpoint,
        "version": conn.version,
        "status": conn.status,
        "consecutive_failures": conn.consecutive_failures,
        "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        "last_success_at": conn.last_success_at.isoformat() if conn.last_success_at else None,
        "last_failure_at": conn.last_failure_at.isoformat() if conn.last_failure_at else None,
        "last_error": conn.last_error,
        "retry_after_until": conn.retry_after_until.isoformat() if conn.retry_after_until else None,
        "records_imported": conn.records_imported or 0,
        "records_rejected": conn.records_rejected or 0,
        "sync_frequency_hours": conn.sync_frequency_hours,
        "schema_fingerprint": conn.schema_fingerprint,
        "freshness": freshness,
        "config": conn.config or {},
    }


def _freshness(conn: IntegrationConnector, now: datetime, freq_hours: int) -> str:
    if conn.status in (CIRCUIT_OPEN, DEGRADED):
        return UNAVAILABLE
    last = conn.last_success_at
    if last is None:
        return UNKNOWN_FRESHNESS
    age = now - last
    if age <= timedelta(hours=freq_hours):
        return FRESH
    if age <= timedelta(hours=freq_hours * 2):
        return RECENT
    return STALE


async def get_or_create_connector_row(
    session: AsyncSession,
    code: str,
    *,
    name: str,
    provider: str | None,
    category: str | None,
    auth_type: str,
    endpoint: str | None,
    version: str | None,
    config: dict[str, Any] | None = None,
) -> IntegrationConnector:
    """Ensure a connector row exists (used by the registry seed / fallback)."""
    row = await session.scalar(
        select(IntegrationConnector).where(IntegrationConnector.code == code)
    )
    if row is None:
        row = IntegrationConnector(
            code=code,
            name=name,
            provider=provider,
            category=category,
            auth_type=auth_type,
            endpoint=endpoint,
            version=version,
            status=UNKNOWN,
            config=config or {},
        )
        session.add(row)
        await session.flush()
    return row


async def record_schema_fingerprint(session: AsyncSession, code: str, fingerprint: str) -> None:
    conn = await get_connector_row(session, code)
    if conn is None:
        return
    conn.schema_fingerprint = fingerprint
    conn.updated_at = _utcnow()
    await session.flush()
