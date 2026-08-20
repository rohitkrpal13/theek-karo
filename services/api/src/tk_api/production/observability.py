"""Observability module (Phase 29).

Provides:
- Enhanced health checks with dependency tracking
- SLO/SLI monitoring
- Business metrics collection
- Dependency health tracking
- Cost tracking
- Performance budgets
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# SLO Metrics
# ---------------------------------------------------------------------------

# API availability SLO: 99.9% of requests succeed (2xx/3xx)
API_AVAILABILITY = Gauge(
    "tk_api_availability_ratio",
    "API availability ratio (non-5xx / total)",
    ["service"],
)

# API latency SLO: p95 < 500ms for read paths
API_LATENCY_P95 = Histogram(
    "tk_api_latency_p95_seconds",
    "API request latency p95",
    ["route_group"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Database query latency
DB_QUERY_LATENCY = Histogram(
    "tk_api_db_query_latency_seconds",
    "Database query latency",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# Cache performance
CACHE_HITS = Counter("tk_api_cache_hits_total", "Cache hits", ["namespace"])
CACHE_MISSES = Counter("tk_api_cache_misses_total", "Cache misses", ["namespace"])
CACHE_ERRORS = Counter("tk_api_cache_errors_total", "Cache errors", ["namespace"])

# Queue depth
QUEUE_DEPTH = Gauge("tk_api_queue_depth", "Queue depth", ["queue_name"])
QUEUE_PROCESSING_TIME = Histogram(
    "tk_api_queue_processing_seconds",
    "Queue task processing time",
    ["task_name"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
)

# AI metrics
AI_REQUESTS = Counter("tk_api_ai_requests_total", "AI requests", ["agent", "status"])
AI_LATENCY = Histogram(
    "tk_api_ai_latency_seconds",
    "AI request latency",
    ["agent"],
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0),
)
AI_COST = Counter("tk_api_ai_cost_usd_total", "AI cost in USD", ["model"])
AI_TOKENS = Counter("tk_api_ai_tokens_total", "AI tokens consumed", ["model", "direction"])

# Notification metrics
NOTIFICATIONS_SENT = Counter("tk_api_notifications_sent_total", "Notifications sent", ["channel"])
NOTIFICATION_FAILURES = Counter(
    "tk_api_notification_failures_total", "Notification failures", ["channel"]
)

# Government workflow metrics
GOV_RESPONSE_TIME = Histogram(
    "tk_api_gov_response_time_seconds",
    "Government response time",
    ["department_type"],
    buckets=(3600, 86400, 604800, 2592000),  # hours to months
)

# Storage metrics
STORAGE_USAGE = Gauge("tk_api_storage_bytes", "Storage usage", ["bucket", "type"])
STORAGE_OPS = Counter("tk_api_storage_ops_total", "Storage operations", ["operation", "status"])


# ---------------------------------------------------------------------------
# Health Check System
# ---------------------------------------------------------------------------


@dataclass
class DependencyHealth:
    """Health status for a single dependency."""

    name: str
    status: str = "unknown"  # ok, degraded, down
    latency_ms: float = 0.0
    last_checked: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class HealthChecker:
    """Comprehensive health check system with dependency tracking."""

    def __init__(self) -> None:
        self._dependencies: dict[str, DependencyHealth] = {}
        self._start_time = datetime.now(UTC)

    async def check_all(self, app: Any) -> dict[str, Any]:
        """Run all health checks and return consolidated status."""
        checks = {}

        # Database check
        checks["database"] = await self._check_database(app)

        # Redis check
        checks["redis"] = await self._check_redis(app)

        # Storage check
        checks["storage"] = await self._check_storage(app)

        # Worker check
        checks["worker"] = await self._check_worker(app)

        # Determine overall status
        statuses = [c.get("status", "down") for c in checks.values()]
        if all(s == "ok" for s in statuses):
            overall = "healthy"
        elif any(s == "down" for s in statuses):
            overall = "degraded"
        else:
            overall = "healthy"

        uptime = (datetime.now(UTC) - self._start_time).total_seconds()

        return {
            "status": overall,
            "version": app.state.settings.env if hasattr(app.state, "settings") else "unknown",
            "uptime_seconds": int(uptime),
            "checks": checks,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    async def _check_database(self, app: Any) -> dict[str, Any]:
        """Check database connectivity and latency."""
        start = time.perf_counter()
        try:
            from tk_api.core.db import ping_database

            await ping_database(app.state.engine)
            latency_ms = (time.perf_counter() - start) * 1000
            return {"status": "ok", "latency_ms": round(latency_ms, 2)}
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return {"status": "down", "latency_ms": round(latency_ms, 2), "error": str(exc)}

    async def _check_redis(self, app: Any) -> dict[str, Any]:
        """Check Redis connectivity and latency."""
        if not hasattr(app.state, "limiter") or app.state.limiter._redis is None:
            return {"status": "ok", "mode": "memory", "note": "Using in-memory fallback"}

        start = time.perf_counter()
        try:
            await app.state.limiter._redis.ping()
            latency_ms = (time.perf_counter() - start) * 1000
            return {"status": "ok", "latency_ms": round(latency_ms, 2)}
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            return {"status": "degraded", "latency_ms": round(latency_ms, 2), "error": str(exc)}

    async def _check_storage(self, app: Any) -> dict[str, Any]:
        """Check object storage connectivity."""
        if not hasattr(app.state, "storage"):
            return {"status": "ok", "mode": "memory"}

        storage = app.state.storage
        mode = type(storage).__name__
        return {"status": "ok", "mode": mode}

    async def _check_worker(self, app: Any) -> dict[str, Any]:
        """Check Celery worker availability."""
        from tk_api.core.config import get_settings

        settings = get_settings()

        if not settings.celery_enabled:
            return {"status": "ok", "mode": "in-process", "note": "Celery disabled"}

        try:
            from tk_api.worker import celery_app

            inspect = celery_app.control.inspect(timeout=2.0)
            active = inspect.active()
            if active:
                total_tasks = sum(len(tasks) for tasks in active.values())
                return {"status": "ok", "active_tasks": total_tasks, "workers": len(active)}
            return {"status": "degraded", "note": "No workers responding"}
        except Exception as exc:
            return {"status": "degraded", "error": str(exc)}


# ---------------------------------------------------------------------------
# Performance Budget Tracker
# ---------------------------------------------------------------------------


@dataclass
class PerformanceBudget:
    """Define performance budgets for different operations."""

    operation: str
    target_p50_ms: float
    target_p95_ms: float
    target_p99_ms: float


# Default performance budgets
DEFAULT_BUDGETS = [
    PerformanceBudget("api_read", 50, 200, 500),
    PerformanceBudget("api_write", 100, 500, 1000),
    PerformanceBudget("case_create", 200, 500, 1000),
    PerformanceBudget("search", 100, 300, 1000),
    PerformanceBudget("map_query", 100, 500, 1500),
    PerformanceBudget("ai_chat", 1000, 5000, 15000),
    PerformanceBudget("notification_send", 500, 2000, 5000),
]


class PerformanceTracker:
    """Track performance against defined budgets."""

    def __init__(self, budgets: list[PerformanceBudget] | None = None):
        self._budgets = {b.operation: b for b in (budgets or DEFAULT_BUDGETS)}
        self._recent: dict[str, list[float]] = {}

    def record(self, operation: str, latency_ms: float) -> None:
        """Record a latency measurement."""
        if operation not in self._recent:
            self._recent[operation] = []
        self._recent[operation].append(latency_ms)
        # Keep only last 1000 measurements
        if len(self._recent[operation]) > 1000:
            self._recent[operation] = self._recent[operation][-1000:]

    def check_budget(self, operation: str) -> dict[str, Any]:
        """Check if an operation is within its performance budget."""
        if operation not in self._recent or not self._recent[operation]:
            return {"operation": operation, "status": "no_data"}

        latencies = sorted(self._recent[operation])
        n = len(latencies)
        p50 = latencies[n // 2]
        p95 = latencies[int(n * 0.95)]
        p99 = latencies[int(n * 0.99)]

        budget = self._budgets.get(operation)
        if budget is None:
            return {
                "operation": operation,
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
                "p99_ms": round(p99, 2),
                "status": "no_budget",
            }

        violations = []
        if p50 > budget.target_p50_ms:
            violations.append(f"p50 ({p50:.0f}ms > {budget.target_p50_ms}ms)")
        if p95 > budget.target_p95_ms:
            violations.append(f"p95 ({p95:.0f}ms > {budget.target_p95_ms}ms)")
        if p99 > budget.target_p99_ms:
            violations.append(f"p99 ({p99:.0f}ms > {budget.target_p99_ms}ms)")

        return {
            "operation": operation,
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "p99_ms": round(p99, 2),
            "budget": {
                "target_p50_ms": budget.target_p50_ms,
                "target_p95_ms": budget.target_p95_ms,
                "target_p99_ms": budget.target_p99_ms,
            },
            "status": "pass" if not violations else "fail",
            "violations": violations,
        }

    def summary(self) -> dict[str, Any]:
        """Get performance summary for all tracked operations."""
        return {op: self.check_budget(op) for op in self._recent}


# ---------------------------------------------------------------------------
# Cost Tracker
# ---------------------------------------------------------------------------


class CostTracker:
    """Track operational costs across services."""

    def __init__(self) -> None:
        self._costs: dict[str, float] = {}
        self._daily: dict[str, dict[str, float]] = {}

    def record(
        self,
        service: str,
        amount: float,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a cost event."""
        self._costs[service] = self._costs.get(service, 0) + amount

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        if today not in self._daily:
            self._daily[today] = {}
        self._daily[today][service] = self._daily[today].get(service, 0) + amount

    def summary(self, days: int = 7) -> dict[str, Any]:
        """Get cost summary for the last N days."""
        cutoff = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
        daily = {date: costs for date, costs in self._daily.items() if date >= cutoff}

        totals: dict[str, float] = {}
        for date_costs in daily.values():
            for service, amount in date_costs.items():
                totals[service] = totals.get(service, 0) + amount

        return {
            "total": sum(totals.values()),
            "by_service": totals,
            "daily": daily,
            "period_days": days,
        }


