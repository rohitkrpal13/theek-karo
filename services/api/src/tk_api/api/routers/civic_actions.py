"""Phase 21 civic-action endpoints (PRD §20, API.md §19).

Prefix ``/api/v1/civic-actions``: action plans, tasks, milestones,
dependencies, updates, volunteer applications, teams, campaign links,
events, evidence + verification, outcome reviews, impact metrics and
measurements (AI-assisted planning goes through an explicit approval gate).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from tk_api.api.deps import CurrentUser, DbSession, require_active
from tk_api.civic_action import evidence as evidence_service
from tk_api.civic_action import service as action_service
from tk_api.civic_action import volunteers as volunteer_service
from tk_api.civic_action.ai_tools import generate_ai_plan_draft, plan_from_suggestion
from tk_api.civic_action.schemas import (
    ActionPlanCreate,
    ActionPlanUpdate,
    ActionTaskCreate,
    ActionTaskUpdate,
    ActionUpdateCreate,
    AiPlanApproval,
    CampaignLinkBody,
    CivicEventCreate,
    CivicEventUpdate,
    CivicTeamCreate,
    CivicTeamMemberBody,
    DependencyCreate,
    EvidenceCreate,
    EvidenceReviewBody,
    ImpactMeasurementCreate,
    ImpactMeasurementDecision,
    ImpactMetricCreate,
    MilestoneCreate,
    MilestoneUpdate,
    ReviewCreate,
    TaskAssignBody,
    TaskCommentCreate,
    VolunteerApplicationCreate,
    VolunteerApplicationDecision,
)
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit

civic_action_router = APIRouter(prefix="/api/v1/civic-actions", tags=["civic-actions"])

ActiveUser = Annotated[Any, Depends(require_active())]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, f"invalid_{kind}_id") from exc


# ---------------------------------------------------------------------------
# Action plans
# ---------------------------------------------------------------------------


@civic_action_router.post("/plans", status_code=201, summary="Create an action plan")
async def create_plan(
    body: ActionPlanCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.create_plan(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get("/plans", summary="List action plans")
async def list_plans(
    user: CurrentUser,
    session: DbSession,
    initiative_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative") if initiative_id else None
    return await action_service.list_plans(
        session,
        viewer=user,
        initiative_id=parsed,
        status=status,
        limit=limit,
        offset=offset,
    )


@civic_action_router.get("/plans/{plan_id}", summary="Get an action plan")
async def get_plan(plan_id: str, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await action_service.get_plan(session, _parse_id(plan_id, kind="plan"), viewer=user)


@civic_action_router.patch("/plans/{plan_id}", summary="Update an action plan")
async def update_plan(
    plan_id: str,
    body: ActionPlanUpdate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.update_plan(
        session,
        plan_id=_parse_id(plan_id, kind="plan"),
        actor=user,
        data=body.model_dump(exclude_unset=True),
        request=request,
    )


@civic_action_router.post(
    "/plans/{plan_id}/verify", summary="Human verification of a completed plan"
)
async def verify_plan(
    plan_id: str,
    body: AiPlanApproval,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    if body.decision not in ("approve", "reject"):
        raise ApiError("decision must be approve or reject", 422, "invalid_decision")
    return await action_service.complete_plan_verification(
        session,
        plan_id=_parse_id(plan_id, kind="plan"),
        actor=user,
        decision="approved" if body.decision == "approve" else "rejected",
        request=request,
    )


@civic_action_router.post(
    "/plans/{plan_id}/ai-suggest",
    summary="Generate an AI GENERATED draft plan (requires human approval)",
)
async def ai_suggest_plan(
    plan_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(plan_id, kind="plan")
    plan = await action_service.get_plan(session, parsed, viewer=user)
    suggestion = await generate_ai_plan_draft(
        session, _parse_id(plan["initiative_id"], kind="initiative")
    )
    return await action_service.store_ai_plan_suggestion(
        session, plan_id=parsed, actor=user, suggestion=suggestion, request=request
    )


@civic_action_router.post(
    "/plans/{plan_id}/ai-decide",
    summary="Human approval gate for an AI-generated draft plan",
)
async def ai_decide_plan(
    plan_id: str,
    body: AiPlanApproval,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(plan_id, kind="plan")
    plan = await action_service.decide_ai_plan_suggestion(
        session, plan_id=parsed, actor=user, decision=body.decision, request=request
    )
    if body.decision == "approve" and plan.get("ai_suggestion"):
        created = []
        for item in await plan_from_suggestion(session, plan["ai_suggestion"]):
            rule = {
                "plan_id": str(parsed),
                "title": item["title"],
                "description": item.get("description"),
                "priority": item.get("priority"),
                "checklist": item.get("checklist") or [],
            }
            created.append(
                await action_service.create_task(session, actor=user, data=rule, request=request)
            )
        plan["tasks"] = created
    return plan


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@civic_action_router.post("/tasks", status_code=201, summary="Create a task")
async def create_task(
    body: ActionTaskCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.create_task(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.patch("/tasks/{task_id}", summary="Update a task")
async def update_task(
    task_id: str,
    body: ActionTaskUpdate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.update_task(
        session,
        task_id=_parse_id(task_id, kind="task"),
        actor=user,
        data=body.model_dump(exclude_unset=True),
        request=request,
    )


@civic_action_router.delete("/tasks/{task_id}", summary="Delete a task")
async def delete_task(
    task_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.delete_task(
        session,
        task_id=_parse_id(task_id, kind="task"),
        actor=user,
        request=request,
    )


@civic_action_router.post("/tasks/{task_id}/assign", summary="Assign a task")
async def assign_task(
    task_id: str,
    body: TaskAssignBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.assign_task(
        session,
        task_id=_parse_id(task_id, kind="task"),
        actor=user,
        assignee_id=action_service._require_uuid(body.assignee_id, "assignee_id"),
        request=request,
    )


@civic_action_router.post("/tasks/{task_id}/comments", status_code=201, summary="Comment on a task")
async def add_task_comment(
    task_id: str,
    body: TaskCommentCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="civic-actions",
        key=f"comment:{client_ip(request)}",
        limit=20,
        window_seconds=60,
    )
    return await action_service.add_task_comment(
        session,
        task_id=_parse_id(task_id, kind="task"),
        actor=user,
        body=body.body,
        request=request,
    )


@civic_action_router.get("/tasks/{task_id}/comments", summary="List task comments")
async def list_task_comments(
    task_id: str,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    return await action_service.list_task_comments(
        session, _parse_id(task_id, kind="task"), viewer=user, limit=limit
    )


@civic_action_router.post(
    "/tasks/{task_id}/dependencies", status_code=201, summary="Add a task dependency"
)
async def add_dependency(
    task_id: str,
    body: DependencyCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed_task = _parse_id(task_id, kind="task")
    parsed_dep = _parse_id(body.depends_on_task_id, kind="task")
    if parsed_task == parsed_dep:
        raise ApiError("a task cannot depend on itself", 422, "self_dependency")
    return await action_service.add_dependency(
        session,
        task_id=parsed_task,
        depends_on_task_id=parsed_dep,
        actor=user,
        request=request,
    )


@civic_action_router.delete(
    "/tasks/{task_id}/dependencies/{depends_on_task_id}",
    summary="Remove a task dependency",
)
async def remove_dependency(
    task_id: str,
    depends_on_task_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.remove_dependency(
        session,
        task_id=_parse_id(task_id, kind="task"),
        depends_on_task_id=_parse_id(depends_on_task_id, kind="task"),
        actor=user,
        request=request,
    )


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


@civic_action_router.post("/milestones", status_code=201, summary="Create a milestone")
async def create_milestone(
    body: MilestoneCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.create_milestone(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.patch("/milestones/{milestone_id}", summary="Update a milestone")
async def update_milestone(
    milestone_id: str,
    body: MilestoneUpdate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.update_milestone(
        session,
        milestone_id=_parse_id(milestone_id, kind="milestone"),
        actor=user,
        data=body.model_dump(exclude_unset=True),
        request=request,
    )


# ---------------------------------------------------------------------------
# Updates + progress
# ---------------------------------------------------------------------------


@civic_action_router.post("/updates", status_code=201, summary="Post an initiative update")
async def add_update(
    body: ActionUpdateCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await action_service.add_action_update(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get("/initiatives/{initiative_id}/updates", summary="List initiative updates")
async def list_updates(
    initiative_id: str,
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await action_service.list_action_updates(
        session,
        _parse_id(initiative_id, kind="initiative"),
        viewer=user,
        limit=limit,
        offset=offset,
    )


@civic_action_router.get("/plans/{plan_id}/progress", summary="Deterministic progress rollup")
async def plan_progress(plan_id: str, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await evidence_service.plan_progress(
        session, viewer=user, plan_id=_parse_id(plan_id, kind="plan")
    )


# ---------------------------------------------------------------------------
# Volunteer applications
# ---------------------------------------------------------------------------


@civic_action_router.post("/volunteer-applications", status_code=201, summary="Apply to volunteer")
async def apply_to_initiative(
    body: VolunteerApplicationCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="civic-actions",
        key=f"apply:{client_ip(request)}",
        limit=10,
        window_seconds=60,
    )
    return await volunteer_service.apply_to_initiative(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get("/volunteer-applications/my", summary="List my volunteer applications")
async def my_applications(
    user: CurrentUser,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    return await volunteer_service.my_applications(session, actor=user, limit=limit, offset=offset)


@civic_action_router.get(
    "/initiatives/{initiative_id}/applications", summary="Applications for an initiative"
)
async def list_applications(
    initiative_id: str,
    user: ActiveUser,
    session: DbSession,
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    return await volunteer_service.list_applications(
        session,
        actor=user,
        initiative_id=_parse_id(initiative_id, kind="initiative"),
        status=status,
    )


@civic_action_router.post(
    "/volunteer-applications/{application_id}/decide",
    summary="Decide a volunteer application",
)
async def decide_application(
    application_id: str,
    body: VolunteerApplicationDecision,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.decide_application(
        session,
        application_id=_parse_id(application_id, kind="application"),
        actor=user,
        decision=body.decision,
        request=request,
    )


@civic_action_router.post(
    "/volunteer-applications/{application_id}/withdraw",
    summary="Withdraw my application",
)
async def withdraw_application(
    application_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.withdraw_application(
        session,
        application_id=_parse_id(application_id, kind="application"),
        actor=user,
        request=request,
    )


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------


@civic_action_router.post("/teams", status_code=201, summary="Create a civic team")
async def create_team(
    body: CivicTeamCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.create_team(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get(
    "/initiatives/{initiative_id}/teams", summary="List teams of an initiative"
)
async def list_teams(initiative_id: str, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await volunteer_service.list_teams(
        session,
        actor=user,
        initiative_id=_parse_id(initiative_id, kind="initiative"),
    )


@civic_action_router.post("/teams/{team_id}/members", status_code=201, summary="Add a team member")
async def add_team_member(
    team_id: str,
    body: CivicTeamMemberBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.add_team_member(
        session,
        team_id=_parse_id(team_id, kind="team"),
        actor=user,
        user_id=action_service._require_uuid(body.user_id, "user_id"),
        role=body.role,
        request=request,
    )


@civic_action_router.delete("/teams/{team_id}/members/{user_id}", summary="Remove a team member")
async def remove_team_member(
    team_id: str,
    user_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.remove_team_member(
        session,
        team_id=_parse_id(team_id, kind="team"),
        actor=user,
        user_id=_parse_id(user_id, kind="user"),
        request=request,
    )


# ---------------------------------------------------------------------------
# Campaign links + members
# ---------------------------------------------------------------------------


@civic_action_router.post(
    "/campaign-links", status_code=201, summary="Link an initiative to a campaign"
)
async def link_campaign_initiative(
    body: CampaignLinkBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.link_campaign_initiative(
        session,
        actor=user,
        campaign_id=_parse_id(body.campaign_id, kind="campaign"),
        initiative_id=_parse_id(body.initiative_id, kind="initiative"),
        request=request,
    )


@civic_action_router.post(
    "/campaigns/{campaign_id}/join", status_code=201, summary="Join a campaign"
)
async def join_campaign(
    campaign_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.join_campaign(
        session,
        actor=user,
        campaign_id=_parse_id(campaign_id, kind="campaign"),
        request=request,
    )


# ---------------------------------------------------------------------------
# Civic events
# ---------------------------------------------------------------------------


@civic_action_router.post("/events", status_code=201, summary="Create a civic event")
async def create_event(
    body: CivicEventCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.create_event(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.patch("/events/{event_id}", summary="Update an event")
async def update_event(
    event_id: str,
    body: CivicEventUpdate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.update_event(
        session,
        event_id=_parse_id(event_id, kind="event"),
        actor=user,
        data=body.model_dump(exclude_unset=True),
        request=request,
    )


@civic_action_router.get("/events", summary="List civic events")
async def list_events(
    user: CurrentUser,
    session: DbSession,
    initiative_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    parsed = _parse_id(initiative_id, kind="initiative") if initiative_id else None
    return await volunteer_service.list_events(
        session,
        viewer=user,
        initiative_id=parsed,
        status=status,
        limit=limit,
        offset=offset,
    )


@civic_action_router.get("/events/{event_id}", summary="Get an event")
async def get_event(event_id: str, user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await volunteer_service.get_event(
        session, _parse_id(event_id, kind="event"), viewer=user
    )


@civic_action_router.post("/events/{event_id}/join", status_code=201, summary="Join an event")
async def join_event(
    event_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.join_event(
        session, event_id=_parse_id(event_id, kind="event"), actor=user, request=request
    )


@civic_action_router.post("/events/{event_id}/cancel", summary="Cancel my event participation")
async def cancel_event_participation(
    event_id: str,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await volunteer_service.cancel_event_participation(
        session, event_id=_parse_id(event_id, kind="event"), actor=user, request=request
    )


# ---------------------------------------------------------------------------
# Evidence + reviews
# ---------------------------------------------------------------------------


@civic_action_router.post("/evidence", status_code=201, summary="Attach evidence")
async def attach_evidence(
    body: EvidenceCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="civic-actions",
        key=f"evidence:{client_ip(request)}",
        limit=20,
        window_seconds=60,
    )
    return await evidence_service.attach_evidence(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get("/evidence", summary="List evidence")
async def list_evidence(
    user: CurrentUser,
    session: DbSession,
    initiative_id: str,
    task_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    parsed_task = _parse_id(task_id, kind="task") if task_id else None
    return await evidence_service.list_evidence(
        session,
        viewer=user,
        initiative_id=_parse_id(initiative_id, kind="initiative"),
        task_id=parsed_task,
        limit=limit,
        offset=offset,
    )


@civic_action_router.post("/evidence/{evidence_id}/review", summary="Review evidence (human)")
async def review_evidence(
    evidence_id: str,
    body: EvidenceReviewBody,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await evidence_service.review_evidence(
        session,
        evidence_id=_parse_id(evidence_id, kind="evidence"),
        actor=user,
        decision=body.decision,
        note=body.note,
        request=request,
    )


@civic_action_router.post("/reviews", status_code=201, summary="Record an outcome review")
async def create_review(
    body: ReviewCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await evidence_service.create_review(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get("/reviews", summary="List outcome reviews")
async def list_reviews(
    user: CurrentUser,
    session: DbSession,
    entity_type: str,
    entity_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return await evidence_service.list_reviews(
        session,
        viewer=user,
        entity_type=entity_type,
        entity_id=_parse_id(entity_id, kind="entity"),
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Impact
# ---------------------------------------------------------------------------


@civic_action_router.post("/impact/metrics", status_code=201, summary="Create an impact metric")
async def create_impact_metric(
    body: ImpactMetricCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await evidence_service.create_impact_metric(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.get("/impact/metrics", summary="List impact metrics")
async def list_impact_metrics(
    user: CurrentUser,
    session: DbSession,
    plan_id: str,
) -> dict[str, Any]:
    return await evidence_service.list_impact_metrics(
        session, viewer=user, plan_id=_parse_id(plan_id, kind="plan")
    )


@civic_action_router.post(
    "/impact/measurements", status_code=201, summary="Record an impact measurement"
)
async def record_measurement(
    body: ImpactMeasurementCreate,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await evidence_service.record_measurement(
        session, actor=user, data=body.model_dump(), request=request
    )


@civic_action_router.post(
    "/impact/measurements/{measurement_id}/decide",
    summary="Human review of an impact measurement",
)
async def decide_measurement(
    measurement_id: str,
    body: ImpactMeasurementDecision,
    request: Request,
    user: ActiveUser,
    session: DbSession,
) -> dict[str, Any]:
    return await evidence_service.decide_measurement(
        session,
        measurement_id=_parse_id(measurement_id, kind="measurement"),
        actor=user,
        decision=body.decision,
        request=request,
    )


@civic_action_router.get("/impact/dashboard", summary="Verified impact dashboard for an initiative")
async def impact_dashboard(
    user: CurrentUser,
    session: DbSession,
    initiative_id: str,
) -> dict[str, Any]:
    return await evidence_service.impact_dashboard(
        session,
        viewer=user,
        initiative_id=_parse_id(initiative_id, kind="initiative"),
    )
