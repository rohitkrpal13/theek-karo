"""Pydantic schemas for Institutions domain (PRD §5, API.md §7)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InstitutionTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_key: str
    attribute_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime


class InstitutionAttributeDefRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_type_id: uuid.UUID
    code: str
    value_type: str
    required: bool = False
    unit: str | None = None
    description: str | None = None
    created_at: datetime


class InstitutionAttributeValueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    definition_id: uuid.UUID
    code: str | None = None
    string_value: str | None = None
    integer_value: int | None = None
    decimal_value: float | None = None
    boolean_value: bool | None = None
    date_value: str | None = None
    enum_value: str | None = None
    source_id: uuid.UUID | None = None


class InstitutionTranslationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    locale: str
    name: str
    short_description: str | None = None
    created_at: datetime


class InstitutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_type_id: uuid.UUID
    name: str
    normalized_name: str
    official_identifier: str | None = None
    address: str | None = None
    geography_id: uuid.UUID | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    website: str | None = None
    management_type: str | None = None
    operational_status: str = "active"
    verification_state: str = "unverified"
    created_at: datetime
    updated_at: datetime


class InstitutionDetailRead(InstitutionRead):
    type: InstitutionTypeRead | None = None
    attributes: list[InstitutionAttributeValueRead] = Field(default_factory=list)
    translations: list[InstitutionTranslationRead] = Field(default_factory=list)


class InstitutionCreate(BaseModel):
    institution_type_id: uuid.UUID
    name: str = Field(min_length=2, max_length=255)
    official_identifier: str | None = None
    address: str | None = None
    geography_id: uuid.UUID | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    website: str | None = None
    management_type: str | None = None
    source_id: uuid.UUID | None = None
    source_identifier: str | None = None
    meta: dict[str, Any] | None = None


class InstitutionUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=255)
    address: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    website: str | None = None
    management_type: str | None = None
    operational_status: str | None = None
    verification_state: str | None = None
    meta: dict[str, Any] | None = None
