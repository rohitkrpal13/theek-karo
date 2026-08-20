"""Phase 23 — Data Trust API router.

Exposes evidence registry, verification, data quality, conflict detection,
dispute management, provenance chain, and data trust dashboard endpoints.

Mounts under ``/api/v1/data-trust/``.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from tk_api.api.deps import CurrentUser, DbSession, OptionalUser, require_active
from tk_api.data_trust import service as trust_service

data_trust_router = APIRouter(prefix="/api/v1/data-trust", tags=["data-trust"])


def _safe_uuid(value: str | None) -> uuid.UUID | None:
    """Parse a UUID string, returning None on failure."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Evidence Registry
# ---------------------------------------------------------------------------


@data_trust_router.post("/evidence", status_code=201)
async def register_evidence(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Register a new evidence item in the central evidence registry."""
    return await trust_service.register_evidence(db, data=body, actor_id=user.id)


@data_trust_router.get("/evidence")
async def list_evidence(
    db: DbSession,
    user: OptionalUser = None,
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    source_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List evidence records with optional filters."""
    geo_id = _safe_uuid(entity_id)
    return await trust_service.list_evidence(
        db,
        entity_type=entity_type,
        entity_id=geo_id,
        source_type=source_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@data_trust_router.get("/evidence/{evidence_id}")
async def get_evidence(
    evidence_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get a single evidence record."""
    return await trust_service.get_evidence(db, evidence_id)


# ---------------------------------------------------------------------------
# Verification Records
# ---------------------------------------------------------------------------


@data_trust_router.post("/verifications", status_code=201)
async def create_verification(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """Create a new verification record (append-only)."""
    return await trust_service.create_verification(db, data=body, actor_id=user.id)


@data_trust_router.get("/verifications")
async def list_verifications(
    db: DbSession,
    user: OptionalUser = None,
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    decision: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List verification records."""
    geo_id = _safe_uuid(entity_id)
    return await trust_service.list_verifications(
        db,
        entity_type=entity_type,
        entity_id=geo_id,
        decision=decision,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------

_moderator_or_analyst = Depends(require_active("admin", "analyst", "moderator"))
_admin_or_analyst = Depends(require_active("admin", "analyst"))


@data_trust_router.post("/quality", status_code=201)
async def record_quality(
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_analyst],
) -> dict[str, Any]:
    """Record a data quality check result."""
    return await trust_service.record_quality_check(db, data=body)


@data_trust_router.get("/quality/{entity_type}/{entity_id}")
async def get_quality(
    entity_type: str,
    entity_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get aggregated quality dimensions for an entity."""
    return await trust_service.get_quality_summary(db, entity_type=entity_type, entity_id=entity_id)


# ---------------------------------------------------------------------------
# Data Conflicts
# ---------------------------------------------------------------------------


@data_trust_router.post("/conflicts", status_code=201)
async def detect_conflict(
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_analyst],
) -> dict[str, Any]:
    """Record a detected data conflict."""
    return await trust_service.detect_conflict(db, data=body)


@data_trust_router.get("/conflicts")
async def list_conflicts(
    db: DbSession,
    user: OptionalUser = None,
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List data conflicts."""
    geo_id = _safe_uuid(entity_id)
    return await trust_service.list_conflicts(
        db,
        entity_type=entity_type,
        entity_id=geo_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@data_trust_router.patch("/conflicts/{conflict_id}/resolve")
async def resolve_conflict(
    conflict_id: uuid.UUID,
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_analyst],
) -> dict[str, Any]:
    """Resolve a data conflict."""
    return await trust_service.resolve_conflict(
        db, conflict_id=conflict_id, data=body, actor_id=user.id
    )


# ---------------------------------------------------------------------------
# Disputes
# ---------------------------------------------------------------------------


@data_trust_router.post("/disputes", status_code=201)
async def file_dispute(
    body: dict[str, Any],
    db: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    """File a new dispute against a record."""
    return await trust_service.file_dispute(db, data=body, actor_id=user.id)


@data_trust_router.get("/disputes")
async def list_disputes(
    db: DbSession,
    user: OptionalUser = None,
    target_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List dispute records."""
    return await trust_service.list_disputes(
        db,
        target_type=target_type,
        status=status,
        limit=limit,
        offset=offset,
    )


@data_trust_router.patch("/disputes/{dispute_id}/review")
async def review_dispute(
    dispute_id: uuid.UUID,
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _moderator_or_analyst],
) -> dict[str, Any]:
    """Review and decide on a dispute."""
    return await trust_service.review_dispute(
        db, dispute_id=dispute_id, data=body, actor_id=user.id
    )


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@data_trust_router.get("/provenance/{entity_type}/{entity_id}")
async def get_provenance(
    entity_type: str,
    entity_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> dict[str, Any]:
    """Get the complete provenance chain for an entity."""
    return await trust_service.get_provenance(db, entity_type=entity_type, entity_id=entity_id)


# ---------------------------------------------------------------------------
# Change History
# ---------------------------------------------------------------------------


@data_trust_router.get("/history/{entity_type}/{entity_id}")
async def get_change_history(
    entity_type: str,
    entity_id: uuid.UUID,
    db: DbSession,
    user: OptionalUser = None,
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Get the change history for an entity."""
    return await trust_service.list_change_history(
        db, entity_type=entity_type, entity_id=entity_id, limit=limit
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@data_trust_router.get("/dashboard")
async def get_dashboard(
    db: DbSession,
    user: Annotated[CurrentUser, _admin_or_analyst],
) -> dict[str, Any]:
    """Get the data quality dashboard summary."""
    return await trust_service.get_dashboard(db)


# ---------------------------------------------------------------------------
# Metric Definitions
# ---------------------------------------------------------------------------


@data_trust_router.post("/metrics", status_code=201)
async def create_metric(
    body: dict[str, Any],
    db: DbSession,
    user: Annotated[CurrentUser, _admin_or_analyst],
) -> dict[str, Any]:
    """Create or update a metric definition."""
    return await trust_service.create_metric_definition(db, data=body)


@data_trust_router.get("/metrics")
async def list_metrics(
    db: DbSession,
    user: OptionalUser = None,
    category: str | None = Query(None),
    visibility: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List metric definitions."""
    return await trust_service.list_metric_definitions(
        db, category=category, visibility=visibility, limit=limit
    )
