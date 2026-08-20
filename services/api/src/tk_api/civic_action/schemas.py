"""Phase 21 civic-action request/response schemas (PRD §20, API.md §19)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PlanStatus = Literal[
    "PROPOSED",
    "OPEN",
    "ACTIVE",
    "BLOCKED",
    "COMPLETED",
    "VERIFICATION_PENDING",
    "VERIFIED",
    "CANCELLED",
]
TaskStatus = Literal[
    "TODO",
    "ASSIGNED",
    "IN_PROGRESS",
    "BLOCKED",
    "SUBMITTED",
    "VERIFICATION_PENDING",
    "COMPLETED",
    "CANCELLED",
]
TaskPriority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]
EvidenceKind = Literal["general", "before", "after", "document", "field_note"]
EvidenceStatus = Literal["unverified", "pending", "approved", "rejected"]
ReviewDecision = Literal["pending", "approved", "rejected"]
TeamRole = Literal["coordinator", "field_volunteer", "evidence_reviewer", "data_reviewer"]


class ActionPlanCreate(BaseModel):
    initiative_id: str
    objective: str = Field(min_length=10, max_length=4000)
    owner_id: str | None = Field(default=None, max_length=64)
    risk_notes: list[dict[str, Any]] = Field(default_factory=list)


class ActionPlanUpdate(BaseModel):
    objective: str | None = Field(default=None, min_length=10, max_length=4000)
    status: PlanStatus | None = None
    risk_notes: list[dict[str, Any]] | None = None


class AiPlanSuggestion(BaseModel):
    """Body for the AI-assisted planning endpoint (approval gate enforced
    server-side: the suggestion is stored, never applied directly)."""

    initiative_id: str
    locale: str = Field(default="en", max_length=8)


class AiPlanApproval(BaseModel):
    """Human approval that materializes a stored AI suggestion into tasks."""

    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=2000)


class ActionTaskCreate(BaseModel):
    plan_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: TaskPriority = "MEDIUM"
    due_at: str | None = None
    location: dict[str, Any] | None = None
    institution_id: str | None = Field(default=None, max_length=64)
    checklist: list[dict[str, Any]] = Field(default_factory=list)


class ActionTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_at: str | None = None
    location: dict[str, Any] | None = None
    institution_id: str | None = Field(default=None, max_length=64)
    checklist: list[dict[str, Any]] | None = None
    blocked_reason: str | None = Field(default=None, max_length=1000)


class TaskAssignBody(BaseModel):
    assignee_id: str


class MilestoneCreate(BaseModel):
    plan_id: str
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    order_idx: int = Field(default=0, ge=0)
    due_at: str | None = None


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    status: Literal["pending", "in_progress", "completed", "cancelled"] | None = None
    order_idx: int | None = Field(default=None, ge=0)
    due_at: str | None = None


class DependencyCreate(BaseModel):
    depends_on_task_id: str


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ActionUpdateCreate(BaseModel):
    initiative_id: str
    description: str = Field(min_length=5, max_length=4000)


class VolunteerApplicationCreate(BaseModel):
    initiative_id: str
    task_id: str | None = Field(default=None, max_length=64)
    message: str | None = Field(default=None, max_length=2000)


class VolunteerApplicationDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class CivicTeamCreate(BaseModel):
    initiative_id: str
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class CivicTeamMemberBody(BaseModel):
    user_id: str
    role: TeamRole = "field_volunteer"


class CampaignLinkBody(BaseModel):
    campaign_id: str
    initiative_id: str


class CampaignMemberBody(BaseModel):
    campaign_id: str
    user_id: str
    role: Literal["member", "organizer"] = "member"


class CivicEventCreate(BaseModel):
    initiative_id: str | None = Field(default=None, max_length=64)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    location: dict[str, Any] = Field(default_factory=dict)
    starts_at: str
    ends_at: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    safety_info: str | None = Field(default=None, max_length=4000)


class CivicEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    location: dict[str, Any] | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    requirements: list[dict[str, Any]] | None = None
    safety_info: str | None = Field(default=None, max_length=4000)
    status: Literal["draft", "submitted", "published", "cancelled", "completed"] | None = None


class EventParticipantBody(BaseModel):
    event_id: str
    status: Literal["joined", "attended", "cancelled"] | None = None


class EvidenceCreate(BaseModel):
    """Associate an already-uploaded MediaObject with an initiative/task."""

    initiative_id: str
    media_id: str
    task_id: str | None = Field(default=None, max_length=64)
    plan_id: str | None = Field(default=None, max_length=64)
    kind: EvidenceKind = "general"
    notes: str | None = Field(default=None, max_length=4000)
    location: dict[str, Any] | None = None


class EvidenceReviewBody(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class ReviewCreate(BaseModel):
    entity_type: Literal["initiative", "task"]
    entity_id: str
    decision: Literal["approved", "rejected"] = "approved"
    note: str | None = Field(default=None, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list)


class ImpactMetricCreate(BaseModel):
    plan_id: str
    name: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    baseline: float = 0.0
    target: float | None = None
    unit: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=500)
    methodology: str | None = Field(default=None, max_length=4000)


class ImpactMeasurementCreate(BaseModel):
    metric_id: str
    value: float
    source: str | None = Field(default=None, max_length=500)
    methodology_note: str | None = Field(default=None, max_length=4000)
    evidence_id: str | None = Field(default=None, max_length=64)


class ImpactMeasurementDecision(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)
