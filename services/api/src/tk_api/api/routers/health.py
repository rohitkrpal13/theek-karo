"""Ops endpoints: liveness, readiness, version."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tk_api import __version__
from tk_api.core.db import ping_database
from tk_api.core.errors import _problem
from tk_api.core.logging import log_extra
from tk_api.production.observability import get_health_checker

router = APIRouter(tags=["ops"])
logger = logging.getLogger("tk_api.health")


@router.get("/healthz", summary="Liveness probe")
@router.get("/health", summary="Liveness probe (alias)")
@router.get("/livez", summary="Liveness probe (alias)")
@router.get("/live", summary="Liveness probe (alias)")
async def healthz() -> dict[str, str]:
    """Liveness: process is up. No dependency checks (SECURITY/API.md)."""
    return {"status": "ok"}


@router.get("/readyz", summary="Readiness probe")
@router.get("/ready", summary="Readiness probe (alias)")
async def readyz(request: Request) -> JSONResponse:
    """Readiness: process is up and critical dependencies are reachable."""
    engine = request.app.state.engine
    checks: dict[str, str] = {}
    try:
        await ping_database(engine)
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("Readiness check failed: database unreachable", **log_extra(error=str(exc)))
        return _problem(
            503,
            title="Service unavailable",
            instance="/readyz",
            detail="Database dependency unavailable",
        )
    return JSONResponse({"status": "ok", "checks": checks})


@router.get("/health/comprehensive", summary="Comprehensive health check")
async def comprehensive_healthz(request: Request) -> JSONResponse:
    """Comprehensive health: database, Redis, storage, worker status."""
    checker = get_health_checker()
    result = await checker.check_all(request.app)
    status_code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(content=result, status_code=status_code)


@router.get("/api/v1/version", summary="Service version")
async def version() -> dict[str, str]:
    return {"service": "tk-api", "version": __version__}
