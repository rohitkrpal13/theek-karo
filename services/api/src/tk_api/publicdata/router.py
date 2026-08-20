"""Phase 15 public-data management endpoints (under `/api/v1/public-data`).

Admin operations manage the public dataset catalog, its versions + lineage,
the data-correction queue and API-key/usage reporting. Regular users manage
their own correction submissions, saved research queries and API keys.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from tk_api.api.deps import CurrentUser, DbSession, require_active
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.publicdata import service as pd_service
from tk_api.publicdata.models import DataExportJob
from tk_api.publicdata.schemas import (
    ApiKeyCreate,
    CorrectionCreate,
    CorrectionDecision,
    DatasetCreate,
    DatasetUpdate,
    DatasetVersionCreate,
    LineageStepCreate,
    SavedQueryCreate,
)

publicdata_router = APIRouter(prefix="/api/v1/public-data", tags=["public-data"])

AdminUser = Annotated[Any, Depends(require_active("admin", "super_admin"))]
DataTeamUser = Annotated[
    Any, Depends(require_active("admin", "super_admin", "analyst", "moderator"))
]

_service = pd_service.PublicDataService()


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


# -----------------------------------------------------------------------------
# Dataset catalog management (admin)
# -----------------------------------------------------------------------------


@publicdata_router.get("/datasets", summary="List public dataset catalog rows")
async def list_datasets(
    session: DbSession,
    category: str | None = None,
    user: CurrentUser = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    rows = await _service.list_public_datasets(session, category=category)
    return {"items": rows, "count": len(rows)}


@publicdata_router.get("/datasets/{slug}", summary="Dataset detail incl. versions + lineage")
async def dataset_detail(
    slug: str,
    session: DbSession,
    user: CurrentUser = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    return await _service.get_public_dataset(session, slug)


@publicdata_router.post("/datasets", status_code=201, summary="Create a public dataset entry")
async def create_dataset(
    body: DatasetCreate,
    session: DbSession,
    request: Request,
    user: AdminUser,
) -> dict[str, Any]:
    await _service.create_public_dataset(session, body.model_dump(), actor_id=user.id)
    await audit(
        session,
        action="public_dataset.create",
        entity_type="public_dataset",
        entity_id=None,
        actor_id=user.id,
        after=body.model_dump(),
        request=request,
    )
    return {"slug": body.slug}


@publicdata_router.patch("/datasets/{slug}", summary="Update a public dataset entry")
async def update_dataset(
    slug: str,
    body: DatasetUpdate,
    session: DbSession,
    request: Request,
    user: AdminUser,
) -> dict[str, Any]:
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    item = await _service.update_public_dataset(session, slug, payload, actor_id=user.id)
    await audit(
        session,
        action="public_dataset.update",
        entity_type="public_dataset",
        entity_id=item["slug"],
        after=payload,
        request=request,
    )
    return item


@publicdata_router.post(
    "/datasets/{slug}/versions", status_code=201, summary="Record a dataset version"
)
async def add_dataset_version(
    slug: str,
    body: DatasetVersionCreate,
    session: DbSession,
    user: AdminUser,
) -> dict[str, Any]:
    return await _service.add_dataset_version(session, slug, body.model_dump(), actor_id=user.id)


@publicdata_router.put("/datasets/{slug}/lineage", summary="Replace dataset lineage steps")
async def replace_lineage(
    slug: str,
    steps: list[LineageStepCreate],
    session: DbSession,
    user: AdminUser,
) -> dict[str, Any]:
    payload = [s.model_dump() for s in steps]
    await _service.set_dataset_lineage(session, slug, payload)
    return {"steps": payload}


# -----------------------------------------------------------------------------
# Data corrections
# -----------------------------------------------------------------------------


@publicdata_router.post("/corrections", status_code=201, summary="Submit a data correction request")
async def submit_correction(
    body: CorrectionCreate,
    session: DbSession,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    row = await _service.create_correction(session, user.id, body.model_dump())
    await audit(
        session,
        action="data_correction.create",
        entity_type="data_correction",
        entity_id=row["id"],
        actor_id=user.id,
        request=request,
    )
    return row


@publicdata_router.get("/corrections", summary="Data correction queue")
async def list_corrections(
    session: DbSession,
    status: str | None = None,
    user: DataTeamUser = None,
) -> dict[str, Any]:
    rows = await _service.list_corrections(session, status=status)
    return {"items": rows, "count": len(rows)}


@publicdata_router.get("/corrections/mine", summary="Current user's correction requests")
async def my_corrections(session: DbSession, user: CurrentUser) -> dict[str, Any]:
    rows = await _service.list_my_corrections(session, user.id)
    return {"items": rows, "count": len(rows)}


@publicdata_router.patch("/corrections/{correction_id}", summary="Decide a correction request")
async def decide_correction(
    correction_id: uuid.UUID,
    body: CorrectionDecision,
    session: DbSession,
    request: Request,
    user: DataTeamUser,
) -> dict[str, Any]:
    row = await _service.review_correction(
        session,
        correction_id,
        decision=body.status,
        note=body.note,
        actor_id=user.id,
    )
    await audit(
        session,
        action=f"data_correction.{body.status}",
        entity_type="data_correction",
        entity_id=row["id"],
        actor_id=user.id,
        after={"status": body.status, "note": body.note},
        request=request,
    )
    return row


# -----------------------------------------------------------------------------
# Saved research queries (private per user)
# -----------------------------------------------------------------------------


@publicdata_router.post("/research/saved", status_code=201, summary="Save a research query")
async def save_research_query(
    body: SavedQueryCreate,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    return await _service.save_query(session, user.id, body.name, body.filters)


@publicdata_router.get("/research/saved", summary="List saved research queries")
async def list_research_queries(session: DbSession, user: CurrentUser) -> dict[str, Any]:
    rows = await _service.list_saved_queries(session, user.id)
    return {"items": rows, "count": len(rows)}


@publicdata_router.delete("/research/saved/{query_id}", status_code=204)
async def delete_research_query(
    query_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
) -> None:
    await _service.delete_saved_query(session, query_id, user.id)


# -----------------------------------------------------------------------------
# Public API keys
# -----------------------------------------------------------------------------


@publicdata_router.post("/api-keys", status_code=201, summary="Create a public API key")
async def create_api_key(
    body: ApiKeyCreate,
    session: DbSession,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    result = await _service.create_api_key(session, user.id, body.name, body.quota_per_hour)
    await audit(
        session,
        action="public_api_key.create",
        entity_type="public_api_key",
        entity_id=result["id"],
        actor_id=user.id,
        request=request,
    )
    return result


@publicdata_router.get("/api-keys", summary="List own API keys (prefix + status only)")
async def list_api_keys(session: DbSession, user: CurrentUser) -> dict[str, Any]:
    rows = await _service.list_api_keys(session, user.id)
    return {"items": rows, "count": len(rows)}


@publicdata_router.post("/api-keys/{key_id}/revoke", summary="Revoke an API key")
async def revoke_api_key(
    key_id: uuid.UUID,
    session: DbSession,
    request: Request,
    user: CurrentUser,
) -> dict[str, Any]:
    row = await _service.revoke_api_key(session, key_id, user.id)
    await audit(
        session,
        action="public_api_key.revoke",
        entity_type="public_api_key",
        entity_id=key_id,
        actor_id=user.id,
        request=request,
    )
    return row


@publicdata_router.get("/usage", summary="Public API usage summary (admin)")
async def usage_report(
    session: DbSession,
    days: int = 7,
    user: AdminUser = None,
) -> dict[str, Any]:
    return await _service.usage_summary(session, days=max(1, min(days, 90)))


# -----------------------------------------------------------------------------
# Export jobs (user-facing status)
# -----------------------------------------------------------------------------


@publicdata_router.get("/exports/{job_id}", summary="Export job status")
async def export_job_status(
    job_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    job = await session.get(DataExportJob, job_id)
    if job is None:
        raise ApiError("export job not found", 404, "export_job_not_found")
    if not user.has_role("admin") and job.user_id != user.id:
        raise ApiError("export job not found", 404, "export_job_not_found")
    return _service._job_payload(job)
