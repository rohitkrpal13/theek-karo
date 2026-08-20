"""Pydantic v2 schemas for Phase 11 AI, RAG, Tools, Assistant, and Structured Outputs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# -----------------------------------------------------------------------------
# 1. Citations & Evidence
# -----------------------------------------------------------------------------


class CitationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str | None = None
    dataset_name: str
    dataset_version: str | None = None
    publication_date: str | None = None
    url: str | None = None
    snippet: str


# -----------------------------------------------------------------------------
# 2. Structured Task Outputs
# -----------------------------------------------------------------------------


class ReportClassificationOutput(BaseModel):
    category_slug: str
    issue_type_slug: str | None = None
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    department_hint: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.7)
    rationale: str | None = None


class DuplicateAnalysisOutput(BaseModel):
    is_duplicate: bool = False
    similarity_score: float = Field(ge=0.0, le=1.0, default=0.0)
    duplicate_candidate_id: str | None = None
    duplicate_ticket_no: str | None = None
    rationale: str | None = None


class InstitutionSummaryOutput(BaseModel):
    institution_id: str
    institution_name: str
    situation_summary: str
    total_reports_analyzed: int = 0
    verified_reports_count: int = 0
    dominant_categories: list[str] = Field(default_factory=list)
    official_data_freshness: str | None = None
    discrepancy_note: str | None = None
    citations: list[CitationItem] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 3. Conversational Civic Assistant
# -----------------------------------------------------------------------------


class CivicChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)
    conversation_id: uuid.UUID | None = None
    session_id: str | None = None
    language: str = "en"
    geography_id: uuid.UUID | None = None
    institution_id: uuid.UUID | None = None


class RelatedEntityRef(BaseModel):
    id: str
    kind: Literal["report", "institution", "geography"]
    title: str
    subtitle: str | None = None


class CivicChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    evidence_points: list[str] = Field(default_factory=list)
    citations: list[CitationItem] = Field(default_factory=list)
    data_freshness_note: str | None = None
    related_entities: list[RelatedEntityRef] = Field(default_factory=list)
    language: str = "en"
    confidence_label: Literal["high", "moderate", "low", "uncertain"] = "moderate"
    model_info: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# -----------------------------------------------------------------------------
# 4. Translation & Multilingual
# -----------------------------------------------------------------------------


class TranslationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source_language: str = "auto"
    target_language: str = "en"


class TranslationResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    model_id: str
    confidence: float = 0.9


# -----------------------------------------------------------------------------
# 5. Feedback & Cost Analytics
# -----------------------------------------------------------------------------


class AiFeedbackCreate(BaseModel):
    ai_output_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    rating: int = Field(ge=1, le=5)
    feedback_type: Literal["helpful", "not_helpful", "incorrect", "missing_info"] = "helpful"
    comment: str | None = None


class AiUsageStatsRead(BaseModel):
    total_runs: int
    total_tokens_in: int
    total_tokens_out: int
    total_cost_usd: float
    model_breakdown: dict[str, int]
    provider_breakdown: dict[str, int]
    average_latency_ms: float
