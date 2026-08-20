"""Department registry & organization entities (Phase 14).

Departments are configuration data, never hard-coded: a department carries a
type, an optional parent (hierarchy), a jurisdiction geography, category
coverage (``department_categories``) and explicit jurisdiction scopes.
``DepartmentUser`` scopes who inside the department can act on cases; the
global role codes (``department_representative`` / ``department_manager`` /
``reviewer``) gate capabilities while membership + scopes gate *which* cases.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DepartmentType(Base):
    __tablename__ = "department_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name_key: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(Text)
    department_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("department_types.id", ondelete="RESTRICT"), index=True
    )
    parent_department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    jurisdiction_geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="RESTRICT"), index=True
    )
    description: Mapped[str | None] = mapped_column(Text)
    official_contact: Mapped[str | None] = mapped_column(Text)
    official_email: Mapped[str | None] = mapped_column(Text)
    official_phone: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="active")
    meta: Mapped[dict[str, Any] | None] = mapped_column("metadata", _jsonb(), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'inactive', 'suspended')", name="ck_departments_status"
        ),
    )


class DepartmentCategory(Base):
    """Category coverage: routes reports in a category to this department."""

    __tablename__ = "department_categories"

    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class JurisdictionScope(Base):
    """Explicit coverage rule: full, a geography subtree, or an institution type."""

    __tablename__ = "jurisdiction_scopes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="CASCADE")
    )
    institution_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institution_types.id", ondelete="CASCADE")
    )
    scope_kind: Mapped[str] = mapped_column(String(16), default="full")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "scope_kind IN ('full', 'geography', 'institution')",
            name="ck_jurisdiction_scopes_kind",
        ),
    )


class OrganizationVerification(Base):
    """Administrative verification of an authorized departmental identity.

    An email domain alone never proves authority: an admin reviews the claim
    (state machine pending → verified | revoked; suspension is reversible).
    """

    __tablename__ = "organization_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    organization_name: Mapped[str] = mapped_column(Text)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL")
    )
    verification_state: Mapped[str] = mapped_column(String(16), default="pending")
    submitted_email: Mapped[str | None] = mapped_column(Text)
    submitted_reason: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "verification_state IN ('pending', 'verified', 'suspended', 'revoked')",
            name="ck_organization_verifications_state",
        ),
    )


class DepartmentUser(Base):
    """Membership + jurisdiction scope of a user inside a department."""

    __tablename__ = "department_users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), index=True
    )
    role_in_department: Mapped[str] = mapped_column(String(16), default="member")
    scope_geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="SET NULL")
    )
    verification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organization_verifications.id", ondelete="SET NULL")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "department_id", name="uq_department_users_membership"),
        CheckConstraint(
            "role_in_department IN ('member', 'manager', 'reviewer')",
            name="ck_department_users_role",
        ),
    )
