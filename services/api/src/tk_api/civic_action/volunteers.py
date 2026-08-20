"""Phase 21 volunteer coordination: applications, civic teams, campaign
initiative links, and civic events.

Design rules:

* Volunteer PII (phone, email, address, exact location) is never exposed;
  matches surface only public profile preferences (skills/availability).
* Applications belong to a single initiative; decisions are made by the plan
  owner / initiative initiator / moderator and are audited.
* Team roles gate what the member can do (coordinator, field_volunteer,
  evidence_reviewer, data_reviewer).
* Events: organizer submits, moderator publishes (public visibility gate).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.civic.models import Campaign
from tk_api.civic_action.models import (
    ActionPlan,
    CampaignInitiativeLink,
    CampaignMember,
    CivicEvent,
    CivicTeam,
    CivicTeamMember,
    EventParticipant,
    VolunteerApplication,
)
from tk_api.civic_action.service import (
    _coerce_uuid,
    _get_initiative,
    _get_plan,
    _get_task,
    _initiative_visibility,
    _is_moderator,
    _require_uuid,
)
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.notifications.events import enqueue_for_users
from tk_api.users.models import User


def _payload_application(app: VolunteerApplication) -> dict[str, Any]:
    return {
        "id": str(app.id),
        "initiative_id": str(app.initiative_id),
        "task_id": str(app.task_id) if app.task_id else None,
        "applicant_id": str(app.applicant_id),
        "message": app.message,
        "status": app.status,
        "decided_by": str(app.decided_by) if app.decided_by else None,
        "decided_at": app.decided_at.isoformat() if app.decided_at else None,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }


def _payload_team(team: CivicTeam, members: Sequence[CivicTeamMember]) -> dict[str, Any]:
    return {
        "id": str(team.id),
        "initiative_id": str(team.initiative_id),
        "name": team.name,
        "description": team.description,
        "members": [
            {
                "id": str(m.id),
                "user_id": str(m.user_id),
                "role": m.role,
            }
            for m in members
        ],
    }


def _payload_event(event: CivicEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "initiative_id": str(event.initiative_id) if event.initiative_id else None,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "starts_at": event.starts_at.isoformat() if event.starts_at else None,
        "ends_at": event.ends_at.isoformat() if event.ends_at else None,
        "organizer_id": str(event.organizer_id),
        "capacity": event.capacity,
        "requirements": event.requirements,
        "safety_info": event.safety_info,
        "status": event.status,
    }


async def _can_manage_volunteers(
    session: AsyncSession, initiative_id: uuid.UUID, actor: User
) -> bool:
    if _is_moderator(actor):
        return True
    initiative = await _get_initiative(session, initiative_id)
    if initiative.initiator_id == actor.id:
        return True
    plan = await session.scalar(select(ActionPlan).where(ActionPlan.initiative_id == initiative_id))
    return plan is not None and plan.owner_id == actor.id


# ---------------------------------------------------------------------------
# Volunteer applications
# ---------------------------------------------------------------------------


async def apply_to_initiative(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _require_uuid(data.get("initiative_id"), "initiative_id")
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, actor):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if initiative.status not in ("approved", "active"):
        raise ApiError("this initiative is not open to volunteers", 409, "initiative_not_open")
    task_id = _coerce_uuid(data.get("task_id"), "task_id")
    if task_id is not None:
        task = await _get_task(session, task_id)
        task_plan = await _get_plan(session, task.plan_id)
        if task_plan.initiative_id != initiative_id:
            raise ApiError("task does not belong to this initiative", 422, "task_mismatch")
    existing = await session.scalar(
        select(VolunteerApplication.id).where(
            VolunteerApplication.initiative_id == initiative_id,
            VolunteerApplication.applicant_id == actor.id,
            VolunteerApplication.status == "pending",
        )
    )
    if existing is not None:
        raise ApiError("you already have a pending application", 409, "application_exists")
    app = VolunteerApplication(
        initiative_id=initiative_id,
        task_id=task_id,
        applicant_id=actor.id,
        message=data.get("message"),
        status="pending",
    )
    session.add(app)
    await session.flush()
    owners = {initiative.initiator_id}
    plan: ActionPlan | None = await session.scalar(
        select(ActionPlan).where(ActionPlan.initiative_id == initiative_id)
    )
    if plan is not None:
        owners.add(plan.owner_id)
    await enqueue_for_users(
        session,
        user_ids=list(owners),
        event="civic_action.volunteer_applied",
        payload={"initiative_id": str(initiative_id), "application_id": str(app.id)},
        channels=["in_app"],
    )
    await audit(
        session,
        action="civic_action.volunteer_apply",
        entity_type="volunteer_application",
        entity_id=app.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _payload_application(app)


async def list_applications(
    session: AsyncSession,
    *,
    actor: User,
    initiative_id: uuid.UUID,
    status: str | None,
) -> dict[str, Any]:
    if not await _can_manage_volunteers(session, initiative_id, actor):
        raise ApiError("not permitted to view applications", 403, "forbidden")
    stmt = (
        select(VolunteerApplication)
        .where(VolunteerApplication.initiative_id == initiative_id)
        .order_by(VolunteerApplication.created_at.desc())
    )
    if status:
        stmt = stmt.where(VolunteerApplication.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return {"items": [_payload_application(a) for a in rows]}


async def decide_application(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    actor: User,
    decision: str,
    request: Request,
) -> dict[str, Any]:
    app = await session.get(VolunteerApplication, application_id)
    if app is None:
        raise ApiError("application not found", 404, "application_not_found")
    if not await _can_manage_volunteers(session, app.initiative_id, actor):
        raise ApiError("not permitted to decide applications", 403, "forbidden")
    if app.status != "pending":
        raise ApiError("application is already decided", 409, "application_decided")
    if decision not in ("approved", "rejected"):
        raise ApiError("decision must be approved or rejected", 422, "invalid_decision")
    app.status = decision
    app.decided_by = actor.id
    app.decided_at = datetime.now(UTC)
    await enqueue_for_users(
        session,
        user_ids=[app.applicant_id],
        event="civic_action.volunteer_decision",
        payload={"status": decision, "initiative_id": str(app.initiative_id)},
        channels=["in_app"],
    )
    await audit(
        session,
        action="civic_action.volunteer_decide",
        entity_type="volunteer_application",
        entity_id=app.id,
        actor_id=actor.id,
        after={"decision": decision},
        request=request,
    )
    await session.commit()
    return _payload_application(app)


async def withdraw_application(
    session: AsyncSession,
    *,
    application_id: uuid.UUID,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    app = await session.get(VolunteerApplication, application_id)
    if app is None or app.applicant_id != actor.id:
        raise ApiError("application not found", 404, "application_not_found")
    if app.status != "pending":
        raise ApiError("only pending applications can be withdrawn", 409, "application_decided")
    app.status = "withdrawn"
    await audit(
        session,
        action="civic_action.volunteer_withdraw",
        entity_type="volunteer_application",
        entity_id=app.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _payload_application(app)


async def my_applications(
    session: AsyncSession, *, actor: User, limit: int, offset: int
) -> dict[str, Any]:
    rows = (
        (
            await session.execute(
                select(VolunteerApplication)
                .where(VolunteerApplication.applicant_id == actor.id)
                .order_by(VolunteerApplication.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return {"items": [_payload_application(a) for a in rows], "count": len(rows)}


# ---------------------------------------------------------------------------
# Civic teams
# ---------------------------------------------------------------------------


async def create_team(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _require_uuid(data.get("initiative_id"), "initiative_id")
    if not await _can_manage_volunteers(session, initiative_id, actor):
        raise ApiError("not permitted to create teams", 403, "forbidden")
    name = str(data.get("name") or "").strip()
    if len(name) < 3:
        raise ApiError("name must be at least 3 characters", 422, "invalid_name")
    team = CivicTeam(
        initiative_id=initiative_id,
        name=name,
        description=data.get("description"),
        created_by=actor.id,
    )
    session.add(team)
    await session.flush()
    coordinator = CivicTeamMember(team_id=team.id, user_id=actor.id, role="coordinator")
    session.add(coordinator)
    await session.flush()
    await audit(
        session,
        action="civic_action.team_create",
        entity_type="civic_team",
        entity_id=team.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _payload_team(team, [coordinator])


async def list_teams(
    session: AsyncSession, *, actor: User, initiative_id: uuid.UUID
) -> dict[str, Any]:
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, actor):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    teams = (
        (await session.execute(select(CivicTeam).where(CivicTeam.initiative_id == initiative_id)))
        .scalars()
        .all()
    )
    items = []
    for team in teams:
        members = (
            (
                await session.execute(
                    select(CivicTeamMember).where(CivicTeamMember.team_id == team.id)
                )
            )
            .scalars()
            .all()
        )
        items.append(_payload_team(team, members))
    return {"items": items}


async def add_team_member(
    session: AsyncSession,
    *,
    team_id: uuid.UUID,
    actor: User,
    user_id: uuid.UUID,
    role: str,
    request: Request,
) -> dict[str, Any]:
    team = await session.get(CivicTeam, team_id)
    if team is None:
        raise ApiError("team not found", 404, "team_not_found")
    if not await _can_manage_volunteers(session, team.initiative_id, actor):
        raise ApiError("not permitted to manage this team", 403, "forbidden")
    user = await session.get(User, user_id)
    if user is None or user.status != "active":
        raise ApiError("user not found", 404, "user_not_found")
    existing = await session.scalar(
        select(CivicTeamMember.id).where(
            CivicTeamMember.team_id == team_id, CivicTeamMember.user_id == user_id
        )
    )
    if existing is not None:
        raise ApiError("user is already a team member", 409, "member_exists")
    member = CivicTeamMember(team_id=team_id, user_id=user_id, role=role)
    session.add(member)
    await session.flush()
    await audit(
        session,
        action="civic_action.team_add_member",
        entity_type="civic_team",
        entity_id=team.id,
        actor_id=actor.id,
        after={"user_id": str(user_id), "role": role},
        request=request,
    )
    await session.commit()
    return {
        "id": str(member.id),
        "team_id": str(team_id),
        "user_id": str(user_id),
        "role": member.role,
    }


async def remove_team_member(
    session: AsyncSession,
    *,
    team_id: uuid.UUID,
    actor: User,
    user_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    team = await session.get(CivicTeam, team_id)
    if team is None:
        raise ApiError("team not found", 404, "team_not_found")
    if not await _can_manage_volunteers(session, team.initiative_id, actor):
        raise ApiError("not permitted to manage this team", 403, "forbidden")
    member = await session.scalar(
        select(CivicTeamMember).where(
            CivicTeamMember.team_id == team_id, CivicTeamMember.user_id == user_id
        )
    )
    if member is None:
        raise ApiError("user is not a team member", 404, "member_not_found")
    if member.role == "coordinator" and member.user_id == actor.id:
        raise ApiError("coordinator cannot remove themselves", 409, "self_removal")
    await audit(
        session,
        action="civic_action.team_remove_member",
        entity_type="civic_team",
        entity_id=team.id,
        actor_id=actor.id,
        after={"user_id": str(user_id)},
        request=request,
    )
    await session.delete(member)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Campaign initiative links + members
# ---------------------------------------------------------------------------


async def link_campaign_initiative(
    session: AsyncSession,
    *,
    actor: User,
    campaign_id: uuid.UUID,
    initiative_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise ApiError("campaign not found", 404, "campaign_not_found")
    membership = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == actor.id
        )
    )
    if (membership is None or membership.role != "organizer") and not _is_moderator(actor):
        raise ApiError("only campaign organizers can link initiatives", 403, "forbidden")
    initiative = await _get_initiative(session, initiative_id)
    if initiative.status not in ("approved", "active"):
        raise ApiError("initiative is not active", 409, "initiative_not_active")
    existing = await session.scalar(
        select(CampaignInitiativeLink).where(
            CampaignInitiativeLink.campaign_id == campaign_id,
            CampaignInitiativeLink.initiative_id == initiative_id,
        )
    )
    if existing is not None:
        raise ApiError("initiative already linked", 409, "link_exists")
    link = CampaignInitiativeLink(
        campaign_id=campaign_id, initiative_id=initiative_id, created_by=actor.id
    )
    session.add(link)
    await session.flush()
    await audit(
        session,
        action="civic_action.campaign_link",
        entity_type="campaign_initiative",
        entity_id=campaign_id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {"ok": True, "campaign_id": str(campaign_id), "initiative_id": str(initiative_id)}


async def join_campaign(
    session: AsyncSession,
    *,
    actor: User,
    campaign_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    campaign = await session.get(Campaign, campaign_id)
    if campaign is None:
        raise ApiError("campaign not found", 404, "campaign_not_found")
    existing = await session.scalar(
        select(CampaignMember).where(
            CampaignMember.campaign_id == campaign_id, CampaignMember.user_id == actor.id
        )
    )
    if existing is not None:
        raise ApiError("already a campaign member", 409, "member_exists")
    member = CampaignMember(campaign_id=campaign_id, user_id=actor.id, role="member")
    session.add(member)
    await session.flush()
    await audit(
        session,
        action="civic_action.campaign_join",
        entity_type="campaign_member",
        entity_id=campaign_id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {"ok": True, "campaign_id": str(campaign_id), "user_id": str(actor.id), "role": "member"}


# ---------------------------------------------------------------------------
# Civic events
# ---------------------------------------------------------------------------


def _parse_dt(value: str | None, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(f"{field} must be an ISO-8601 timestamp", 422, f"invalid_{field}") from exc


def _can_set_event_status(event: CivicEvent, actor: User, new_status: str) -> bool:
    if _is_moderator(actor):
        return True
    if event.organizer_id != actor.id:
        return False
    return new_status != "published"


async def create_event(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _coerce_uuid(data.get("initiative_id"), "initiative_id")
    if initiative_id is not None:
        initiative = await _get_initiative(session, initiative_id)
        if not await _initiative_visibility(session, initiative, actor):
            raise ApiError("initiative not found", 404, "initiative_not_found")
    starts_at = _parse_dt(data.get("starts_at"), "starts_at")
    if starts_at is None:
        raise ApiError("starts_at is required", 422, "missing_starts_at")
    title = str(data.get("title") or "").strip()
    if len(title) < 3:
        raise ApiError("title must be at least 3 characters", 422, "invalid_title")
    event = CivicEvent(
        initiative_id=initiative_id,
        title=title,
        description=data.get("description"),
        location=data.get("location") or {},
        starts_at=starts_at,
        ends_at=_parse_dt(data.get("ends_at"), "ends_at"),
        organizer_id=actor.id,
        capacity=data.get("capacity"),
        requirements=data.get("requirements") or [],
        safety_info=data.get("safety_info"),
        status="draft",
    )
    session.add(event)
    await session.flush()
    await audit(
        session,
        action="civic_action.event_create",
        entity_type="civic_event",
        entity_id=event.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _payload_event(event)


async def update_event(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    event = await session.get(CivicEvent, event_id)
    if event is None:
        raise ApiError("event not found", 404, "event_not_found")
    if event.organizer_id != actor.id and not _is_moderator(actor):
        raise ApiError("not permitted to edit this event", 403, "forbidden")
    for field in (
        "title",
        "description",
        "location",
        "ends_at",
        "capacity",
        "requirements",
        "safety_info",
    ):
        if field in data and data[field] is not None:
            setattr(event, field, data[field])
    parsed_start = _parse_dt(data.get("starts_at"), "starts_at")
    if parsed_start is not None:
        event.starts_at = parsed_start
    new_status = data.get("status")
    if new_status is not None:
        if new_status not in ("draft", "submitted", "published", "cancelled", "completed"):
            raise ApiError("invalid event status", 422, "invalid_status")
        if not _can_set_event_status(event, actor, new_status):
            raise ApiError("not permitted to set this event status", 403, "forbidden")
        event.status = new_status
        if new_status == "published":
            await enqueue_for_users(
                session,
                user_ids=[event.organizer_id],
                event="civic_action.event_published",
                payload={"title": event.title, "event_id": str(event.id)},
                channels=["in_app"],
            )
    await audit(
        session,
        action="civic_action.event_update",
        entity_type="civic_event",
        entity_id=event.id,
        actor_id=actor.id,
        after={"status": event.status},
        request=request,
    )
    await session.commit()
    return _payload_event(event)


async def list_events(
    session: AsyncSession,
    *,
    viewer: User,
    initiative_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    stmt = select(CivicEvent).order_by(CivicEvent.starts_at.desc())
    if initiative_id is not None:
        stmt = stmt.where(CivicEvent.initiative_id == initiative_id)
    if status:
        stmt = stmt.where(CivicEvent.status == status)
    elif not _is_moderator(viewer):
        stmt = stmt.where(CivicEvent.status == "published")
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return {"items": [_payload_event(e) for e in rows]}


async def get_event(session: AsyncSession, event_id: uuid.UUID, viewer: User) -> dict[str, Any]:
    event = await session.get(CivicEvent, event_id)
    if event is None or (
        event.status != "published"
        and event.organizer_id != viewer.id
        and not _is_moderator(viewer)
    ):
        raise ApiError("event not found", 404, "event_not_found")
    participants = (
        (
            await session.execute(
                select(EventParticipant).where(EventParticipant.event_id == event_id)
            )
        )
        .scalars()
        .all()
    )
    return {
        **_payload_event(event),
        "participants": [{"user_id": str(p.user_id), "status": p.status} for p in participants],
    }


async def join_event(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    event = await session.get(CivicEvent, event_id)
    if event is None:
        raise ApiError("event not found", 404, "event_not_found")
    if event.status != "published":
        raise ApiError("event is not published", 409, "event_not_published")
    existing = await session.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id, EventParticipant.user_id == actor.id
        )
    )
    if existing is not None and existing.status == "cancelled":
        existing.status = "joined"
        await session.flush()
        await session.commit()
        return {"ok": True, "status": "joined"}
    if existing is not None:
        raise ApiError("already joined this event", 409, "already_joined")
    if event.capacity:
        joined_count = await session.scalar(
            select(func.count(EventParticipant.id)).where(
                EventParticipant.event_id == event_id,
                EventParticipant.status == "joined",
            )
        )
        if (joined_count or 0) >= event.capacity:
            raise ApiError("event is full", 409, "event_full")
    participant = EventParticipant(event_id=event_id, user_id=actor.id, status="joined")
    session.add(participant)
    await session.flush()
    await audit(
        session,
        action="civic_action.event_join",
        entity_type="civic_event",
        entity_id=event.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {"ok": True, "status": "joined"}


async def cancel_event_participation(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    participant = await session.scalar(
        select(EventParticipant).where(
            EventParticipant.event_id == event_id, EventParticipant.user_id == actor.id
        )
    )
    if participant is None or participant.status == "cancelled":
        raise ApiError("participation not found", 404, "participation_not_found")
    participant.status = "cancelled"
    await audit(
        session,
        action="civic_action.event_cancel_participation",
        entity_type="civic_event",
        entity_id=event_id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {"ok": True}
