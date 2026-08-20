"""Resolution, reputation, subscriptions, devices (PRD S16-S19, S21; Phase 14)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from tk_api.core.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _jsonb() -> JSON:
    return JSON().with_variant(JSONB, "postgresql")


class ResolutionSubmission(Base):
    __tablename__ = "resolution_submissions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cases.id", ondelete="SET NULL"), index=True
    )
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="submitted")
    notes: Mapped[str | None] = mapped_column(Text)
    responsible_party: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    resolution_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reference_numbers: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', 'verified', 'rejected', "
            "'more_evidence_required', 'partially_verified', 'disputed')",
            name="ck_resolution_submissions_status",
        ),
    )


class ResolutionEvidence(Base):
    __tablename__ = "resolution_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    resolution_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resolution_submissions.id", ondelete="CASCADE")
    )
    media_object_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("media_objects.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    document_kind: Mapped[str | None] = mapped_column(Text)
    before_after: Mapped[str | None] = mapped_column(String(16))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checksum: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "before_after IS NULL OR before_after IN ('before', 'after', 'neutral')",
            name="ck_resolution_evidence_before_after",
        ),
        CheckConstraint(
            "visibility IN ('public', 'internal')", name="ck_resolution_evidence_visibility"
        ),
    )


class ResolutionReview(Base):
    """Independent review of a resolution submission (separation of duties).

    The decision moves the submission state machine; the reviewer must not be
    the submitter and ``conflict_of_interest`` is always recorded.
    """

    __tablename__ = "resolution_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    resolution_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resolution_submissions.id", ondelete="CASCADE")
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str | None] = mapped_column(Text)
    ai_assessment: Mapped[dict[str, Any] | None] = mapped_column(_jsonb())
    conflict_of_interest: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('verified', 'more_evidence_required', 'rejected', 'partially_verified')",
            name="ck_resolution_reviews_decision",
        ),
    )


class ResolutionVerification(Base):
    __tablename__ = "resolution_verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    resolution_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resolution_submissions.id", ondelete="CASCADE")
    )
    verifier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decision: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ResolutionFollowup(Base):
    """One citizen signal per case on a verified resolution (PRD §B.2).

    "observed_improvement" feeds the two-confirmer gate (reporter + one more
    citizen -> ``cases.community_confirmed_at`` set); "issue_still_exists"
    feeds the reopen signal. Unique per (case, user) so a user cannot signal
    twice; the signal is a review trigger, never an auto-reopen/close.
    """

    __tablename__ = "resolution_followups"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    resolution_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resolution_submissions.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    signal: Mapped[str] = mapped_column(String(24))
    observation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("case_id", "user_id", name="uq_resolution_followups_case_user"),
        CheckConstraint(
            "signal IN ('observed_improvement', 'issue_still_exists')",
            name="ck_resolution_followups_signal",
        ),
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'escalated', 'dismissed')",
            name="ck_resolution_followups_status",
        ),
    )


class ResolutionReopenSignal(Base):
    """Aggregate "issue still exists" signal queued for human review.

    Created when the reopen threshold of distinct citizen followups is met;
    never reopens a case by itself. Approving routes the case through the
    existing reopen-request machinery; dismissing closes the signal.
    """

    __tablename__ = "resolution_reopen_signals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"))
    signal_count: Mapped[int] = mapped_column(Integer)
    raised_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'dismissed')",
            name="ck_resolution_reopen_signals_status",
        ),
    )


class ResolutionDispute(Base):
    __tablename__ = "resolution_disputes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    resolution_submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resolution_submissions.id", ondelete="CASCADE")
    )
    raised_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReputationPolicy(Base):
    __tablename__ = "reputation_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_kind: Mapped[str] = mapped_column(String(64), unique=True)
    delta: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ReputationEvent(Base):
    __tablename__ = "reputation_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_kind: Mapped[str] = mapped_column(String(64))
    delta: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(32))
    content_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subscriber_kind: Mapped[str] = mapped_column(String(16))
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE")
    )
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE")
    )
    geography_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("geographies.id", ondelete="CASCADE")
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE")
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(Text, unique=True)
    platform: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
