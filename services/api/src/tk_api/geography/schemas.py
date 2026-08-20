"""Pydantic schemas for Geography domain (API.md, PRD §3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GeographyTypeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name_key: str
    parent_type_id: uuid.UUID | None = None
    sort_order: int = 0
    supports_geometry: bool = True
    is_active: bool = True
    created_at: datetime


class GeographyTranslationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    locale: str
    name: str
    transliteration: str | None = None
    source: str = "community"
    created_at: datetime


class GeographyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type_id: uuid.UUID
    name: str
    normalized_name: str
    parent_id: uuid.UUID | None = None
    country_code: str
    official_identifier: str | None = None
    alternate_names: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class GeographyDetailRead(GeographyRead):
    type_code: str | None = None
    translations: list[GeographyTranslationRead] = Field(default_factory=list)
    parent: GeographyRead | None = None


class GeographyHierarchyNode(BaseModel):
    id: uuid.UUID
    name: str
    type_code: str
    parent_id: uuid.UUID | None = None
    children_count: int = 0


class GeographyCreate(BaseModel):
    type_id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None = None
    country_code: str = "IND"
    official_identifier: str | None = None
    alternate_names: dict[str, Any] | None = None
