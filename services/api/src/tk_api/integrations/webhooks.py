"""Transactional outbox + signed outgoing webhooks (Phase 19, spec §57-§59).

Design (ADR-057):

- ``emit_outbox_event`` writes one ``OutboxEvent`` row **inside the caller's
  transaction** (same commit as the domain action), so external delivery can
  never diverge from committed state and a crashed worker cannot lose events.
- ``dispatch_due_webhooks`` (worker beat) polls due events, fans out to active
  matching subscriptions, and delivers with an HMAC-SHA256 signature
  (``X-TK-Signature`` = ``t=<ts>,v1=<hmac>``) plus a timestamp for replay
  protection. The signing key is *derived* per subscription
  (``HKDF(webhook_master_secret, secret_key_id)``) so the raw secret is never
  persisted.
- Retries use exponential backoff with jitter, capped by
  ``webhook_max_attempts``; exhausted deliveries dead-letter (status ``DEAD``)
  and are visible in the admin delivery log. No secrets are ever logged.

Core Theek Karo functionality never depends on delivery success: dispatch
failures only mutate outbox/delivery rows.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import random
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.config import Settings, get_settings
from tk_api.govdata.connectors import ConnectorSecurityError, validate_source_url
from tk_api.integrations.models import (
    OutboxEvent,
    WebhookDelivery,
    WebhookSubscription,
)

logger = logging.getLogger("tk_api.integrations.webhooks")

# Allowed outgoing event names (spec §57). Anything else is rejected at emit.
VALID_EVENTS = frozenset(
    {
        "report.created",
        "report.updated",
        "evidence.added",
        "department.response_submitted",
        "resolution.submitted",
        "resolution.verified",
        "institution.updated",
        "dataset.updated",
    }
)

# Replay-protection window for inbound verification of the timestamp header.
_MAX_TS_SKEW_SECONDS = 300

_OUTBOX_PENDING = "PENDING"
_OUTBOX_DELIVERING = "DELIVERING"
_OUTBOX_DELIVERED = "DELIVERED"
_OUTBOX_FAILED = "FAILED"
_OUTBOX_DEAD = "DEAD"

_DELIVERY_PENDING = "PENDING"
_DELIVERY_SUCCESS = "SUCCESS"
_DELIVERY_FAILED = "FAILED"
_DELIVERY_DEAD = "DEAD"


class WebhookError(Exception):
    """Raised for invalid subscriptions / events / URLs."""


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _settings() -> Settings:
    return get_settings()


# ---------------------------------------------------------------------------
# Signing (per-subscription derived key, replay protection)
# ---------------------------------------------------------------------------


def derive_signing_key(master_secret: str, secret_key_id: str) -> bytes:
    """HKDF-style derived per-subscription HMAC key (never store the raw key)."""
    info = b"tk-webhook-v1"
    return hmac.new(
        master_secret.encode("utf-8"), secret_key_id.encode("utf-8") + info, hashlib.sha256
    ).digest()


def sign_payload(master_secret: str, secret_key_id: str, payload: bytes, timestamp: int) -> str:
    key = derive_signing_key(master_secret, secret_key_id)
    message = f"{timestamp}.{payload.decode('utf-8')}".encode()
    digest = hmac.new(key, message, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_signature(
    master_secret: str, secret_key_id: str, payload: bytes, header: str, *, now: int | None = None
) -> bool:
    """Verify an inbound signature with replay protection."""
    try:
        parts = dict(pair.split("=", 1) for pair in header.split(","))
        timestamp = int(parts["t"])
        digest = parts["v1"]
    except (KeyError, ValueError):
        return False
    now = now or int(datetime.now(UTC).timestamp())
    if abs(now - timestamp) > _MAX_TS_SKEW_SECONDS:
        return False
    expected = sign_payload(master_secret, secret_key_id, payload, timestamp).split(",v1=")[1]
    return hmac.compare_digest(digest, expected)


# ---------------------------------------------------------------------------
# Outbox (written in-transaction by domain actions)
# ---------------------------------------------------------------------------


async def emit_outbox_event(
    session: AsyncSession,
    *,
    event: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> OutboxEvent:
    """Create an outbox row *within the caller's transaction*.

    The row is flushed but not committed — it commits atomically with the
    domain change (outbox pattern, spec §59).
    """
    if event not in VALID_EVENTS:
        raise WebhookError(f"event '{event}' is not a supported webhook event")
    row = OutboxEvent(
        event=event,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        status=_OUTBOX_PENDING,
        next_attempt_at=_utcnow(),
    )
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# Subscriptions (admin CRUD + SSRF-safe URL validation)
# ---------------------------------------------------------------------------


def validate_webhook_url(url: str) -> str:
    """Validate an outgoing webhook target URL (SSRF-safe, https required)."""
    if not url.lower().startswith("https://"):
        raise WebhookError("webhook URLs must use https://")
    try:
        return validate_source_url(url)
    except ConnectorSecurityError as exc:
        raise WebhookError(f"webhook URL rejected: {exc}") from exc


def new_secret_key_id() -> str:
    return secrets.token_urlsafe(16)


async def create_subscription(
    session: AsyncSession,
    *,
    name: str,
    url: str,
    events: list[str],
    created_by: uuid.UUID | None,
) -> WebhookSubscription:
    invalid = [e for e in events if e not in VALID_EVENTS]
    if invalid:
        raise WebhookError(f"unsupported event(s): {', '.join(invalid)}")
    if not events:
        raise WebhookError("at least one event is required")
    url = validate_webhook_url(url)
    sub = WebhookSubscription(
        name=name.strip(),
        url=url,
        events=events,
        secret_key_id=new_secret_key_id(),
        status="active",
        created_by=created_by,
    )
    session.add(sub)
    await session.flush()
    return sub


async def list_subscriptions(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(WebhookSubscription).order_by(WebhookSubscription.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "url": s.url,
            "events": s.events or [],
            "status": s.status,
            "secret_key_id": s.secret_key_id,  # identifier only, never the key
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]


# ---------------------------------------------------------------------------
# Dispatch (worker)
# ---------------------------------------------------------------------------


async def dispatch_due_webhooks(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, int]:
    """Deliver due outbox events to matching active subscriptions.

    Called by the worker beat. Returns counts: ``delivered``, ``failed``,
    ``dead``, ``events_processed``. Never raises on delivery failure.
    """
    settings = settings or _settings()
    now = _utcnow()
    due_events = (
        (
            await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status.in_((_OUTBOX_PENDING, _OUTBOX_FAILED)),
                    OutboxEvent.next_attempt_at.is_(None) | (OutboxEvent.next_attempt_at <= now),
                )
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    if not due_events:
        return {"delivered": 0, "failed": 0, "dead": 0, "events_processed": 0}

    subs = (
        (
            await session.execute(
                select(WebhookSubscription).where(WebhookSubscription.status == "active")
            )
        )
        .scalars()
        .all()
    )
    subs_by_event: dict[str, list[WebhookSubscription]] = {}
    for sub in subs:
        for event in sub.events or []:
            subs_by_event.setdefault(event, []).append(sub)

    counts = {"delivered": 0, "failed": 0, "dead": 0, "events_processed": 0}
    for event in due_events:
        counts["events_processed"] += 1
        matches = subs_by_event.get(event.event, [])
        if not matches:
            event.status = _OUTBOX_DELIVERED  # nothing to deliver
            event.delivered_at = now
            event.next_attempt_at = None
            await session.flush()
            continue
        for sub in matches:
            delivery = await _get_or_create_delivery(session, sub.id, event.id)
            if delivery is None:
                continue  # already delivered for this subscription
            await _attempt_delivery(session, event, sub, delivery, settings, client)
            if delivery.status == _DELIVERY_SUCCESS:
                counts["delivered"] += 1
            elif delivery.status == _DELIVERY_DEAD:
                counts["dead"] += 1
            else:
                counts["failed"] += 1
        # If every matching subscription is terminal, mark the event done.
        if await _all_deliveries_terminal(session, event.id):
            event.status = _OUTBOX_DELIVERED
            event.delivered_at = now
            event.next_attempt_at = None
            await session.flush()
    await session.commit()
    return counts


async def _get_or_create_delivery(
    session: AsyncSession, subscription_id: uuid.UUID, event_id: uuid.UUID
) -> WebhookDelivery | None:
    existing = await session.scalar(
        select(WebhookDelivery).where(
            WebhookDelivery.subscription_id == subscription_id,
            WebhookDelivery.outbox_event_id == event_id,
        )
    )
    if existing is not None:
        if existing.status == _DELIVERY_SUCCESS:
            return None
        return existing
    delivery = WebhookDelivery(
        subscription_id=subscription_id,
        outbox_event_id=event_id,
        status=_DELIVERY_PENDING,
        next_attempt_at=_utcnow(),
    )
    session.add(delivery)
    await session.flush()
    return delivery


async def _all_deliveries_terminal(session: AsyncSession, event_id: uuid.UUID) -> bool:
    """True when no delivery for this event is still pending retry
    (non-terminal: PENDING or FAILED with a future attempt)."""
    pending = await session.scalar(
        select(WebhookDelivery.id)
        .where(
            WebhookDelivery.outbox_event_id == event_id,
            WebhookDelivery.status.in_((_DELIVERY_PENDING, _DELIVERY_FAILED)),
        )
        .limit(1)
    )
    return pending is None


async def _attempt_delivery(
    session: AsyncSession,
    event: OutboxEvent,
    sub: WebhookSubscription,
    delivery: WebhookDelivery,
    settings: Settings,
    client: httpx.AsyncClient | None,
) -> None:
    delivery.attempts = (delivery.attempts or 0) + 1
    if delivery.attempts > settings.webhook_max_attempts:
        delivery.status = _DELIVERY_DEAD
        delivery.last_error = "max attempts exceeded"
        delivery.next_attempt_at = None
        await session.flush()
        return

    body = json.dumps(
        {
            "event": event.event,
            "aggregate_type": event.aggregate_type,
            "aggregate_id": str(event.aggregate_id) if event.aggregate_id else None,
            "payload": event.payload,
            "sent_at": datetime.now(UTC).isoformat(),
        },
        default=str,
    ).encode("utf-8")
    if len(body) > settings.webhook_max_body_bytes:
        delivery.status = _DELIVERY_DEAD
        delivery.last_error = "payload exceeds webhook_max_body_bytes"
        delivery.next_attempt_at = None
        await session.flush()
        return

    timestamp = int(datetime.now(UTC).timestamp())
    signature = sign_payload(settings.webhook_master_secret, sub.secret_key_id, body, timestamp)
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "TheekKaro-Webhook/1.0",
        "X-TK-Signature": signature,
        "X-TK-Event": event.event,
        "X-TK-Webhook-Id": str(sub.id),
    }

    try:
        async with client or httpx.AsyncClient(
            timeout=settings.webhook_timeout_seconds, follow_redirects=False
        ) as http:
            resp = await http.post(sub.url, content=body, headers=headers)
        delivery.http_status = resp.status_code
        if 200 <= resp.status_code < 300:
            delivery.status = _DELIVERY_SUCCESS
            delivery.last_error = None
            delivery.next_attempt_at = None
            event.status = _OUTBOX_DELIVERING
        else:
            _mark_retry(delivery, f"http {resp.status_code}", settings)
    except Exception as exc:  # network/timeout — transient, retry
        _mark_retry(delivery, f"{type(exc).__name__}: {exc}", settings)
    await session.flush()


def _mark_retry(delivery: WebhookDelivery, error: str, settings: Settings) -> None:
    delivery.status = _DELIVERY_FAILED
    delivery.last_error = error[:2000]
    delay = min(settings.webhook_base_delay_seconds * (2 ** (delivery.attempts - 1)), 3600)
    # Retry jitter — non-security randomness (delivery timing only)
    jitter = random.uniform(0.5, 1.5)  # nosec B311
    delivery.next_attempt_at = _utcnow() + timedelta(seconds=delay * jitter)


async def get_delivery_log(
    session: AsyncSession, *, limit: int = 50, subscription_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    stmt = select(WebhookDelivery, WebhookSubscription).join(
        WebhookSubscription, WebhookDelivery.subscription_id == WebhookSubscription.id
    )
    if subscription_id:
        stmt = stmt.where(WebhookDelivery.subscription_id == subscription_id)
    stmt = stmt.order_by(WebhookDelivery.created_at.desc()).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(d.id),
            "subscription_id": str(d.subscription_id),
            "subscription_name": s.name,
            "outbox_event_id": str(d.outbox_event_id),
            "status": d.status,
            "http_status": d.http_status,
            "attempts": d.attempts,
            "next_attempt_at": d.next_attempt_at.isoformat() if d.next_attempt_at else None,
            "last_error": d.last_error,
            "created_at": d.created_at.isoformat(),
        }
        for d, s in rows
    ]
