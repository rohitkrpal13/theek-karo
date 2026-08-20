"""Ops metrics endpoint (Phase 10): Prometheus exposition.

Besides the request histogram/counters, a ``tk_api_queue_backlog`` gauge is
refreshed per scrape with the queued-notification count (best-effort: DB
unavailability leaves the previous value, which the alert window covers).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from sqlalchemy import text

logger = logging.getLogger("tk_api.metrics")

QUEUE_BACKLOG = Gauge("tk_api_queue_backlog", "queued notification_queue rows (per-scrape)")

metrics_router = APIRouter()


@metrics_router.get("/metrics")
async def metrics(request: Request) -> Response:
    engine = getattr(request.app.state, "engine", None)
    if engine is not None:
        try:
            async with engine.connect() as conn:
                queued = (
                    await conn.execute(
                        text("SELECT count(*) FROM notification_queue WHERE status = 'queued'")
                    )
                ).scalar_one()
            QUEUE_BACKLOG.set(float(queued))
        except Exception:
            logger.warning("queue gauge refresh failed; keeping previous value")
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
