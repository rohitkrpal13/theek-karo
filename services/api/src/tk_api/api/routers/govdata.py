"""FastAPI router for Government Data, Official Sources, Discrepancies, and Comparison."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from tk_api.api.deps import DbSession, require_roles
from tk_api.core.audit import audit
from tk_api.govdata import service as gov_service
from tk_api.govdata.schemas import (
    DataQualityReportRead,
    DataSourceCreate,
    DataSourceRead,
    DiscrepancyItemRead,
    EntityMatchReviewDecision,
    EntityMatchReviewRead,
    ImportJobCreate,
    ImportJobRead,
    InstitutionComparisonRead,
    OfficialDataRead,
)

govdata_router = APIRouter(tags=["govdata"])
AdminOrAnalyst = Annotated[Any, Depends(require_roles("admin", "analyst"))]


# -----------------------------------------------------------------------------
# 1. Public Institution Official Data & Comparison Endpoints
# -----------------------------------------------------------------------------


@govdata_router.get(
    "/api/v1/institutions/{institution_id}/official-data",
    response_model=OfficialDataRead,
    summary="Institution official dataset and canonical attributes",
)
async def get_institution_official_data(
    institution_id: uuid.UUID,
    session: DbSession,
) -> OfficialDataRead:
    """Retrieve structured official government data for an institution."""
    return await gov_service.get_institution_official_data(session, institution_id=institution_id)


@govdata_router.get(
    "/api/v1/institutions/{institution_id}/discrepancies",
    response_model=list[DiscrepancyItemRead],
    summary="Institution discrepancy analysis",
)
async def get_institution_discrepancies(
    institution_id: uuid.UUID,
    session: DbSession,
) -> list[DiscrepancyItemRead]:
    """Retrieve rule-based discrepancy analysis between official baseline and citizen reports."""
    return await gov_service.get_institution_discrepancies(session, institution_id=institution_id)


@govdata_router.get(
    "/api/v1/institutions/{institution_id}/comparison",
    response_model=InstitutionComparisonRead,
    summary="Comparative resource matrix (Official vs Citizen vs AI vs Freshness)",
)
async def get_institution_comparison(
    institution_id: uuid.UUID,
    session: DbSession,
) -> InstitutionComparisonRead:
    """Generate comparative matrix of resources and observation reports."""
    return await gov_service.get_institution_comparison(session, institution_id=institution_id)


# -----------------------------------------------------------------------------
# 2. Public Data Sources Registry
# -----------------------------------------------------------------------------


@govdata_router.get(
    "/api/v1/govdata/sources",
    response_model=list[DataSourceRead],
    summary="List approved government data sources",
)
async def list_data_sources(
    session: DbSession,
    source_type: Annotated[str | None, Query(description="Filter by source type")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Items limit")] = 50,
) -> list[DataSourceRead]:
    """List approved official data sources and update freshness."""
    return await gov_service.list_data_sources(session, source_type=source_type, limit=limit)


@govdata_router.get(
    "/api/v1/govdata/sources/{source_id}",
    response_model=DataSourceRead,
    summary="Retrieve data source details",
)
async def get_data_source(
    source_id: uuid.UUID,
    session: DbSession,
) -> DataSourceRead:
    """Retrieve a specific registered data source by ID."""
    return await gov_service.get_data_source(session, source_id=source_id)


# -----------------------------------------------------------------------------
# 3. Admin Ingestion, Entity Matches & Data Quality
# -----------------------------------------------------------------------------


@govdata_router.post(
    "/api/v1/govdata/sources",
    response_model=DataSourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new official data source (Admin/Analyst)",
)
async def create_data_source(
    payload: DataSourceCreate,
    session: DbSession,
    request: Request,
    user: AdminOrAnalyst,
) -> DataSourceRead:
    """Register a new official source in the approved registry."""
    src = await gov_service.create_data_source(session, payload)
    await audit(
        session,
        action="govdata.source_create",
        entity_type="data_source",
        entity_id=src.id,
        actor_id=user.id,
        after=payload.model_dump(mode="json"),
        request=request,
    )
    await session.commit()
    return src


@govdata_router.post(
    "/api/v1/govdata/imports",
    response_model=ImportJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger dataset import & entity resolution job (Admin/Analyst)",
)
async def trigger_import_job(
    payload: ImportJobCreate,
    session: DbSession,
    request: Request,
    user: AdminOrAnalyst,
) -> ImportJobRead:
    """Trigger an asynchronous or direct ingestion and matching job. Large
    imports run in the background worker (spec §32); ``preview_only`` returns
    the change-detection preview without writing (spec §70)."""
    job = await gov_service.trigger_import_job(
        session,
        dataset_id=payload.dataset_id,
        raw_payload=payload.raw_payload,
        dry_run=payload.dry_run,
        background=payload.background,
        force=payload.force,
        preview_only=payload.preview_only,
        request=request,
    )
    await audit(
        session,
        action="govdata.import_trigger",
        entity_type="gov_import_job",
        entity_id=job.id,
        actor_id=user.id,
        after={
            "dataset_id": str(payload.dataset_id),
            "dry_run": payload.dry_run,
            "background": payload.background,
            "force": payload.force,
            "preview_only": payload.preview_only,
        },
        request=request,
    )
    return job


@govdata_router.post(
    "/api/v1/govdata/imports/{job_id}/rollback",
    response_model=dict[str, Any],
    summary="Roll back a dataset import (Admin/Analyst, spec §71)",
)
async def rollback_import(
    job_id: uuid.UUID,
    session: DbSession,
    request: Request,
    user: AdminOrAnalyst,
) -> dict[str, Any]:
    """Safely undo a large import: drop its staged records and reverted
    institution canonical data. Historical rows from other jobs are kept."""
    result = await gov_service.rollback_import(session, job_id=job_id)
    await audit(
        session,
        action="govdata.import_rollback",
        entity_type="gov_import_job",
        entity_id=job_id,
        actor_id=user.id,
        after=result,
        request=request,
    )
    return result


@govdata_router.get(
    "/api/v1/govdata/catalog",
    response_model=list[dict[str, Any]],
    summary="Public data catalog (spec §44)",
)
async def get_data_catalog(session: DbSession) -> list[dict[str, Any]]:
    """Published datasets with measured quality dimensions (completeness,
    freshness, record count) — never an invented composite score."""
    return await gov_service.get_data_catalog(session)


@govdata_router.get(
    "/api/v1/govdata/connectors/health",
    response_model=list[dict[str, Any]],
    summary="Connector health & circuit-breaker view (Admin/Analyst, spec §37)",
)
async def get_connector_health(
    session: DbSession,
    user: AdminOrAnalyst = None,
) -> list[dict[str, Any]]:
    """Status, freshness, sync/failure times, records, rate limits per connector."""
    return await gov_service.get_connector_health(session)


@govdata_router.get(
    "/api/v1/govdata/lineage/institution/{institution_id}",
    response_model=dict[str, Any],
    summary="Data lineage for an institution (spec §60)",
)
async def get_institution_lineage(
    institution_id: uuid.UUID,
    session: DbSession,
    user: AdminOrAnalyst = None,
) -> dict[str, Any]:
    """Trace where an institution's data originated: source → dataset →
    external record → canonical institution → reports."""
    return await gov_service.get_institution_lineage(session, institution_id)


@govdata_router.get(
    "/api/v1/govdata/entity-matches",
    response_model=list[EntityMatchReviewRead],
    summary="List entity match review queue (Admin/Analyst)",
)
async def list_entity_matches(
    session: DbSession,
    dataset_id: Annotated[uuid.UUID | None, Query(description="Filter by dataset ID")] = None,
    review_status: Annotated[str | None, Query(description="Filter review status")] = "pending",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    user: AdminOrAnalyst = None,
) -> list[EntityMatchReviewRead]:
    """Retrieve imported records awaiting administrative entity match verification."""
    return await gov_service.list_entity_matches(
        session, dataset_id=dataset_id, review_status=review_status, limit=limit
    )


@govdata_router.post(
    "/api/v1/govdata/entity-matches/{review_id}/review",
    response_model=EntityMatchReviewRead,
    summary="Submit review decision for an entity match (Admin/Analyst)",
)
async def decide_entity_match(
    review_id: uuid.UUID,
    payload: EntityMatchReviewDecision,
    session: DbSession,
    request: Request,
    user: AdminOrAnalyst,
) -> EntityMatchReviewRead:
    """Confirm, reject, or reassign an entity match."""
    result = await gov_service.decide_entity_match(
        session, review_id=review_id, decision=payload, user_id=user.id
    )
    await audit(
        session,
        action="govdata.entity_match_review",
        entity_type="entity_match_review",
        entity_id=review_id,
        actor_id=user.id,
        after=payload.model_dump(mode="json"),
        request=request,
    )
    return result


@govdata_router.get(
    "/api/v1/govdata/data-quality",
    response_model=DataQualityReportRead,
    summary="Government data quality & coverage scorecard (Admin/Analyst)",
)
async def get_data_quality_report(
    session: DbSession,
    user: AdminOrAnalyst = None,
) -> DataQualityReportRead:
    """Retrieve platform-wide government data quality metrics."""
    return await gov_service.get_data_quality_report(session)
