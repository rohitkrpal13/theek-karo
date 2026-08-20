"""Phase 21 Civic Action Orchestration entities.

Converts civic intelligence (Phase 20) into coordinated, lawful civic action:
action plans, tasks, milestones, dependencies, volunteer applications and
assignments, teams, events, action evidence, human verification, and impact
measurement. Every entity reuses existing infrastructure (users, initiatives,
media, audit, notifications) — nothing here duplicates those systems.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
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


class ActionPlan(Base):
    """Execution plan attached to an approved civic initiative."""

    __tablename__ = "action_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="CASCADE"), unique=True, index=True
    )
    objective: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(
        String(32),
        default="PROPOSED",
        server_default="PROPOSED",
    )
    risk_notes: Mapped[list[dict[str, Any]]] = mapped_column(_jsonb(), default=list)
    # AI-assisted planning (approval gate): the AI-produced suggestion is stored
    # here and only materialized into tasks after a human approves it.
    ai_generated: Mapped[bool] = mapped_column(default=False)
    ai_suggestion: Mapped[dict[str, Any] | None] = mapped_column(_jsonb(), nullable=True)
    ai_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    ai_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PROPOSED','OPEN','ACTIVE','BLOCKED','COMPLETED',"
            "'VERIFICATION_PENDING','VERIFIED','CANCELLED')",
            name="ck_action_plans_status",
        ),
    )


class ActionTask(Base):
    """A unit of work inside an action plan."""

    __tablename__ = "action_tasks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_plans.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM", server_default="MEDIUM")
    status: Mapped[str] = mapped_column(
        String(32),
        default="TODO",
        server_default="TODO",
        index=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[dict[str, Any] | None] = mapped_column(_jsonb(), nullable=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(_jsonb(), default=list)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    blocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('TODO','ASSIGNED','IN_PROGRESS','BLOCKED','SUBMITTED',"
            "'VERIFICATION_PENDING','COMPLETED','CANCELLED')",
            name="ck_action_tasks_status",
        ),
        CheckConstraint(
            "priority IN ('LOW','MEDIUM','HIGH','URGENT')", name="ck_action_tasks_priority"
        ),
    )


class ActionMilestone(Base):
    """Named milestone inside an action plan (order by ``order_idx``)."""

    __tablename__ = "action_milestones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_plans.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    order_idx: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','in_progress','completed','cancelled')",
            name="ck_action_milestones_status",
        ),
    )


class ActionDependency(Base):
    """Task A depends on task B; A cannot be completed while B is incomplete."""

    __tablename__ = "action_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_tasks.id", ondelete="CASCADE"), index=True
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_tasks.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_action_dependencies"),
        CheckConstraint("task_id != depends_on_task_id", name="ck_action_dependencies_distinct"),
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_tasks.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ActionUpdate(Base):
    """Structured public update posted by participants (drives the action feed)."""

    __tablename__ = "action_updates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(Text)
    status_snapshot: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CivicTeam(Base):
    """A named working team inside an initiative (roles -> permissions)."""

    __tablename__ = "civic_teams"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CivicTeamMember(Base):
    __tablename__ = "civic_team_members"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_teams.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(24), default="field_volunteer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_civic_team_members"),
        CheckConstraint(
            "role IN ('coordinator','field_volunteer','evidence_reviewer','data_reviewer')",
            name="ck_civic_team_members_role",
        ),
    )


class VolunteerApplication(Base):
    """A volunteer's request to contribute to an initiative (optionally a task)."""

    __tablename__ = "volunteer_applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("action_tasks.id", ondelete="CASCADE"), index=True
    )
    applicant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected','withdrawn')",
            name="ck_volunteer_applications_status",
        ),
    )


class ActionEvidence(Base):
    """Evidence attached to an initiative/task. Bytes live in the existing media
    pipeline (mime/size/checksum/malware-scan gates); this row adds civic
    context (before/after, checklist, location) and the verification workflow."""

    __tablename__ = "action_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("action_plans.id", ondelete="CASCADE")
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("action_tasks.id", ondelete="CASCADE"), index=True
    )
    uploader_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    media_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_objects.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), default="general", server_default="general")
    notes: Mapped[str | None] = mapped_column(Text)
    checklist_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(_jsonb(), default=list)
    location: Mapped[dict[str, Any] | None] = mapped_column(_jsonb(), nullable=True)
    # Integrity metadata copied from the media object (checksum lives there).
    sha256: Mapped[str] = mapped_column(String(64), default="")
    mime_type: Mapped[str] = mapped_column(String(64), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    verification_status: Mapped[str] = mapped_column(
        String(16), default="unverified", server_default="unverified"
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('general','before','after','document','field_note')",
            name="ck_action_evidence_kind",
        ),
        CheckConstraint(
            "verification_status IN ('unverified','pending','approved','rejected')",
            name="ck_action_evidence_verification_status",
        ),
        Index("ix_action_evidence_initiative_task", "initiative_id", "task_id"),
    )


class ActionReview(Base):
    """Human verification of an outcome (initiative- or task-level)."""

    __tablename__ = "action_reviews"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    decision: Mapped[str] = mapped_column(String(16))
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    note: Mapped[str | None] = mapped_column(Text)
    evidence_ids: Mapped[list[str]] = mapped_column(_jsonb(), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "decision IN ('pending','approved','rejected')", name="ck_action_reviews_decision"
        ),
        CheckConstraint("entity_type IN ('initiative','task')", name="ck_action_reviews_entity"),
    )


class ImpactMetric(Base):
    """A measurable outcome for an initiative (baseline -> target)."""

    __tablename__ = "impact_metrics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("action_plans.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    baseline: Mapped[float] = mapped_column(Float, default=0)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str | None] = mapped_column(Text)
    methodology: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class ImpactMeasurement(Base):
    """A single measurement of an impact metric, tied to evidence + review."""

    __tablename__ = "impact_measurements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    metric_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("impact_metrics.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(Text)
    methodology_note: Mapped[str | None] = mapped_column(Text)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("action_evidence.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')", name="ck_impact_measurements_status"
        ),
    )


class CivicEvent(Base):
    """A lawful civic event (cleanup, awareness, audit, meeting, inspection)."""

    __tablename__ = "civic_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[dict[str, Any]] = mapped_column(_jsonb())
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organizer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requirements: Mapped[dict[str, Any]] = mapped_column(_jsonb(), default=dict)
    safety_info: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','submitted','published','cancelled','completed')",
            name="ck_civic_events_status",
        ),
    )


class EventParticipant(Base):
    __tablename__ = "event_participants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_events.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), default="joined", server_default="joined")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("event_id", "user_id", name="uq_event_participants"),
        CheckConstraint(
            "status IN ('joined','attended','cancelled')", name="ck_event_participants_status"
        ),
    )


class CampaignInitiativeLink(Base):
    """Links a civic campaign to the initiatives it coordinates."""

    __tablename__ = "campaign_initiatives"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("civic_initiatives.id", ondelete="CASCADE"), primary_key=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CampaignMember(Base):
    __tablename__ = "campaign_members"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member", server_default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        CheckConstraint("role IN ('member','organizer')", name="ck_campaign_members_role"),
    )
