"""Civic endpoint payload schemas (API.md §4)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CATEGORY_SLUG_PATTERN = r"^[a-z0-9_-]+$"
CAMPAIGN_STATUSES = ("planned", "live", "paused", "closed")


class CategoryCreate(BaseModel):
    slug: str = Field(pattern=CATEGORY_SLUG_PATTERN, min_length=1, max_length=64)
    icon: str = Field(min_length=1, max_length=32)
    form_schema: dict[str, Any]
    verification_policy: dict[str, Any]
    attachment_rules: dict[str, Any] = Field(default_factory=dict)
    default_locale_keys: dict[str, Any] | None = None


class CategoryUpdate(BaseModel):
    slug: str | None = Field(
        default=None, pattern=CATEGORY_SLUG_PATTERN, min_length=1, max_length=64
    )
    icon: str | None = Field(default=None, min_length=1, max_length=32)
    form_schema: dict[str, Any] | None = None
    verification_policy: dict[str, Any] | None = None
    attachment_rules: dict[str, Any] | None = None
    default_locale_keys: dict[str, Any] | None = None
    is_active: bool | None = None


class CategoryRead(BaseModel):
    id: uuid.UUID
    slug: str
    icon: str
    form_schema: dict[str, Any]
    verification_policy: dict[str, Any]
    attachment_rules: dict[str, Any] = Field(default_factory=dict)
    default_locale_keys: dict[str, Any] | None = None
    form_schema_version: int = 1
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class CategoryTranslationRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    locale: str
    name: str
    description: str | None = None
    created_at: datetime


class IssueTypeRead(BaseModel):
    id: uuid.UUID
    category_id: uuid.UUID
    slug: str
    name: str
    description: str | None = None
    form_schema: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class IssueTypeCreate(BaseModel):
    category_id: uuid.UUID
    slug: str = Field(pattern=CATEGORY_SLUG_PATTERN, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    form_schema: dict[str, Any] = Field(default_factory=dict)


class CategoryDetailRead(CategoryRead):
    issue_types: list[IssueTypeRead] = Field(default_factory=list)
    translations: list[CategoryTranslationRead] = Field(default_factory=list)


class CampaignCreate(BaseModel):
    category_id: uuid.UUID
    slug: str = Field(pattern=CATEGORY_SLUG_PATTERN, min_length=1, max_length=64)
    title_key: str = Field(min_length=1, max_length=120)
    scope: dict[str, Any] = Field(default_factory=dict)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: Literal["planned"] = "planned"


class CampaignUpdate(BaseModel):
    slug: str | None = Field(
        default=None, pattern=CATEGORY_SLUG_PATTERN, min_length=1, max_length=64
    )
    title_key: str | None = Field(default=None, min_length=1, max_length=120)
    scope: dict[str, Any] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: Literal["planned", "live", "paused", "closed"] | None = None
