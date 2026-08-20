"""Department registry, membership & verification API (PRD §19-§24)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_permission
from tk_api.core.errors import ApiError, NotFoundError
from tk_api.departments import service
from tk_api.departments.models import Department, DepartmentUser
from tk_api.departments.schemas import (
    DepartmentCategoryWrite,
    DepartmentCreate,
    DepartmentJurisdictionsWrite,
    DepartmentMemberCreate,
    DepartmentMemberUpdate,
    DepartmentTypeCreate,
    DepartmentUpdate,
    OrganizationVerificationCreate,
    OrganizationVerificationReview,
)

departments_router = APIRouter(prefix="/api/v1/departments", tags=["departments"])

DepDepartmentsRead = Annotated[Any, Depends(require_permission("departments.read"))]
DepDepartmentsManage = Annotated[Any, Depends(require_permission("departments.manage"))]
DepMembersManage = Annotated[Any, Depends(require_permission("departments.members.manage"))]
DepVerifyOrg = Annotated[Any, Depends(require_permission("departments.verify_org"))]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, "invalid_id") from exc


# ---------------------------------------------------------------------------
# registry (read is public for logged-in users; write is admin)
# ---------------------------------------------------------------------------


@departments_router.get("/types", summary="List department types")
async def list_types(
    session: DbSession,
    _user: DepDepartmentsRead,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[dict[str, Any]]:
    rows = await service.list_department_types(session, include_inactive=include_inactive)
    return [
        {
            "id": str(r.id),
            "code": r.code,
            "name_key": r.name_key,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@departments_router.post("/types", status_code=201, summary="Create a department type")
async def create_type(
    body: DepartmentTypeCreate,
    session: DbSession,
    _user: DepDepartmentsManage,
) -> dict[str, Any]:
    row = await service.create_department_type(
        session, code=body.code, name_key=body.name_key, is_active=body.is_active
    )
    await session.commit()
    return {"id": str(row.id), "code": row.code}


@departments_router.get("", summary="List departments")
async def list_departments(
    session: DbSession,
    _user: DepDepartmentsRead,
    include_inactive: Annotated[bool, Query()] = False,
    department_type_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    rows = await service.list_departments(
        session,
        include_inactive=include_inactive,
        department_type_id=department_type_id,
        q=q,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "slug": r.slug,
                "name": r.name,
                "department_type_id": str(r.department_type_id),
                "parent_department_id": str(r.parent_department_id)
                if r.parent_department_id
                else None,
                "jurisdiction_geography_id": str(r.jurisdiction_geography_id)
                if r.jurisdiction_geography_id
                else None,
                "description": r.description,
                "status": r.status,
                "metadata": r.meta or {},
            }
            for r in rows
        ],
        "count": len(rows),
    }


@departments_router.get("/me", summary="Departments of the current user")
async def my_departments(
    session: DbSession,
    user: CurrentUser,
    _perm: DepDepartmentsRead,
) -> list[dict[str, Any]]:
    memberships = await service.get_user_departments(session, user.id)
    out: list[dict[str, Any]] = []
    for m in memberships:
        dept = await session.get(Department, m.department_id)
        out.append(
            {
                "department_id": str(m.department_id),
                "department_name": dept.name if dept else None,
                "department_slug": dept.slug if dept else None,
                "role_in_department": m.role_in_department,
                "scope_geography_id": str(m.scope_geography_id) if m.scope_geography_id else None,
                "is_active": m.is_active,
            }
        )
    return out


@departments_router.get("/{department_id}", summary="Department detail")
async def get_department(
    department_id: str,
    session: DbSession,
    _user: DepDepartmentsRead,
) -> dict[str, Any]:
    dept = await service.get_department(session, _parse_id(department_id, kind="department"))
    return {
        "id": str(dept.id),
        "slug": dept.slug,
        "name": dept.name,
        "department_type_id": str(dept.department_type_id),
        "parent_department_id": str(dept.parent_department_id)
        if dept.parent_department_id
        else None,
        "jurisdiction_geography_id": str(dept.jurisdiction_geography_id)
        if dept.jurisdiction_geography_id
        else None,
        "description": dept.description,
        "official_contact": dept.official_contact,
        "official_email": dept.official_email,
        "official_phone": dept.official_phone,
        "status": dept.status,
        "metadata": dept.meta or {},
        "created_at": dept.created_at,
        "updated_at": dept.updated_at,
    }


@departments_router.post("", status_code=201, summary="Create a department")
async def create_department(
    body: DepartmentCreate,
    session: DbSession,
    _user: DepDepartmentsManage,
) -> dict[str, Any]:
    row = await service.create_department(
        session,
        slug=body.slug,
        name=body.name,
        department_type_id=body.department_type_id,
        parent_department_id=body.parent_department_id,
        jurisdiction_geography_id=body.jurisdiction_geography_id,
        description=body.description,
        official_contact=body.official_contact,
        official_email=body.official_email,
        official_phone=body.official_phone,
        metadata=body.metadata,
    )
    await session.commit()
    return {"id": str(row.id), "slug": row.slug}


@departments_router.patch("/{department_id}", summary="Update a department")
async def update_department(
    department_id: str,
    body: DepartmentUpdate,
    session: DbSession,
    _user: DepDepartmentsManage,
) -> dict[str, Any]:
    dept = await service.get_department(session, _parse_id(department_id, kind="department"))
    row = await service.update_department(
        session,
        dept,
        name=body.name,
        description=body.description,
        official_contact=body.official_contact,
        official_email=body.official_email,
        official_phone=body.official_phone,
        status=body.status,
        metadata=body.metadata,
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@departments_router.put(
    "/{department_id}/categories", summary="Replace department category coverage"
)
async def set_categories(
    department_id: str,
    body: DepartmentCategoryWrite,
    session: DbSession,
    _user: DepDepartmentsManage,
) -> dict[str, Any]:
    dept = await service.get_department(session, _parse_id(department_id, kind="department"))
    rows = await service.set_department_categories(session, dept, category_ids=body.category_ids)
    await session.commit()
    return {"count": len(rows)}


@departments_router.put(
    "/{department_id}/jurisdictions", summary="Replace department jurisdiction scopes"
)
async def set_jurisdictions(
    department_id: str,
    body: DepartmentJurisdictionsWrite,
    session: DbSession,
    _user: DepDepartmentsManage,
) -> dict[str, Any]:
    dept = await service.get_department(session, _parse_id(department_id, kind="department"))
    rows = await service.set_jurisdiction_scopes(
        session, dept, scopes=[s.model_dump() for s in body.scopes]
    )
    await session.commit()
    return {"count": len(rows)}


# ---------------------------------------------------------------------------
# membership
# ---------------------------------------------------------------------------


@departments_router.get("/{department_id}/members", summary="List department members")
async def list_members(
    department_id: str,
    session: DbSession,
    _user: DepMembersManage,
    include_inactive: Annotated[bool, Query()] = False,
) -> list[dict[str, Any]]:
    dept = await service.get_department(session, _parse_id(department_id, kind="department"))
    rows = await service.list_department_members(
        session, dept.id, include_inactive=include_inactive
    )
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "department_id": str(r.department_id),
            "role_in_department": r.role_in_department,
            "scope_geography_id": str(r.scope_geography_id) if r.scope_geography_id else None,
            "is_active": r.is_active,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@departments_router.post(
    "/{department_id}/members", status_code=201, summary="Add a department member"
)
async def add_member(
    department_id: str,
    body: DepartmentMemberCreate,
    session: DbSession,
    _user: DepMembersManage,
) -> dict[str, Any]:
    dept = await service.get_department(session, _parse_id(department_id, kind="department"))
    row = await service.add_department_member(
        session,
        dept,
        user_id=body.user_id,
        role_in_department=body.role_in_department,
        scope_geography_id=body.scope_geography_id,
    )
    await session.commit()
    return {"id": str(row.id), "user_id": str(row.user_id)}


@departments_router.patch(
    "/{department_id}/members/{membership_id}", summary="Update a department member"
)
async def update_member(
    department_id: str,
    membership_id: str,
    body: DepartmentMemberUpdate,
    session: DbSession,
    _user: DepMembersManage,
) -> dict[str, Any]:
    _ = _parse_id(department_id, kind="department")
    membership = await session.get(DepartmentUser, _parse_id(membership_id, kind="membership"))
    if membership is None:
        raise NotFoundError("membership not found", kind="membership_not_found")
    row = await service.update_department_member(
        session,
        membership,
        role_in_department=body.role_in_department,
        scope_geography_id=body.scope_geography_id,
        is_active=body.is_active,
    )
    await session.commit()
    return {"id": str(row.id), "is_active": row.is_active}


@departments_router.delete(
    "/{department_id}/members/{membership_id}",
    status_code=204,
    summary="Remove a department member",
)
async def remove_member(
    department_id: str,
    membership_id: str,
    session: DbSession,
    _user: DepMembersManage,
) -> None:
    _ = _parse_id(department_id, kind="department")
    membership = await session.get(DepartmentUser, _parse_id(membership_id, kind="membership"))
    if membership is None:
        raise NotFoundError("membership not found", kind="membership_not_found")
    await service.remove_department_member(session, membership)
    await session.commit()


# ---------------------------------------------------------------------------
# organization verification
# ---------------------------------------------------------------------------


@departments_router.post(
    "/verifications", status_code=201, summary="Request departmental identity verification"
)
async def request_verification(
    body: OrganizationVerificationCreate,
    session: DbSession,
    user: CurrentUser,
) -> dict[str, Any]:
    row = await service.create_organization_verification(
        session,
        user_id=user.id,
        organization_name=body.organization_name,
        department_id=body.department_id,
        institution_id=body.institution_id,
        submitted_email=body.submitted_email,
        submitted_reason=body.submitted_reason,
    )
    await session.commit()
    return {"id": str(row.id), "verification_state": row.verification_state}


@departments_router.get("/verifications", summary="List organization verifications")
async def list_verifications(
    session: DbSession,
    _user: DepVerifyOrg,
    state: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    rows = await service.list_organization_verifications(
        session, state=state, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "user_id": str(r.user_id),
                "organization_name": r.organization_name,
                "department_id": str(r.department_id) if r.department_id else None,
                "institution_id": str(r.institution_id) if r.institution_id else None,
                "verification_state": r.verification_state,
                "submitted_email": r.submitted_email,
                "submitted_reason": r.submitted_reason,
                "verified_by": str(r.verified_by) if r.verified_by else None,
                "verified_at": r.verified_at,
                "scope_note": r.scope_note,
                "created_at": r.created_at,
            }
            for r in rows
        ],
        "count": len(rows),
    }


@departments_router.post(
    "/verifications/{verification_id}/review", summary="Review an organization verification"
)
async def review_verification(
    verification_id: str,
    body: OrganizationVerificationReview,
    session: DbSession,
    user: CurrentUser,
    _perm: DepVerifyOrg,
) -> dict[str, Any]:
    verification = await service.get_organization_verification(
        session, _parse_id(verification_id, kind="verification")
    )
    row = await service.review_organization_verification(
        session,
        verification,
        state=body.state,
        actor_id=user.id,
        scope_note=body.scope_note,
    )
    await session.commit()
    return {"id": str(row.id), "verification_state": row.verification_state}
