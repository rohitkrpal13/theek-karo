"""Institution Digital Twin API endpoints (API.md §7, PRD §5)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status

from tk_api.api.deps import DbSession, require_roles
from tk_api.core.audit import audit
from tk_api.core.pagination import PageParams, PageResponse
from tk_api.institutions import service as inst_service
from tk_api.institutions.schemas import (
    InstitutionCreate,
    InstitutionDetailRead,
    InstitutionRead,
    InstitutionTypeRead,
    InstitutionUpdate,
)

institutions_router = APIRouter(prefix="/api/v1/institutions", tags=["institutions"])


@institutions_router.get("/types", response_model=list[InstitutionTypeRead])
async def list_institution_types(session: DbSession) -> list[InstitutionTypeRead]:
    """List all supported institution types (school, hospital, ward office, etc.)."""
    return await inst_service.list_institution_types(session)


OfficialUser = Annotated[Any, Depends(require_roles("admin", "official"))]


@institutions_router.get("", response_model=PageResponse[InstitutionRead])
async def list_institutions(
    session: DbSession,
    type_id: Annotated[uuid.UUID | None, Query(description="Filter by institution type ID")] = None,
    geography_id: Annotated[uuid.UUID | None, Query(description="Filter by geography ID")] = None,
    operational_status: Annotated[
        str | None, Query(description="Filter by operational status")
    ] = None,
    verification_state: Annotated[
        str | None, Query(description="Filter by verification state")
    ] = None,
    q: Annotated[str | None, Query(description="Search term for name")] = None,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> PageResponse[InstitutionRead]:
    """Browse and filter institutions with pagination."""
    params = PageParams(page=page, limit=limit)
    return await inst_service.list_institutions(
        session,
        type_id=type_id,
        geography_id=geography_id,
        operational_status=operational_status,
        verification_state=verification_state,
        q=q,
        params=params,
    )


@institutions_router.get("/{inst_id}", response_model=InstitutionDetailRead)
async def get_institution_detail(
    inst_id: uuid.UUID,
    session: DbSession,
) -> InstitutionDetailRead:
    """Retrieve detailed institution digital twin record with attributes and translations."""
    return await inst_service.get_institution_detail(session, inst_id=inst_id)


@institutions_router.post("", response_model=InstitutionRead, status_code=status.HTTP_201_CREATED)
async def create_institution(
    payload: InstitutionCreate,
    session: DbSession,
    request: Request,
    user: OfficialUser,
) -> InstitutionRead:
    """Create a new institution (official / admin only)."""
    inst = await inst_service.create_institution(session, payload)
    await audit(
        session,
        action="institution.create",
        entity_type="institution",
        entity_id=inst.id,
        actor_id=user.id,
        after=payload.model_dump(mode="json"),
        request=request,
    )
    await session.commit()
    return inst


@institutions_router.patch("/{inst_id}", response_model=InstitutionRead)
async def update_institution(
    inst_id: uuid.UUID,
    payload: InstitutionUpdate,
    session: DbSession,
    request: Request,
    user: OfficialUser,
) -> InstitutionRead:
    """Update an institution record (official / admin only)."""
    inst = await inst_service.update_institution(session, inst_id, payload)
    await audit(
        session,
        action="institution.update",
        entity_type="institution",
        entity_id=inst_id,
        actor_id=user.id,
        after=payload.model_dump(mode="json", exclude_none=True),
        request=request,
    )
    await session.commit()
    return inst
