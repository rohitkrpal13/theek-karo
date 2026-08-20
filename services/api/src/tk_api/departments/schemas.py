"""Pydantic schemas for the department registry & membership APIs (Phase 14)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DepartmentTypeRead(BaseModel):
    id: uuid.UUID
    code: str
    name_key: str
    is_active: bool
    created_at: datetime


class DepartmentTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name_key: str = Field(min_length=1)
    is_active: bool = True


class DepartmentCategoryWrite(BaseModel):
    category_ids: list[uuid.UUID] = []


class DepartmentJurisdictionsWrite(BaseModel):
    scopes: list[JurisdictionScopeWrite]


class JurisdictionScopeWrite(BaseModel):
    scope_kind: str
    geography_id: uuid.UUID | None = None
    institution_type_id: uuid.UUID | None = None
    is_active: bool = True


class DepartmentCreate(BaseModel):
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1)
    department_type_id: uuid.UUID
    parent_department_id: uuid.UUID | None = None
    jurisdiction_geography_id: uuid.UUID | None = None
    description: str | None = None
    official_contact: str | None = None
    official_email: str | None = None
    official_phone: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DepartmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    official_contact: str | None = None
    official_email: str | None = None
    official_phone: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None


class DepartmentRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    department_type_id: uuid.UUID
    parent_department_id: uuid.UUID | None
    jurisdiction_geography_id: uuid.UUID | None
    description: str | None
    official_contact: str | None
    official_email: str | None
    official_phone: str | None
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DepartmentMemberCreate(BaseModel):
    user_id: uuid.UUID
    role_in_department: str = "member"
    scope_geography_id: uuid.UUID | None = None


class DepartmentMemberUpdate(BaseModel):
    role_in_department: str | None = None
    scope_geography_id: uuid.UUID | None = None
    is_active: bool | None = None


class DepartmentMemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    department_id: uuid.UUID
    role_in_department: str
    scope_geography_id: uuid.UUID | None
    is_active: bool
    created_at: datetime


class OrganizationVerificationCreate(BaseModel):
    organization_name: str = Field(min_length=1)
    department_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None
    submitted_email: str | None = None
    submitted_reason: str | None = None


class OrganizationVerificationReview(BaseModel):
    state: str
    scope_note: str | None = None


class OrganizationVerificationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    organization_name: str
    department_id: uuid.UUID | None
    institution_id: uuid.UUID | None
    verification_state: str
    submitted_email: str | None
    submitted_reason: str | None
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    scope_note: str | None
    created_at: datetime
