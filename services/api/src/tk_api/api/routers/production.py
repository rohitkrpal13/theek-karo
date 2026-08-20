"""Production readiness API router (Phase 29).

Endpoints for:
- Comprehensive health checks
- Performance budget monitoring
- Cost tracking
- Database optimization
- SLO compliance
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_permission
from tk_api.production.observability import (
    get_cost_tracker,
    get_health_checker,
    get_performance_tracker,
)

router = APIRouter(prefix="/api/v1/production", tags=["production"])

DepSecRead = Annotated[Any, Depends(require_permission("security.read"))]
DepAiAdmin = Annotated[Any, Depends(require_permission("ai.admin"))]


# ---------------------------------------------------------------------------
# Health Checks
# ---------------------------------------------------------------------------


@router.get("/health")
async def comprehensive_health(
    request: Request,
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """Comprehensive health check with all dependencies."""
    checker = get_health_checker()
    return await checker.check_all(request.app)


@router.get("/health/database")
async def database_health(
    request: Request,
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """Database-specific health check with pool stats."""
    from tk_api.production.db_optimization import DatabaseOptimizer

    optimizer = DatabaseOptimizer(request.app.state.engine)
    pool_stats = await optimizer.check_connections()
    return pool_stats


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------


@router.get("/performance/budgets")
async def performance_budgets(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """Check performance against defined budgets."""
    tracker = get_performance_tracker()
    return tracker.summary()


# ---------------------------------------------------------------------------
# Cost Tracking
# ---------------------------------------------------------------------------


@router.get("/cost/summary")
async def cost_summary(
    user: CurrentUser,
    _perm: DepAiAdmin,
    db: DbSession,
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    """Get cost summary for the specified period."""
    tracker = get_cost_tracker()
    return tracker.summary(days=days)


# ---------------------------------------------------------------------------
# Database Optimization
# ---------------------------------------------------------------------------


@router.get("/database/maintenance")
async def database_maintenance(
    request: Request,
    user: CurrentUser,
    _perm: DepAiAdmin,
    db: DbSession,
) -> dict[str, Any]:
    """Run database maintenance checks (table sizes, unused indexes, bloat)."""
    from tk_api.production.db_optimization import DatabaseOptimizer

    optimizer = DatabaseOptimizer(request.app.state.engine)
    return await optimizer.run_maintenance()


@router.get("/database/slow-queries")
async def slow_queries(
    request: Request,
    user: CurrentUser,
    _perm: DepAiAdmin,
    db: DbSession,
) -> dict[str, Any]:
    """Get recorded slow queries."""
    from tk_api.production.db_optimization import DatabaseOptimizer

    optimizer = DatabaseOptimizer(request.app.state.engine)
    return {"slow_queries": await optimizer.get_slow_queries()}


@router.get("/database/query-stats")
async def query_stats(
    request: Request,
    user: CurrentUser,
    _perm: DepAiAdmin,
    db: DbSession,
) -> dict[str, Any]:
    """Get query performance statistics."""
    from tk_api.production.db_optimization import DatabaseOptimizer

    optimizer = DatabaseOptimizer(request.app.state.engine)
    return optimizer.get_query_stats()


# ---------------------------------------------------------------------------
# SLO
# ---------------------------------------------------------------------------


@router.get("/slo/availability")
async def slo_availability(
    user: CurrentUser,
    _perm: DepSecRead,
    db: DbSession,
) -> dict[str, Any]:
    """Calculate API availability SLO."""
    # In production, this would query Prometheus
    return {
        "target": 0.999,
        "note": "Query Prometheus for actual values in production",
    }


# Export router
production_router = router