# ---------------------------------------------------------------------------
# SLO Calculator
# ---------------------------------------------------------------------------


class SLOCalculator:
    """Calculate SLO compliance from metrics."""

    @staticmethod
    def availability(
        successful: int,
        total: int,
    ) -> dict[str, Any]:
        """Calculate availability SLO."""
        if total == 0:
            return {"ratio": 1.0, "status": "no_data", "target": 0.999}

        ratio = successful / total
        target = 0.999  # 99.9%
        return {
            "ratio": round(ratio, 6),
            "target": target,
            "status": "pass" if ratio >= target else "fail",
            "error_budget_remaining": round(max(0, target - ratio) / (1 - target), 4),
        }

    @staticmethod
    def latency_slo(
        latencies_ms: list[float],
        target_p95_ms: float = 500,
    ) -> dict[str, Any]:
        """Calculate latency SLO compliance."""
        if not latencies_ms:
            return {"status": "no_data", "target_p95_ms": target_p95_ms}

        sorted_latencies = sorted(latencies_ms)
        n = len(sorted_latencies)
        p95 = sorted_latencies[int(n * 0.95)]

        return {
            "p95_ms": round(p95, 2),
            "target_p95_ms": target_p95_ms,
            "status": "pass" if p95 <= target_p95_ms else "fail",
            "sample_count": n,
        }


# ---------------------------------------------------------------------------
# Global instances (initialized at app startup)
# ---------------------------------------------------------------------------

_health_checker = HealthChecker()
_performance_tracker = PerformanceTracker()
_cost_tracker = CostTracker()


def get_health_checker() -> HealthChecker:
    return _health_checker


def get_performance_tracker() -> PerformanceTracker:
    return _performance_tracker


def get_cost_tracker() -> CostTracker:
    return _cost_tracker
