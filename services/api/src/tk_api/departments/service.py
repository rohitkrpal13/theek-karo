"""Department registry, membership and jurisdiction service (PRD §18-§24).

Departments are configuration rows (never code). This module provides the
CRUD used by the admin registry, the membership + verification workflow used
by the identity side, and the jurisdiction predicate used by the case routing
engine. All writes are audited via the app-level ``audit()`` helper.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.errors import ApiError, ConflictError, NotFoundError
from tk_api.departments.models import (
    Department,
    DepartmentCategory,
    DepartmentType,
    DepartmentUser,
    JurisdictionScope,
    OrganizationVerification,
)

ALLOWED_SCOPES = frozenset({"full", "geography", "institution"})
ALLOWED_VERIFICATION_STATES = frozenset({"pending", "verified", "suspended", "revoked"})


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# department types
# ---------------------------------------------------------------------------


async def list_department_types(
    session: AsyncSession, *, include_inactive: bool = False
) -> list[DepartmentType]:
    stmt = select(DepartmentType).order_by(DepartmentType.code.asc())
    if not include_inactive:
        stmt = stmt.where(DepartmentType.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def get_department_type(session: AsyncSession, type_id: uuid.UUID) -> DepartmentType:
    row = await session.get(DepartmentType, type_id)
    if row is None:
        raise NotFoundError("department type not found", kind="department_type_not_found")
    return row


async def create_department_type(
    session: AsyncSession,
    *,
    code: str,
    name_key: str,
    is_active: bool = True,
) -> DepartmentType:
    existing = await session.scalar(select(DepartmentType).where(DepartmentType.code == code))
    if existing is not None:
        raise ConflictError(f"department type code already exists: {code}")
    row = DepartmentType(code=code, name_key=name_key, is_active=is_active)
    session.add(row)
    await session.flush()
    return row


# ---------------------------------------------------------------------------
# departments
# ---------------------------------------------------------------------------


async def list_departments(
    session: AsyncSession,
    *,
    include_inactive: bool = False,
    department_type_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Department]:
    stmt = select(Department).order_by(Department.name.asc())
    if not include_inactive:
        stmt = stmt.where(Department.status == "active")
    if department_type_id is not None:
        stmt = stmt.where(Department.department_type_id == department_type_id)
    if q:
        stmt = stmt.where(Department.name.ilike(f"%{q}%"))
    stmt = stmt.limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


async def get_department(session: AsyncSession, department_id: uuid.UUID) -> Department:
    row = await session.get(Department, department_id)
    if row is None:
        raise NotFoundError("department not found", kind="department_not_found")
    return row


async def get_department_by_slug(session: AsyncSession, slug: str) -> Department:
    row = await session.scalar(select(Department).where(Department.slug == slug))
    if row is None:
        raise NotFoundError("department not found", kind="department_not_found")
    return row


async def create_department(
    session: AsyncSession,
    *,
    slug: str,
    name: str,
    department_type_id: uuid.UUID,
    parent_department_id: uuid.UUID | None,
    jurisdiction_geography_id: uuid.UUID | None,
    description: str | None = None,
    official_contact: str | None = None,
    official_email: str | None = None,
    official_phone: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Department:
    if not slug or not slug.islower() or not slug.replace("-", "").isalnum():
        raise ApiError("slug must be lowercase alphanumeric with dashes", 422, "invalid_slug")
    existing = await session.scalar(select(Department).where(Department.slug == slug))
    if existing is not None:
        raise ConflictError(f"department slug already exists: {slug}")
    await get_department_type(session, department_type_id)
    row = Department(
        slug=slug,
        name=name,
        department_type_id=department_type_id,
        parent_department_id=parent_department_id,
        jurisdiction_geography_id=jurisdiction_geography_id,
        description=description,
        official_contact=official_contact,
        official_email=official_email,
        official_phone=official_phone,
        metadata=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def update_department(
    session: AsyncSession,
    department: Department,
    *,
    name: str | None = None,
    description: str | None = None,
    official_contact: str | None = None,
    official_email: str | None = None,
    official_phone: str | None = None,
    status: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Department:
    if status is not None and status not in ("active", "inactive", "suspended"):
        raise ApiError("invalid department status", 422, "invalid_status")
    if name is not None:
        department.name = name
    if description is not None:
        department.description = description
    if official_contact is not None:
        department.official_contact = official_contact
    if official_email is not None:
        department.official_email = official_email
    if official_phone is not None:
        department.official_phone = official_phone
    if status is not None:
        department.status = status
    if metadata is not None:
        merged = dict(department.meta or {})
        merged.update(metadata)
        department.meta = merged
    department.updated_at = _utcnow()
    await session.flush()
    return department


async def set_department_categories(
    session: AsyncSession,
    department: Department,
    *,
    category_ids: list[uuid.UUID],
) -> list[DepartmentCategory]:
    await session.execute(
        delete(DepartmentCategory).where(DepartmentCategory.department_id == department.id)
    )
    rows = [DepartmentCategory(department_id=department.id, category_id=c) for c in category_ids]
    if rows:
        session.add_all(rows)
    await session.flush()
    return rows


async def set_jurisdiction_scopes(
    session: AsyncSession,
    department: Department,
    *,
    scopes: list[dict[str, Any]],
) -> list[JurisdictionScope]:
    await session.execute(
        delete(JurisdictionScope).where(JurisdictionScope.department_id == department.id)
    )
    rows: list[JurisdictionScope] = []
    for scope in scopes:
        kind = scope.get("scope_kind")
        if kind not in ALLOWED_SCOPES:
            raise ApiError(f"invalid scope_kind: {kind}", 422, "invalid_scope_kind")
        rows.append(
            JurisdictionScope(
                department_id=department.id,
                geography_id=scope.get("geography_id"),
                institution_type_id=scope.get("institution_type_id"),
                scope_kind=kind,
                is_active=bool(scope.get("is_active", True)),
            )
        )
    if rows:
        session.add_all(rows)
    await session.flush()
    return rows


# ---------------------------------------------------------------------------
# membership + verification
# ---------------------------------------------------------------------------


async def department_member_user_ids(
    session: AsyncSession, department_id: uuid.UUID | None
) -> list[uuid.UUID]:
    """All active member user ids (used for case visibility + escalations)."""
    if department_id is None:
        return []
    rows = (
        (
            await session.execute(
                select(DepartmentUser).where(
                    DepartmentUser.department_id == department_id,
                    DepartmentUser.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    return [r.user_id for r in rows]


async def list_department_members(
    session: AsyncSession, department_id: uuid.UUID, *, include_inactive: bool = False
) -> list[DepartmentUser]:
    stmt = select(DepartmentUser).where(DepartmentUser.department_id == department_id)
    if not include_inactive:
        stmt = stmt.where(DepartmentUser.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def add_department_member(
    session: AsyncSession,
    department: Department,
    *,
    user_id: uuid.UUID,
    role_in_department: str = "member",
    scope_geography_id: uuid.UUID | None = None,
    verification_id: uuid.UUID | None = None,
) -> DepartmentUser:
    if role_in_department not in ("member", "manager", "reviewer"):
        raise ApiError("invalid role_in_department", 422, "invalid_role")
    existing = await session.scalar(
        select(DepartmentUser).where(
            DepartmentUser.user_id == user_id, DepartmentUser.department_id == department.id
        )
    )
    if existing is not None:
        raise ConflictError("user is already a member of this department")
    row = DepartmentUser(
        user_id=user_id,
        department_id=department.id,
        role_in_department=role_in_department,
        scope_geography_id=scope_geography_id,
        verification_id=verification_id,
    )
    session.add(row)
    await session.flush()
    return row


async def update_department_member(
    session: AsyncSession,
    membership: DepartmentUser,
    *,
    role_in_department: str | None = None,
    scope_geography_id: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> DepartmentUser:
    if role_in_department is not None:
        if role_in_department not in ("member", "manager", "reviewer"):
            raise ApiError("invalid role_in_department", 422, "invalid_role")
        membership.role_in_department = role_in_department
    if scope_geography_id is not None:
        membership.scope_geography_id = scope_geography_id
    if is_active is not None:
        membership.is_active = is_active
    membership.updated_at = _utcnow()
    await session.flush()
    return membership


async def remove_department_member(session: AsyncSession, membership: DepartmentUser) -> None:
    await session.delete(membership)
    await session.flush()


async def get_user_departments(
    session: AsyncSession, user_id: uuid.UUID, *, active_only: bool = True
) -> list[DepartmentUser]:
    stmt = select(DepartmentUser).where(DepartmentUser.user_id == user_id)
    if active_only:
        stmt = stmt.where(DepartmentUser.is_active.is_(True))
    return list((await session.execute(stmt)).scalars().all())


async def user_in_department(
    session: AsyncSession,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
) -> bool:
    row = await session.scalar(
        select(DepartmentUser).where(
            DepartmentUser.user_id == user_id,
            DepartmentUser.department_id == department_id,
            DepartmentUser.is_active.is_(True),
        )
    )
    return row is not None


async def user_manages_department(
    session: AsyncSession,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
) -> bool:
    row = await session.scalar(
        select(DepartmentUser).where(
            DepartmentUser.user_id == user_id,
            DepartmentUser.department_id == department_id,
            DepartmentUser.is_active.is_(True),
            DepartmentUser.role_in_department.in_(("manager", "reviewer")),
        )
    )
    return row is not None


# ---------------------------------------------------------------------------
# organization verification
# ---------------------------------------------------------------------------


async def create_organization_verification(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    organization_name: str,
    department_id: uuid.UUID | None,
    institution_id: uuid.UUID | None,
    submitted_email: str | None,
    submitted_reason: str | None,
) -> OrganizationVerification:
    if not organization_name.strip():
        raise ApiError("organization_name is required", 422, "invalid_payload")
    if department_id is None and institution_id is None:
        raise ApiError(
            "one of department_id or institution_id is required",
            422,
            "invalid_payload",
        )
    row = OrganizationVerification(
        user_id=user_id,
        organization_name=organization_name.strip(),
        department_id=department_id,
        institution_id=institution_id,
        submitted_email=submitted_email,
        submitted_reason=submitted_reason,
        verification_state="pending",
    )
    session.add(row)
    await session.flush()
    return row


async def list_organization_verifications(
    session: AsyncSession,
    *,
    state: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[OrganizationVerification]:
    stmt = select(OrganizationVerification).order_by(OrganizationVerification.created_at.desc())
    if state is not None:
        if state not in ALLOWED_VERIFICATION_STATES:
            raise ApiError("invalid verification state", 422, "invalid_state")
        stmt = stmt.where(OrganizationVerification.verification_state == state)
    if limit <= 0:
        return list((await session.execute(stmt)).scalars().all())
    return list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())


async def get_organization_verification(
    session: AsyncSession, verification_id: uuid.UUID
) -> OrganizationVerification:
    row = await session.get(OrganizationVerification, verification_id)
    if row is None:
        raise NotFoundError("verification not found", kind="verification_not_found")
    return row


async def review_organization_verification(
    session: AsyncSession,
    verification: OrganizationVerification,
    *,
    state: str,
    actor_id: uuid.UUID,
    scope_note: str | None = None,
) -> OrganizationVerification:
    if state not in ALLOWED_VERIFICATION_STATES:
        raise ApiError("invalid verification state", 422, "invalid_state")
    if verification.verification_state != "pending":
        raise ApiError(
            "only pending verifications may be reviewed", 409, "verification_not_pending"
        )
    verification.verification_state = state
    verification.verified_by = actor_id
    verification.verified_at = _utcnow()
    if scope_note is not None:
        verification.scope_note = scope_note
    if state == "verified" and verification.department_id is not None:
        member = DepartmentUser(
            user_id=verification.user_id,
            department_id=verification.department_id,
            role_in_department="member",
            verification_id=verification.id,
        )
        session.add(member)
    verification.updated_at = _utcnow()
    await session.flush()
    return verification
