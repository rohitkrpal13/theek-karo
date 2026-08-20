"""AI entities (DATABASE.md §3.6, §8; ADR-018).

``ai_runs`` logs every model call with PII-insulated payloads (ADR-019);
``ai_annotations`` carries the T4 envelope (content is always ``AI_ANALYSIS`` —
enforced by a CHECK constraint so AI can never self-declare verified status);
``ai_reviews`` is the human review queue (ADR-018: AI only suggests, humans
decide).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AiRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_kind: Mapped[str] = mapped_column(String(64), index=True)
    model_id: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    payload_in: Mapped[dict[str, Any]] = mapped_column(_jsonb())
    payload_out: Mapped[dict[str, Any]] = mapped_column(_jsonb())
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))  # succeeded|failed|flagged|needs_review
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[str | None] = mapped_column(String(64), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))  # user|assistant|system|tool
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(_jsonb())
    tool_calls: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(_jsonb())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiAnnotation(Base):
    __tablename__ = "ai_annotations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT"), index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ai_runs.id", ondelete="RESTRICT"))
    content: Mapped[dict[str, Any]] = mapped_column(_jsonb())
    info_class: Mapped[str] = mapped_column(String(32), default="AI_ANALYSIS")
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    model_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint("info_class = 'AI_ANALYSIS'", name="ck_ai_annotations_info_class"),
    )


class AiCitation(Base):
    __tablename__ = "ai_citations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    annotation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_annotations.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="RESTRICT")
    )
    url: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiReview(Base):
    __tablename__ = "ai_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32))  # duplicate_merge (ADR-018)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    annotation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ai_annotations.id", ondelete="RESTRICT")
    )
    suggested_report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="RESTRICT")
    )
    similarity: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|approved|rejected
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_ai_reviews_status"
        ),
    )


# --- Cycle-2 AI domain (PRD §23): outputs, feedback, evaluations.


class AiOutput(Base):
    __tablename__ = "ai_outputs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_runs.id", ondelete="CASCADE"), index=True
    )
    capability: Mapped[str] = mapped_column(String(64))
    output: Mapped[dict[str, Any]] = mapped_column(_jsonb())
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(String(16), default="succeeded")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiFeedback(Base):
    __tablename__ = "ai_feedback"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    ai_output_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_outputs.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AiEvaluation(Base):
    __tablename__ = "ai_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    eval_name: Mapped[str] = mapped_column(String(64))
    capability: Mapped[str] = mapped_column(String(64))
    dataset_ref: Mapped[str] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(_jsonb())
    model_id: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
