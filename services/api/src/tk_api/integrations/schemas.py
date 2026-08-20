"""Schemas for the Phase 19 integration hub: connector health, data catalog,
webhook subscriptions, and delivery logs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConnectorHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    provider: str | None = None
    category: str | None = None
    auth_type: str
    endpoint: str | None = None
    version: str | None = None
    status: str
    consecutive_failures: int = 0
    last_sync_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_error: str | None = None
    retry_after_until: datetime | None = None
    records_imported: int = 0
    records_rejected: int = 0
    sync_frequency_hours: int | None = None
    schema_fingerprint: str | None = None
    freshness: str
    config: dict[str, Any] = Field(default_factory=dict)


class CatalogDatasetRead(BaseModel):
    """Public data catalog entry (spec §44): one row per published dataset."""

    dataset_id: uuid.UUID
    dataset_name: str
    publisher: str
    description: str | None = None
    coverage: str | None = None
    time_period: str | None = None
    source: str | None = None
    license: str | None = None
    last_update: datetime | None = None
    api: str | None = None
    download_options: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    # Quality dimensions (spec §45) — never an invented composite score
    completeness: float | None = None
    freshness: str | None = None
    record_count: int = 0
    duplicate_rate: float | None = None
    conflict_rate: float | None = None
    connector_code: str | None = None
    connector_status: str | None = None


class WebhookSubscriptionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    url: str = Field(min_length=8)
    events: list[str] = Field(min_length=1)


class WebhookSubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    url: str
    events: list[str]
    status: str
    secret_key_id: str
    created_at: datetime


class WebhookDeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subscription_id: uuid.UUID
    subscription_name: str | None = None
    outbox_event_id: uuid.UUID
    status: str
    http_status: int | None = None
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime


class SyncTriggerRead(BaseModel):
    job_id: uuid.UUID
    dataset_id: uuid.UUID
    connector_code: str
    status: str
    queued: bool
    note: str


class RollbackResultRead(BaseModel):
    job_id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    records_removed: int
    matches_removed: int
    institutions_affected: int
