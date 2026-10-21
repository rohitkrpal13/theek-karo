"""Real-time event broadcasting and pubsub engine (PRD §5, §15).

Provides:
- In-memory event bus for local dev, tests, and resilient fallback.
- Redis Pub/Sub integration on channel `tk:live`.
- Non-blocking `broadcast_live_event` helper.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI
from starlette.requests import Request

logger = logging.getLogger("tk_api.events")

LIVE_CHANNEL = "tk:live"


class InMemoryEventBus:
    """Lightweight in-memory event broadcaster for local development and test environments."""

    def __init__(self, max_subscribers: int = 500, queue_size: int = 100) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._max_subscribers = max_subscribers
        self._queue_size = queue_size
        self._lock = asyncio.Lock()

    async def register(self) -> asyncio.Queue[dict[str, Any]]:
        async with self._lock:
            if len(self._subscribers) >= self._max_subscribers:
                # Evict oldest or reject to avoid unbounded memory
                oldest = next(iter(self._subscribers))
                self._subscribers.discard(oldest)
            q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self._queue_size)
            self._subscribers.add(q)
            return q

    async def unregister(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            self._subscribers.discard(q)

    async def publish(self, event: str, data: dict[str, Any], event_id: str | None = None) -> int:
        event_identifier = event_id or str(uuid.uuid4())
        payload = {
            "id": event_identifier,
            "event": event,
            "data": data,
            "timestamp": time.time(),
        }
        async with self._lock:
            active = list(self._subscribers)

        dispatched = 0
        for q in active:
            try:
                q.put_nowait(payload)
                dispatched += 1
            except asyncio.QueueFull:
                # Discard slow consumer event to avoid backpressure
                pass
        return dispatched


def get_event_bus(app: FastAPI) -> InMemoryEventBus:
    """Retrieve or initialize the in-memory event bus on application state."""
    bus = getattr(app.state, "event_bus", None)
    if bus is None:
        bus = InMemoryEventBus()
        app.state.event_bus = bus
    return bus  # type: ignore[no-any-return]


async def broadcast_live_event(
    target: Request | FastAPI | None,
    event: str,
    data: dict[str, Any],
    event_id: str | None = None,
) -> None:
    """Broadcast a real-time event to both Redis Pub/Sub and in-memory listeners.

    Never raises an exception — non-blocking so primary business operations
    are never disrupted by event publication errors.
    """
    if target is None:
        return

    app: FastAPI | None = None
    if isinstance(target, Request):
        app = target.app
    elif isinstance(target, FastAPI):
        app = target
    else:
        app = getattr(target, "app", None)

    if app is None:
        return

    event_identifier = event_id or str(uuid.uuid4())
    payload = {
        "id": event_identifier,
        "event": event,
        "data": data,
        "timestamp": time.time(),
    }

    # 1. In-memory bus dispatch
    try:
        bus = get_event_bus(app)
        await bus.publish(event, data, event_id=event_identifier)
    except Exception as exc:
        logger.warning("in-memory event broadcast failed: %s", exc)

    # 2. Redis Pub/Sub dispatch
    try:
        redis_client = getattr(app.state, "redis", None)
        if not redis_client:
            limiter = getattr(app.state, "limiter", None)
            redis_client = getattr(limiter, "_redis", None) if limiter else None

        if redis_client is not None:
            raw = json.dumps(payload, default=str)
            await redis_client.publish(LIVE_CHANNEL, raw)
    except Exception as exc:
        logger.warning("redis live broadcast failed: %s", exc)
