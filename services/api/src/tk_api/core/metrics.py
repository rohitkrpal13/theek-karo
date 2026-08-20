"""SLO metrics (Phase 10): request duration histogram + status counters.

Prometheus exposition at ``/metrics`` (ops endpoint, no auth in dev; guarded
by network policy in prod). SLO basis (docs/SLOs.md): p95 API latency < 500 ms
for health/civic read paths; high-cardinality labels are avoided by design —
only route groups, not per-path series.
"""

from __future__ import annotations

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

REQUEST_DURATION = Histogram(
    "tk_api_request_duration_seconds",
    "API request duration (seconds)",
    labelnames=["route_group", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
REQUEST_TOTAL = Counter(
    "tk_api_requests_total",
    "API requests total",
    labelnames=["route_group", "method", "status_class"],
)
DB_PING_ERRORS = Counter("tk_api_db_ping_errors_total", "readyz DB check failures")


def route_group(path: str) -> str:
    """Cards paths to a bounded label set (SLO drives cardinality discipline)."""
    if path in ("/healthz", "/readyz", "/metrics"):
        return "ops"
    if path.startswith("/api/v1/reports"):
        return "reports"
    if path.startswith("/api/v1/civic"):
        return "civic"
    if path.startswith("/api/v1/auth"):
        return "auth"
    if path.startswith("/api/v1/gis"):
        return "gis"
    if path.startswith("/api/v1/media"):
        return "media"
    if path.startswith("/api/v1/ai"):
        return "ai"
    if path.startswith("/api/v1/notifications"):
        return "notifications"
    if path.startswith("/api/v1/measurement"):
        return "measurement"
    if path.startswith("/api/v1/users"):
        return "users"
    return "other"


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        group = route_group(request.url.path)
        method = request.method
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            REQUEST_TOTAL.labels(group, method, "5xx").inc()
            raise
        finally:
            REQUEST_DURATION.labels(group, method).observe(time.perf_counter() - start)
        status_class = f"{response.status_code // 100}xx"
        REQUEST_TOTAL.labels(group, method, status_class).inc()
        return response
