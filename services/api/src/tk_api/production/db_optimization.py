"""Database optimization helpers (Phase 29).

Provides:
- Connection pool monitoring
- Slow query detection
- Read replica routing
- Query analysis helpers
- Index recommendations
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import AsyncAdaptedQueuePool

logger = logging.getLogger("tk_api.db_optimization")


@dataclass
class PoolStats:
    """Connection pool statistics."""

    size: int = 0
    checked_in: int = 0
    checked_out: int = 0
    overflow: int = 0
    total_connections: int = 0
    idle_connections: int = 0


@dataclass
class SlowQuery:
    """Record of a slow query."""

    query: str
    duration_ms: float
    parameters: dict[str, Any] | None = None
    timestamp: float = field(default_factory=time.time)


class DatabaseOptimizer:
    """Database optimization and monitoring utilities."""

    def __init__(
        self,
        engine: AsyncEngine,
        slow_query_threshold_ms: float = 200,
    ):
        self._engine = engine
        self._slow_query_threshold = slow_query_threshold_ms
        self._slow_queries: list[SlowQuery] = []
        self._query_stats: dict[str, list[float]] = {}

    async def get_pool_stats(self) -> PoolStats:
        """Get connection pool statistics."""
        pool = cast(AsyncAdaptedQueuePool, self._engine.pool)
        try:
            return PoolStats(
                size=pool.size(),
                checked_in=pool.checkedin(),
                checked_out=pool.checkedout(),
                overflow=pool.overflow(),
                total_connections=pool.size() + pool.overflow(),
                idle_connections=pool.checkedin(),
            )
        except AttributeError:
            # StaticPool (tests) doesn't have size/checkedin/checkedout
            return PoolStats(size=1, checked_in=1, checked_out=0)

    async def check_connections(self) -> dict[str, Any]:
        """Check database connection health and pool status."""
        stats = await self.get_pool_stats()
        total = stats.size + stats.overflow
        utilization = stats.checked_out / max(total, 1) if total > 0 else 0

        status = "healthy"
        if utilization > 0.9:
            status = "critical"
        elif utilization > 0.7:
            status = "warning"

        return {
            "status": status,
            "pool": {
                "size": stats.size,
                "checked_out": stats.checked_out,
                "checked_in": stats.checked_in,
                "overflow": stats.overflow,
                "utilization": round(utilization, 3),
            },
        }

    async def run_maintenance(self) -> dict[str, Any]:
        """Run database maintenance tasks (ANALYZE, VACUUM stats)."""
        results: dict[str, Any] = {}

        try:
            async with self._engine.connect() as conn:
                # Get table sizes
                size_result = await conn.execute(
                    text(
                        "SELECT schemaname, tablename, "
                        "pg_size_pretty(pg_total_relation_size("
                        "schemaname||'.'||tablename)) as size "
                        "FROM pg_tables WHERE schemaname = 'public' "
                        "ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC "
                        "LIMIT 20"
                    )
                )
                tables = [
                    {"schema": row[0], "table": row[1], "size": row[2]} for row in size_result.all()
                ]
                results["table_sizes"] = tables

                # Get index usage
                index_result = await conn.execute(
                    text(
                        "SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read "
                        "FROM pg_stat_user_indexes "
                        "WHERE schemaname = 'public' "
                        "ORDER BY idx_scan ASC "
                        "LIMIT 20"
                    )
                )
                unused_indexes = [
                    {
                        "schema": row[0],
                        "table": row[1],
                        "index": row[2],
                        "scans": row[3],
                        "tuples_read": row[4],
                    }
                    for row in index_result.all()
                ]
                results["unused_indexes"] = unused_indexes

                # Get table bloat estimate
                bloat_result = await conn.execute(
                    text(
                        "SELECT schemaname, tablename, n_dead_tup, n_live_tup, "
                        "CASE WHEN n_live_tup > 0 THEN "
                        "round(n_dead_tup * 100.0 / n_live_tup, 2) ELSE 0 END as dead_ratio "
                        "FROM pg_stat_user_tables "
                        "WHERE schemaname = 'public' AND n_dead_tup > 1000 "
                        "ORDER BY n_dead_tup DESC "
                        "LIMIT 10"
                    )
                )
                bloat = [
                    {
                        "schema": row[0],
                        "table": row[1],
                        "dead_tuples": row[2],
                        "live_tuples": row[3],
                        "dead_ratio_pct": float(row[4]),
                    }
                    for row in bloat_result.all()
                ]
                results["table_bloat"] = bloat

        except Exception as exc:
            logger.error("Database maintenance check failed: %s", exc)
            results["error"] = str(exc)

        return results

    async def get_slow_queries(self) -> list[dict[str, Any]]:
        """Get recorded slow queries."""
        return [
            {
                "query": sq.query[:200],
                "duration_ms": round(sq.duration_ms, 2),
                "timestamp": sq.timestamp,
            }
            for sq in self._slow_queries[-50:]  # Last 50
        ]

    def record_query(self, query: str, duration_ms: float) -> None:
        """Record a query execution for slow query detection."""
        # Track by query pattern (first 100 chars)
        pattern = query[:100]
        if pattern not in self._query_stats:
            self._query_stats[pattern] = []
        self._query_stats[pattern].append(duration_ms)
        if len(self._query_stats[pattern]) > 100:
            self._query_stats[pattern] = self._query_stats[pattern][-100:]

        if duration_ms > self._slow_query_threshold:
            self._slow_queries.append(SlowQuery(query=query, duration_ms=duration_ms))
            if len(self._slow_queries) > 200:
                self._slow_queries = self._slow_queries[-200:]
            logger.warning(
                "Slow query detected (%.1fms): %s",
                duration_ms,
                query[:100],
            )

    def get_query_stats(self) -> dict[str, Any]:
        """Get query performance statistics."""
        stats = {}
        for pattern, durations in self._query_stats.items():
            sorted_d = sorted(durations)
            n = len(sorted_d)
            stats[pattern] = {
                "count": n,
                "avg_ms": round(sum(durations) / n, 2) if n > 0 else 0,
                "p50_ms": round(sorted_d[n // 2], 2) if n > 0 else 0,
                "p95_ms": round(sorted_d[int(n * 0.95)], 2) if n > 0 else 0,
                "max_ms": round(max(durations), 2) if n > 0 else 0,
            }
        return stats


# ---------------------------------------------------------------------------
# Pagination Helpers
# ---------------------------------------------------------------------------


class CursorPagination:
    """Cursor-based pagination for efficient large-dataset traversal.

    Usage:
        pagination = CursorPagination(limit=50)
        query = pagination.apply(query, model.id)
        results = await session.execute(query)
        next_cursor = pagination.get_next_cursor(results)
    """

    def __init__(self, limit: int = 50, max_limit: int = 200):
        self._limit = min(limit, max_limit)
        self._max_limit = max_limit

    @property
    def limit(self) -> int:
        return self._limit

    def apply(
        self,
        query: Any,
        cursor_column: Any,
        cursor: str | None = None,
    ) -> Any:
        """Apply cursor-based pagination to a query."""
        if cursor:
            try:
                from sqlalchemy import or_

                query = query.where(
                    or_(
                        cursor_column > cursor,
                        cursor_column == None,  # noqa: E711
                    )
                )
            except Exception:
                pass  # Invalid cursor, ignore
        return query.order_by(cursor_column).limit(self._limit + 1)

    def get_next_cursor(self, results: list[Any], id_getter: Any = None) -> str | None:
        """Extract next cursor from results."""
        if len(results) <= self._limit:
            return None
        last = results[self._limit - 1]
        if id_getter:
            return str(id_getter(last))
        return str(getattr(last, "id", None))

    def format_response(
        self,
        items: list[Any],
        next_cursor: str | None,
    ) -> dict[str, Any]:
        """Format paginated response."""
        has_more = len(items) > self._limit
        return {
            "items": items[: self._limit],
            "next_cursor": next_cursor if has_more else None,
            "has_more": has_more,
            "limit": self._limit,
        }


class OffsetPagination:
    """Traditional offset-based pagination with safety limits."""

    def __init__(self, default_limit: int = 50, max_limit: int = 200):
        self._default = default_limit
        self._max = max_limit

    def get_params(
        self,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[int, int]:
        """Get safe pagination parameters."""
        safe_offset = max(0, offset)
        safe_limit = min(limit or self._default, self._max)
        return safe_offset, safe_limit

    def format_response(
        self,
        items: list[Any],
        total: int,
        offset: int,
        limit: int,
    ) -> dict[str, Any]:
        """Format paginated response."""
        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": (offset + limit) < total,
        }
