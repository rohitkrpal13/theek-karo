"""Phase 18 civic participation service (ADR-053): civic initiatives, volunteer
system, community groups, and deterministic badges.

Civic principles enforced here:
- Initiatives/groups are civic, evidence-based, and non-partisan.
- Volunteer profiles store only explicit user preferences (no phone, address,
  or exact location); the only joinable surface is an opportunity.
- Badges are awarded by deterministic criteria evaluated against the database
  (never AI-only); no competitive leaderboards.
- Platform safety rules always override group rules; public content requires
  review before it becomes visible platform-wide.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.community.models import (
    Badge,
    CivicInitiative,
    CommunityGroup,
    GroupMember,
    InitiativeFollower,
    InitiativeMember,
    InitiativeObservation,
    Reaction,
    UserBadge,
    VolunteerOpportunity,
    VolunteerProfile,
    VolunteerSignup,
)
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.notifications.events import enqueue_for_users
from tk_api.publicdata.models import DataCorrectionRequest
from tk_api.reports.models import Report, ReportComment, ReportEvidence
from tk_api.users.models import User

INITIATIVE_PUBLIC_STATUSES = ("approved", "active", "completed", "archived")
INITIATIVE_VISIBLE_TO_MODERATOR = {"draft", "submitted", "review", "rejected"}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    cleaned = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return (cleaned or "initiative")[:48]


def _is_moderator(user: User) -> bool:
    return any(role in {"super_admin", "admin", "moderator"} for role in user.role_codes())


def _user_public(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "username": user.username,
    }


def _coerce_uuid(value: Any, field: str) -> uuid.UUID | None:
    """Coerce a JSON-body UUID (str) to ``uuid.UUID``; model columns require it."""
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ApiError(f"{field} must be a valid UUID", 422, f"invalid_{field}") from exc


# ---------------------------------------------------------------------------
# Initiatives
# ---------------------------------------------------------------------------


async def create_initiative(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    slug = _slugify(str(data.get("title") or "initiative")) + "-" + uuid.uuid4().hex[:8]
    initiative = CivicInitiative(
        slug=slug,
        title=str(data.get("title") or "").strip(),
        description=str(data.get("description") or "").strip(),
        category_id=_coerce_uuid(data.get("category_id"), "category_id"),
        geography_id=_coerce_uuid(data.get("geography_id"), "geography_id"),
        initiator_id=actor.id,
        status="draft",
        goal=data.get("goal"),
        expected_activities=data.get("expected_activities") or [],
        duration_days=data.get("duration_days"),
        participation_rules=data.get("participation_rules") or {},
        evidence_requirements=data.get("evidence_requirements") or {},
    )
    if not initiative.title or not initiative.description:
        raise ApiError("title and description are required", 422, "invalid_initiative")
    session.add(initiative)
    await session.flush()
    session.add(
        InitiativeMember(
            initiative_id=initiative.id,
            user_id=actor.id,
            role="initiator",
            status="active",
        )
    )
    await audit(
        session,
        action="community.initiative_create",
        entity_type="civic_initiative",
        entity_id=initiative.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=actor)


async def list_initiatives(
    session: AsyncSession,
    *,
    viewer: User | None,
    status: str | None,
    category_id: uuid.UUID | None,
    geography_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    stmt = select(CivicInitiative).order_by(CivicInitiative.created_at.desc())
    if viewer is not None and _is_moderator(viewer):
        if status:
            stmt = stmt.where(CivicInitiative.status == status)
    else:
        # non-staff: public statuses, plus the viewer's own drafts/submitted
        stmt = stmt.where(CivicInitiative.status.in_(INITIATIVE_PUBLIC_STATUSES))
        if viewer is not None:
            stmt = stmt.where(
                (CivicInitiative.initiator_id == viewer.id)
                | (CivicInitiative.status.in_(INITIATIVE_PUBLIC_STATUSES))
            )
    if category_id is not None:
        stmt = stmt.where(CivicInitiative.category_id == category_id)
    if geography_id is not None:
        stmt = stmt.where(CivicInitiative.geography_id == geography_id)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    items = [await _initiative_payload(session, row, viewer=viewer) for row in rows]
    return {"items": items, "count": len(items)}


async def get_initiative(
    session: AsyncSession, initiative_id: uuid.UUID, viewer: User | None
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if not await _can_view_initiative(session, initiative, viewer):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    return await _initiative_payload(session, initiative, viewer=viewer)


async def _can_view_initiative(
    session: AsyncSession, initiative: CivicInitiative, viewer: User | None
) -> bool:
    if initiative.status in INITIATIVE_PUBLIC_STATUSES:
        return True
    if viewer is None:
        return False
    if _is_moderator(viewer):
        return True
    return initiative.initiator_id == viewer.id


async def update_initiative(
    session: AsyncSession,
    *,
    initiative_id: uuid.UUID,
    actor: User,
    changes: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if initiative.status != "draft" or initiative.initiator_id != actor.id:
        raise ApiError(
            "only the initiator can edit an initiative while it is a draft",
            403,
            "initiative_not_editable",
        )
    for field in (
        "title",
        "description",
        "goal",
        "expected_activities",
        "duration_days",
        "participation_rules",
        "evidence_requirements",
    ):
        if field in changes:
            setattr(initiative, field, changes[field])
    if "category_id" in changes:
        initiative.category_id = _coerce_uuid(changes["category_id"], "category_id")
    if "geography_id" in changes:
        initiative.geography_id = _coerce_uuid(changes["geography_id"], "geography_id")
    await audit(
        session,
        action="community.initiative_update",
        entity_type="civic_initiative",
        entity_id=initiative.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=actor)


async def submit_initiative(
    session: AsyncSession, *, initiative_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if initiative.initiator_id != actor.id:
        raise ApiError("only the initiator may submit", 403, "forbidden")
    if initiative.status != "draft":
        raise ApiError("initiative is not a draft", 409, "invalid_status")
    initiative.status = "submitted"
    await audit(
        session,
        action="community.initiative_submit",
        entity_type="civic_initiative",
        entity_id=initiative.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=actor)


async def review_initiative(
    session: AsyncSession,
    *,
    initiative_id: uuid.UUID,
    reviewer: User,
    decision: str,
    note: str | None,
    request: Request,
) -> dict[str, Any]:
    if not _is_moderator(reviewer):
        raise ApiError("moderator permission required", 403, "forbidden")
    if decision not in ("approve", "reject"):
        raise ApiError("decision must be approve or reject", 422, "invalid_decision")
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if initiative.status not in ("submitted", "review"):
        raise ApiError("initiative is not awaiting review", 409, "invalid_status")
    now = datetime.now(UTC)
    initiative.status = "active" if decision == "approve" else "rejected"
    initiative.reviewed_by = reviewer.id
    initiative.reviewed_at = now
    initiative.review_note = note
    if decision == "approve" and initiative.starts_at is None:
        initiative.starts_at = now
    await audit(
        session,
        action="community.initiative_review",
        entity_type="civic_initiative",
        entity_id=initiative.id,
        actor_id=reviewer.id,
        after={"decision": decision, "note": note},
        request=request,
    )
    await enqueue_for_users(
        session,
        user_ids=[initiative.initiator_id],
        event="community.initiative_reviewed",
        payload={
            "initiative_id": str(initiative.id),
            "initiative_title": initiative.title,
            "outcome": "approved" if decision == "approve" else "rejected",
        },
        channels=["in_app"],
    )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=reviewer)


async def join_initiative(
    session: AsyncSession, *, initiative_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if initiative.status not in ("approved", "active"):
        raise ApiError("initiative is not open for participation", 409, "invalid_status")
    existing = await session.scalar(
        select(InitiativeMember).where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.user_id == actor.id,
        )
    )
    if existing is None:
        session.add(
            InitiativeMember(
                initiative_id=initiative.id, user_id=actor.id, role="participant", status="active"
            )
        )
        await audit(
            session,
            action="community.initiative_join",
            entity_type="civic_initiative",
            entity_id=initiative.id,
            actor_id=actor.id,
            request=request,
        )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=actor)


async def leave_initiative(
    session: AsyncSession, *, initiative_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    if initiative.initiator_id == actor.id:
        raise ApiError("the initiator cannot leave their own initiative", 409, "forbidden")
    await session.execute(
        delete(InitiativeMember).where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.user_id == actor.id,
        )
    )
    await audit(
        session,
        action="community.initiative_leave",
        entity_type="civic_initiative",
        entity_id=initiative.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=actor)


async def list_observations(
    session: AsyncSession, *, initiative_id: uuid.UUID, viewer: User | None
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None or not await _can_view_initiative(session, initiative, viewer):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    rows = (
        (
            await session.execute(
                select(InitiativeObservation)
                .where(InitiativeObservation.initiative_id == initiative_id)
                .order_by(InitiativeObservation.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    items = []
    for row in rows:
        author = await session.get(User, row.user_id)
        item: dict[str, Any] = {
            "id": str(row.id),
            "kind": row.kind,
            "notes": row.notes,
            "media_object_id": str(row.media_object_id) if row.media_object_id else None,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "user": _user_public(author)
            if author
            else {"id": str(row.user_id), "display_name": "Anonymous"},
        }
        can_see_reviewer = False
        if viewer is not None:
            can_see_reviewer = _is_moderator(viewer) or initiative.initiator_id == viewer.id
        if can_see_reviewer:
            item["reviewed_by"] = str(row.reviewed_by) if row.reviewed_by else None
        items.append(item)
    return {"items": items, "count": len(items)}


async def add_observation(
    session: AsyncSession,
    *,
    initiative_id: uuid.UUID,
    actor: User,
    kind: str,
    notes: str | None,
    media_object_id: uuid.UUID | None,
    request: Request,
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    member = await session.scalar(
        select(InitiativeMember).where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.user_id == actor.id,
        )
    )
    if member is None and not _is_moderator(actor):
        raise ApiError("join the initiative to contribute observations", 403, "not_a_member")
    if initiative.status not in ("approved", "active"):
        raise ApiError("initiative is not active", 409, "invalid_status")
    observation = InitiativeObservation(
        initiative_id=initiative.id,
        user_id=actor.id,
        kind=kind,
        notes=notes,
        media_object_id=media_object_id,
        status="pending",
    )
    session.add(observation)
    await audit(
        session,
        action="community.initiative_observation",
        entity_type="initiative_observation",
        entity_id=observation.id,
        actor_id=actor.id,
        after={"kind": kind, "initiative_id": str(initiative.id)},
        request=request,
    )
    await session.commit()
    return {
        "id": str(observation.id),
        "kind": observation.kind,
        "notes": observation.notes,
        "status": observation.status,
        "created_at": observation.created_at.isoformat(),
    }


async def review_observation(
    session: AsyncSession,
    *,
    initiative_id: uuid.UUID,
    observation_id: uuid.UUID,
    reviewer: User,
    decision: str,
    request: Request,
) -> dict[str, Any]:
    if decision not in ("accept", "reject"):
        raise ApiError("decision must be accept or reject", 422, "invalid_decision")
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    organizer = await session.scalar(
        select(InitiativeMember).where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.user_id == reviewer.id,
            InitiativeMember.role.in_(["initiator", "organizer"]),
        )
    )
    if organizer is None and not _is_moderator(reviewer):
        raise ApiError("only organizers or moderators may review observations", 403, "forbidden")
    observation = await session.get(InitiativeObservation, observation_id)
    if observation is None or observation.initiative_id != initiative.id:
        raise ApiError("observation not found", 404, "observation_not_found")
    observation.status = "accepted" if decision == "accept" else "rejected"
    observation.reviewed_by = reviewer.id
    observation.reviewed_at = datetime.now(UTC)
    await audit(
        session,
        action="community.initiative_observation_review",
        entity_type="initiative_observation",
        entity_id=observation.id,
        actor_id=reviewer.id,
        after={"decision": decision},
        request=request,
    )
    await session.commit()
    return {"id": str(observation.id), "status": observation.status}


async def complete_initiative(
    session: AsyncSession,
    *,
    initiative_id: uuid.UUID,
    actor: User,
    results: dict[str, Any] | None,
    request: Request,
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    member = await session.scalar(
        select(InitiativeMember).where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.user_id == actor.id,
            InitiativeMember.role.in_(["initiator", "organizer"]),
        )
    )
    if member is None and not _is_moderator(actor):
        raise ApiError("only organizers may complete an initiative", 403, "forbidden")
    if initiative.status != "active":
        raise ApiError("only active initiatives can be completed", 409, "invalid_status")
    initiative.status = "completed"
    initiative.results = results
    initiative.ends_at = datetime.now(UTC)
    await session.execute(
        update(InitiativeMember)
        .where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.status == "active",
        )
        .values(status="completed", completed_at=datetime.now(UTC))
    )
    await audit(
        session,
        action="community.initiative_complete",
        entity_type="civic_initiative",
        entity_id=initiative.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _initiative_payload(session, initiative, viewer=actor)


async def follow_initiative(
    session: AsyncSession, initiative_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    existing = await session.scalar(
        select(InitiativeFollower).where(
            InitiativeFollower.initiative_id == initiative_id,
            InitiativeFollower.user_id == user.id,
        )
    )
    if existing is None:
        session.add(InitiativeFollower(initiative_id=initiative_id, user_id=user.id))
        await session.commit()
    return {"status": "following", "initiative_id": str(initiative_id)}


async def unfollow_initiative(
    session: AsyncSession, initiative_id: uuid.UUID, *, user: User
) -> dict[str, Any]:
    await session.execute(
        delete(InitiativeFollower).where(
            InitiativeFollower.initiative_id == initiative_id,
            InitiativeFollower.user_id == user.id,
        )
    )
    await session.commit()
    return {"status": "not_following", "initiative_id": str(initiative_id)}


async def _initiative_payload(
    session: AsyncSession, initiative: CivicInitiative, viewer: User | None
) -> dict[str, Any]:
    initiator = await session.get(User, initiative.initiator_id)
    participants = await session.scalar(
        select(func.count())
        .select_from(InitiativeMember)
        .where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.status == "active",
        )
    )
    observations = await session.scalar(
        select(func.count())
        .select_from(InitiativeObservation)
        .where(InitiativeObservation.initiative_id == initiative.id)
    )
    accepted_evidence = await session.scalar(
        select(func.count())
        .select_from(InitiativeObservation)
        .where(
            InitiativeObservation.initiative_id == initiative.id,
            InitiativeObservation.status == "accepted",
        )
    )
    is_member = False
    is_organizer = False
    if viewer is not None:
        membership = await session.scalar(
            select(InitiativeMember).where(
                InitiativeMember.initiative_id == initiative.id,
                InitiativeMember.user_id == viewer.id,
            )
        )
        is_member = membership is not None
        is_organizer = membership is not None and membership.role in ("initiator", "organizer")
    following = False
    if viewer is not None:
        following = (
            await session.scalar(
                select(InitiativeFollower).where(
                    InitiativeFollower.initiative_id == initiative.id,
                    InitiativeFollower.user_id == viewer.id,
                )
            )
        ) is not None
    return {
        "id": str(initiative.id),
        "slug": initiative.slug,
        "title": initiative.title,
        "description": initiative.description,
        "category_id": str(initiative.category_id) if initiative.category_id else None,
        "geography_id": str(initiative.geography_id) if initiative.geography_id else None,
        "status": initiative.status,
        "goal": initiative.goal,
        "expected_activities": initiative.expected_activities or [],
        "duration_days": initiative.duration_days,
        "participation_rules": initiative.participation_rules or {},
        "evidence_requirements": initiative.evidence_requirements or {},
        "results": initiative.results,
        "participant_count": int(participants or 0),
        "observation_count": int(observations or 0),
        "accepted_evidence_count": int(accepted_evidence or 0),
        "initiator": _user_public(initiator) if initiator else None,
        "starts_at": initiative.starts_at.isoformat() if initiative.starts_at else None,
        "ends_at": initiative.ends_at.isoformat() if initiative.ends_at else None,
        "created_at": initiative.created_at.isoformat(),
        "updated_at": initiative.updated_at.isoformat(),
        "is_member": is_member,
        "is_organizer": is_organizer,
        "is_following": following,
    }


# ---------------------------------------------------------------------------
# Volunteers
# ---------------------------------------------------------------------------


async def get_volunteer_profile(session: AsyncSession, user: User) -> dict[str, Any]:
    profile = await session.get(VolunteerProfile, user.id)
    if profile is None:
        return {
            "user_id": str(user.id),
            "languages": [],
            "interests": [],
            "categories": [],
            "areas": [],
            "skills": [],
            "availability": {},
        }
    return {
        "user_id": str(user.id),
        "languages": profile.languages or [],
        "interests": profile.interests or [],
        "categories": profile.categories or [],
        "areas": profile.areas or [],
        "skills": profile.skills or [],
        "availability": profile.availability or {},
        "updated_at": profile.updated_at.isoformat(),
    }


def _clean_str_list(values: Any, field: str, max_items: int = 20) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ApiError(f"{field} must be a list of strings", 422, "invalid_payload")
    cleaned = [str(v).strip()[:80] for v in values if str(v).strip()]
    if len(cleaned) > max_items:
        raise ApiError(f"{field} can have at most {max_items} entries", 422, "invalid_payload")
    return cleaned


async def update_volunteer_profile(
    session: AsyncSession, *, user: User, changes: dict[str, Any], request: Request
) -> dict[str, Any]:
    profile = await session.get(VolunteerProfile, user.id)
    if profile is None:
        profile = VolunteerProfile(user_id=user.id)
        session.add(profile)
    for field in ("languages", "interests", "categories", "areas", "skills"):
        if field in changes:
            setattr(profile, field, _clean_str_list(changes[field], field))
    if "availability" in changes:
        if not isinstance(changes["availability"], dict):
            raise ApiError("availability must be an object", 422, "invalid_payload")
        profile.availability = changes["availability"]
    await audit(
        session,
        action="community.volunteer_profile_update",
        entity_type="volunteer_profile",
        entity_id=user.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return await get_volunteer_profile(session, user)


async def list_opportunities(
    session: AsyncSession,
    *,
    viewer: User | None,
    status: str | None,
    geography_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    stmt = select(VolunteerOpportunity).order_by(VolunteerOpportunity.created_at.desc())
    if status:
        stmt = stmt.where(VolunteerOpportunity.status == status)
    if geography_id is not None:
        stmt = stmt.where(VolunteerOpportunity.geography_id == geography_id)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    items = [await _opportunity_payload(session, row, viewer=viewer) for row in rows]
    return {"items": items, "count": len(items)}


async def create_opportunity(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _coerce_uuid(data.get("initiative_id"), "initiative_id")
    if initiative_id is not None:
        initiative = await session.get(CivicInitiative, initiative_id)
        if initiative is None:
            raise ApiError("initiative not found", 404, "initiative_not_found")
        member = await session.scalar(
            select(InitiativeMember).where(
                InitiativeMember.initiative_id == initiative.id,
                InitiativeMember.user_id == actor.id,
                InitiativeMember.role.in_(["initiator", "organizer"]),
            )
        )
        if member is None and not _is_moderator(actor):
            raise ApiError(
                "only initiative organizers may create linked opportunities", 403, "forbidden"
            )
    opportunity = VolunteerOpportunity(
        initiative_id=initiative_id,
        title=str(data.get("title") or "").strip(),
        description=str(data.get("description") or "").strip(),
        location_label=data.get("location_label"),
        geography_id=_coerce_uuid(data.get("geography_id"), "geography_id"),
        skills=_clean_str_list(data.get("skills"), "skills"),
        participants_needed=max(1, int(data.get("participants_needed") or 1)),
        status="open",
        created_by=actor.id,
    )
    if not opportunity.title or not opportunity.description:
        raise ApiError("title and description are required", 422, "invalid_opportunity")
    session.add(opportunity)
    await audit(
        session,
        action="community.volunteer_opportunity_create",
        entity_type="volunteer_opportunity",
        entity_id=opportunity.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _opportunity_payload(session, opportunity, viewer=actor)


async def get_opportunity(
    session: AsyncSession, opportunity_id: uuid.UUID, viewer: User | None
) -> dict[str, Any]:
    opportunity = await session.get(VolunteerOpportunity, opportunity_id)
    if opportunity is None:
        raise ApiError("opportunity not found", 404, "opportunity_not_found")
    return await _opportunity_payload(session, opportunity, viewer=viewer)


async def join_opportunity(
    session: AsyncSession, *, opportunity_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    opportunity = await session.get(VolunteerOpportunity, opportunity_id)
    if opportunity is None:
        raise ApiError("opportunity not found", 404, "opportunity_not_found")
    if opportunity.status != "open":
        raise ApiError("opportunity is not open", 409, "invalid_status")
    existing = await session.scalar(
        select(VolunteerSignup).where(
            VolunteerSignup.opportunity_id == opportunity.id,
            VolunteerSignup.user_id == actor.id,
        )
    )
    if existing is None:
        joined = (
            await session.scalar(
                select(func.count())
                .select_from(VolunteerSignup)
                .where(
                    VolunteerSignup.opportunity_id == opportunity.id,
                    VolunteerSignup.status == "joined",
                )
            )
            or 0
        )
        if int(joined) >= opportunity.participants_needed:
            raise ApiError("opportunity is full", 409, "opportunity_full")
        session.add(VolunteerSignup(opportunity_id=opportunity.id, user_id=actor.id))
        await audit(
            session,
            action="community.volunteer_join",
            entity_type="volunteer_opportunity",
            entity_id=opportunity.id,
            actor_id=actor.id,
            request=request,
        )
    await session.commit()
    return await _opportunity_payload(session, opportunity, viewer=actor)


async def withdraw_opportunity(
    session: AsyncSession, *, opportunity_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    opportunity = await session.get(VolunteerOpportunity, opportunity_id)
    if opportunity is None:
        raise ApiError("opportunity not found", 404, "opportunity_not_found")
    signup = await session.scalar(
        select(VolunteerSignup).where(
            VolunteerSignup.opportunity_id == opportunity.id,
            VolunteerSignup.user_id == actor.id,
        )
    )
    if signup is not None and signup.status == "joined":
        signup.status = "withdrawn"
        signup.withdrawn_at = datetime.now(UTC)
        await audit(
            session,
            action="community.volunteer_withdraw",
            entity_type="volunteer_opportunity",
            entity_id=opportunity.id,
            actor_id=actor.id,
            request=request,
        )
    await session.commit()
    return await _opportunity_payload(session, opportunity, viewer=actor)


async def _opportunity_payload(
    session: AsyncSession, opportunity: VolunteerOpportunity, viewer: User | None
) -> dict[str, Any]:
    joined = (
        await session.scalar(
            select(func.count())
            .select_from(VolunteerSignup)
            .where(
                VolunteerSignup.opportunity_id == opportunity.id,
                VolunteerSignup.status == "joined",
            )
        )
        or 0
    )
    creator = await session.get(User, opportunity.created_by)
    my_status = None
    if viewer is not None:
        signup = await session.scalar(
            select(VolunteerSignup).where(
                VolunteerSignup.opportunity_id == opportunity.id,
                VolunteerSignup.user_id == viewer.id,
            )
        )
        my_status = signup.status if signup else None
    return {
        "id": str(opportunity.id),
        "initiative_id": str(opportunity.initiative_id) if opportunity.initiative_id else None,
        "title": opportunity.title,
        "description": opportunity.description,
        "location_label": opportunity.location_label,
        "geography_id": str(opportunity.geography_id) if opportunity.geography_id else None,
        "skills": opportunity.skills or [],
        "participants_needed": opportunity.participants_needed,
        "participants_count": int(joined),
        "status": opportunity.status,
        "created_by": _user_public(creator) if creator else None,
        "created_at": opportunity.created_at.isoformat(),
        "my_status": my_status,
    }


# ---------------------------------------------------------------------------
# Community groups
# ---------------------------------------------------------------------------


async def create_group(
    session: AsyncSession, *, actor: User, data: dict[str, Any], request: Request
) -> dict[str, Any]:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ApiError("group name is required", 422, "invalid_group")
    slug = _slugify(name) + "-" + uuid.uuid4().hex[:8]
    group = CommunityGroup(
        name=name,
        slug=slug,
        description=data.get("description"),
        category_id=_coerce_uuid(data.get("category_id"), "category_id"),
        geography_id=_coerce_uuid(data.get("geography_id"), "geography_id"),
        rules=data.get("rules") or {},
        status="requested",
        owner_id=actor.id,
    )
    session.add(group)
    await session.flush()
    session.add(GroupMember(group_id=group.id, user_id=actor.id, role="owner", status="active"))
    await audit(
        session,
        action="community.group_create",
        entity_type="community_group",
        entity_id=group.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _group_payload(session, group, viewer=actor)


async def list_groups(
    session: AsyncSession,
    *,
    viewer: User | None,
    status: str | None,
    geography_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    stmt = select(CommunityGroup).order_by(CommunityGroup.created_at.desc())
    if viewer is not None and _is_moderator(viewer):
        if status:
            stmt = stmt.where(CommunityGroup.status == status)
    else:
        stmt = stmt.where(CommunityGroup.status.in_(("approved", "active")))
        if viewer is not None:
            stmt = stmt.where(
                (CommunityGroup.owner_id == viewer.id)
                | (CommunityGroup.status.in_(("approved", "active")))
            )
    if geography_id is not None:
        stmt = stmt.where(CommunityGroup.geography_id == geography_id)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    items = [await _group_payload(session, row, viewer=viewer) for row in rows]
    return {"items": items, "count": len(items)}


async def get_group(
    session: AsyncSession, group_id: uuid.UUID, viewer: User | None
) -> dict[str, Any]:
    group = await session.get(CommunityGroup, group_id)
    if group is None:
        raise ApiError("group not found", 404, "group_not_found")
    if group.status not in ("approved", "active") and not (
        viewer is not None and (viewer.id == group.owner_id or _is_moderator(viewer))
    ):
        raise ApiError("group not found", 404, "group_not_found")
    return await _group_payload(session, group, viewer=viewer)


async def update_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    actor: User,
    changes: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    group = await session.get(CommunityGroup, group_id)
    if group is None:
        raise ApiError("group not found", 404, "group_not_found")
    membership = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == actor.id,
            GroupMember.role.in_(["owner", "moderator"]),
        )
    )
    if membership is None and not _is_moderator(actor):
        raise ApiError("only the owner or moderators may edit the group", 403, "forbidden")
    for field in ("name", "description", "rules"):
        if field in changes:
            setattr(group, field, changes[field])
    if "category_id" in changes:
        group.category_id = _coerce_uuid(changes["category_id"], "category_id")
    if "geography_id" in changes:
        group.geography_id = _coerce_uuid(changes["geography_id"], "geography_id")
    await audit(
        session,
        action="community.group_update",
        entity_type="community_group",
        entity_id=group.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _group_payload(session, group, viewer=actor)


async def review_group(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    reviewer: User,
    decision: str,
    note: str | None,
    request: Request,
) -> dict[str, Any]:
    if not _is_moderator(reviewer):
        raise ApiError("moderator permission required", 403, "forbidden")
    if decision not in ("approve", "reject"):
        raise ApiError("decision must be approve or reject", 422, "invalid_decision")
    group = await session.get(CommunityGroup, group_id)
    if group is None:
        raise ApiError("group not found", 404, "group_not_found")
    if group.status != "requested":
        raise ApiError("group is not awaiting review", 409, "invalid_status")
    group.status = "active" if decision == "approve" else "archived"
    group.reviewed_by = reviewer.id
    group.reviewed_at = datetime.now(UTC)
    await audit(
        session,
        action="community.group_review",
        entity_type="community_group",
        entity_id=group.id,
        actor_id=reviewer.id,
        after={"decision": decision, "note": note},
        request=request,
    )
    await enqueue_for_users(
        session,
        user_ids=[group.owner_id],
        event="community.group_reviewed",
        payload={
            "group_id": str(group.id),
            "group_name": group.name,
            "outcome": "approved" if decision == "approve" else "rejected",
        },
        channels=["in_app"],
    )
    await session.commit()
    return await _group_payload(session, group, viewer=reviewer)


async def join_group(
    session: AsyncSession, *, group_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    group = await session.get(CommunityGroup, group_id)
    if group is None:
        raise ApiError("group not found", 404, "group_not_found")
    if group.status not in ("approved", "active"):
        raise ApiError("group is not open for membership", 409, "invalid_status")
    existing = await session.scalar(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == actor.id)
    )
    if existing is None:
        session.add(GroupMember(group_id=group.id, user_id=actor.id))
        await audit(
            session,
            action="community.group_join",
            entity_type="community_group",
            entity_id=group.id,
            actor_id=actor.id,
            request=request,
        )
    await session.commit()
    return await _group_payload(session, group, viewer=actor)


async def leave_group(
    session: AsyncSession, *, group_id: uuid.UUID, actor: User, request: Request
) -> dict[str, Any]:
    group = await session.get(CommunityGroup, group_id)
    if group is None:
        raise ApiError("group not found", 404, "group_not_found")
    membership = await session.scalar(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == actor.id)
    )
    if membership is not None and membership.role == "owner":
        raise ApiError("the owner cannot leave without transferring ownership", 409, "forbidden")
    if membership is not None:
        await session.execute(
            delete(GroupMember).where(
                GroupMember.group_id == group.id, GroupMember.user_id == actor.id
            )
        )
        await audit(
            session,
            action="community.group_leave",
            entity_type="community_group",
            entity_id=group.id,
            actor_id=actor.id,
            request=request,
        )
    await session.commit()
    return await _group_payload(session, group, viewer=actor)


async def manage_group_member(
    session: AsyncSession,
    *,
    group_id: uuid.UUID,
    target_user_id: uuid.UUID,
    actor: User,
    action: str,
    request: Request,
) -> dict[str, Any]:
    """action ∈ {add, remove, ban, promote, demote}."""
    group = await session.get(CommunityGroup, group_id)
    if group is None:
        raise ApiError("group not found", 404, "group_not_found")
    membership = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id,
            GroupMember.user_id == actor.id,
            GroupMember.role.in_(["owner", "moderator"]),
        )
    )
    if membership is None and not _is_moderator(actor):
        raise ApiError("only owners or moderators manage members", 403, "forbidden")
    target = await session.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group.id, GroupMember.user_id == target_user_id
        )
    )
    if action == "add":
        if target is None:
            session.add(GroupMember(group_id=group.id, user_id=target_user_id))
        elif target.status == "banned":
            raise ApiError("member is banned", 409, "member_banned")
        else:
            raise ApiError("already a member", 409, "already_member")
    elif action == "remove":
        if target is None:
            raise ApiError("not a member", 404, "not_a_member")
        if target.role == "owner":
            raise ApiError("cannot remove the owner", 409, "forbidden")
        await session.execute(
            delete(GroupMember).where(
                GroupMember.group_id == group.id, GroupMember.user_id == target_user_id
            )
        )
    elif action == "ban":
        if target is None or target.role == "owner":
            raise ApiError("cannot ban this member", 409, "forbidden")
        target.status = "banned"
    elif action in ("promote", "demote"):
        if target is None or target.role == "owner":
            raise ApiError("cannot change this member's role", 409, "forbidden")
        target.role = "moderator" if action == "promote" else "member"
    else:
        raise ApiError("unknown member action", 422, "invalid_action")
    await audit(
        session,
        action="community.group_member_manage",
        entity_type="community_group",
        entity_id=group.id,
        actor_id=actor.id,
        after={"target_user_id": str(target_user_id), "action": action},
        request=request,
    )
    await session.commit()
    return await _group_payload(session, group, viewer=actor)


async def _group_payload(
    session: AsyncSession, group: CommunityGroup, viewer: User | None
) -> dict[str, Any]:
    owner = await session.get(User, group.owner_id)
    members = await session.scalar(
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.group_id == group.id, GroupMember.status == "active")
    )
    my_role = None
    if viewer is not None:
        membership = await session.scalar(
            select(GroupMember).where(
                GroupMember.group_id == group.id, GroupMember.user_id == viewer.id
            )
        )
        my_role = membership.role if membership else None
    return {
        "id": str(group.id),
        "name": group.name,
        "slug": group.slug,
        "description": group.description,
        "category_id": str(group.category_id) if group.category_id else None,
        "geography_id": str(group.geography_id) if group.geography_id else None,
        "rules": group.rules or {},
        "status": group.status,
        "owner": _user_public(owner) if owner else None,
        "member_count": int(members or 0),
        "my_role": my_role,
        "created_at": group.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Badges (deterministic criteria)
# ---------------------------------------------------------------------------


async def _badge_metrics(session: AsyncSession, user: User) -> dict[str, int]:
    """Deterministic contribution signals. Every metric must be computable from
    auditable tables — never an AI judgement."""
    uid = user.id
    verified_contributions = (
        await session.scalar(
            select(func.count())
            .select_from(Report)
            .where(
                Report.reporter_id == uid,
                Report.status.in_(
                    ("verified", "assigned", "resolved", "closed", "resolution_verified")
                ),
            )
        )
        or 0
    )
    accepted_evidence = (
        await session.scalar(
            select(func.count())
            .select_from(ReportEvidence)
            .where(ReportEvidence.uploaded_by == uid)
        )
        or 0
    )
    accepted_corrections = (
        await session.scalar(
            select(func.count())
            .select_from(DataCorrectionRequest)
            .where(
                DataCorrectionRequest.user_id == uid,
                DataCorrectionRequest.status == "approved",
            )
        )
        or 0
    )
    comments_written = (
        await session.scalar(
            select(func.count()).select_from(ReportComment).where(ReportComment.author_id == uid)
        )
        or 0
    )
    volunteer_completions = (
        await session.scalar(
            select(func.count())
            .select_from(VolunteerSignup)
            .where(VolunteerSignup.user_id == uid, VolunteerSignup.status == "completed")
        )
        or 0
    )
    initiatives_completed_organized = (
        await session.scalar(
            select(func.count())
            .select_from(InitiativeMember)
            .join(CivicInitiative, CivicInitiative.id == InitiativeMember.initiative_id)
            .where(
                InitiativeMember.user_id == uid,
                InitiativeMember.role.in_(["initiator", "organizer"]),
                CivicInitiative.status == "completed",
            )
        )
        or 0
    )
    helpful_reactions = (
        await session.scalar(
            select(func.count())
            .select_from(ReportComment)
            .join(Reaction, Reaction.comment_id == ReportComment.id)
            .where(
                ReportComment.author_id == uid,
                Reaction.kind == "helpful",
            )
        )
        or 0
    )
    return {
        "verified_contributions": int(verified_contributions),
        "accepted_evidence": int(accepted_evidence),
        "accepted_corrections": int(accepted_corrections),
        "comments_written": int(comments_written),
        "volunteer_completions": int(volunteer_completions),
        "initiatives_completed_organized": int(initiatives_completed_organized),
        "helpful_reactions": int(helpful_reactions),
    }


async def my_badges(session: AsyncSession, user: User) -> dict[str, Any]:
    """Recompute badge eligibility from deterministic metrics and persist awards."""
    metrics = await _badge_metrics(session, user)
    badges = (await session.execute(select(Badge).order_by(Badge.code))).scalars().all()
    earned: list[dict[str, Any]] = []
    progress: list[dict[str, Any]] = []
    for badge in badges:
        criterion = badge.criteria or {}
        metric = criterion.get("metric")
        minimum = int(criterion.get("min") or 0)
        current = metrics.get(str(metric), 0)
        achieved = current >= minimum
        awarded = await session.scalar(
            select(UserBadge).where(UserBadge.user_id == user.id, UserBadge.badge_id == badge.id)
        )
        if achieved and awarded is None:
            session.add(UserBadge(user_id=user.id, badge_id=badge.id))
        entry = {
            "code": badge.code,
            "name": badge.name,
            "name_hi": badge.name_hi,
            "description": badge.description,
            "criteria": criterion,
            "current": current,
            "earned": achieved or awarded is not None,
        }
        (earned if achieved or awarded is not None else progress).append(entry)
    await session.commit()
    return {"metrics": metrics, "earned": earned, "in_progress": progress}


async def list_badges(session: AsyncSession) -> dict[str, Any]:
    badges = (await session.execute(select(Badge).order_by(Badge.code))).scalars().all()
    return {
        "items": [
            {
                "code": b.code,
                "name": b.name,
                "name_hi": b.name_hi,
                "description": b.description,
                "criteria": b.criteria,
            }
            for b in badges
        ]
    }
