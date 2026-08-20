"""Phase 21 civic action orchestration services: action plans, tasks,
milestones, dependencies, comments, and progress-driven updates.

Design rules enforced here (see docs/CIVIC-ACTION.md):

* Progress is computed from task/milestone state — never entered manually.
* AI suggestions are stored separately and only materialize after a human
  approval (``ai_generated`` + ``ai_approved_by``).
* No autonomous high-impact action: statuses that affect the public record
  (VERIFICATION_PENDING, VERIFIED) require explicit human steps and evidence.
* Plan/task visibility mirrors initiative visibility (public initiatives ->
  public plans/tasks); private drafts stay visible only to participants.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.civic_action.models import (
    ActionDependency,
    ActionMilestone,
    ActionPlan,
    ActionTask,
    ActionUpdate,
    TaskComment,
)
from tk_api.community.models import CivicInitiative, InitiativeMember
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.notifications.events import enqueue_for_users
from tk_api.users.models import User

PLAN_PUBLIC_STATUSES = (
    "OPEN",
    "ACTIVE",
    "BLOCKED",
    "COMPLETED",
    "VERIFICATION_PENDING",
    "VERIFIED",
)
TASK_ACTIVE_STATUSES = ("TODO", "ASSIGNED", "IN_PROGRESS", "BLOCKED")


def _is_moderator(user: User) -> bool:
    return any(role in {"super_admin", "admin", "moderator"} for role in user.role_codes())


def _coerce_uuid(value: Any, field: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise ApiError(f"{field} must be a valid UUID", 422, f"invalid_{field}") from exc


def _require_uuid(value: Any, field: str) -> uuid.UUID:
    parsed = _coerce_uuid(value, field)
    if parsed is None:
        raise ApiError(f"{field} is required", 422, f"missing_{field}")
    return parsed


def _user_public(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "username": user.username,
    }


async def _get_initiative(session: AsyncSession, initiative_id: uuid.UUID) -> CivicInitiative:
    initiative = await session.get(CivicInitiative, initiative_id)
    if initiative is None:
        raise ApiError("initiative not found", 404, "initiative_not_found")
    return initiative


async def _get_plan(session: AsyncSession, plan_id: uuid.UUID) -> ActionPlan:
    plan = await session.get(ActionPlan, plan_id)
    if plan is None:
        raise ApiError("action plan not found", 404, "action_plan_not_found")
    return plan


async def _get_task(session: AsyncSession, task_id: uuid.UUID) -> ActionTask:
    task = await session.get(ActionTask, task_id)
    if task is None:
        raise ApiError("task not found", 404, "task_not_found")
    return task


async def _initiative_visibility(
    session: AsyncSession, initiative: CivicInitiative, viewer: User
) -> bool:
    """The viewer can see the initiative (public status or participant)."""
    from tk_api.community.participation import INITIATIVE_PUBLIC_STATUSES

    if initiative.status in INITIATIVE_PUBLIC_STATUSES:
        return True
    if _is_moderator(viewer):
        return True
    if initiative.initiator_id == viewer.id:
        return True
    member = await session.scalar(
        select(InitiativeMember.id).where(
            InitiativeMember.initiative_id == initiative.id,
            InitiativeMember.user_id == viewer.id,
        )
    )
    return member is not None


async def _can_edit_plan(session: AsyncSession, plan: ActionPlan, actor: User) -> bool:
    """Plan owner, initiative initiator, or moderator."""
    if _is_moderator(actor) or plan.owner_id == actor.id or plan.created_by == actor.id:
        return True
    initiative = await _get_initiative(session, plan.initiative_id)
    return initiative.initiator_id == actor.id


async def _plan_payload(session: AsyncSession, plan: ActionPlan) -> dict[str, Any]:
    task_rows = (
        (await session.execute(select(ActionTask).where(ActionTask.plan_id == plan.id)))
        .scalars()
        .all()
    )
    milestone_rows = (
        (
            await session.execute(
                select(ActionMilestone)
                .where(ActionMilestone.plan_id == plan.id)
                .order_by(ActionMilestone.order_idx)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": str(plan.id),
        "initiative_id": str(plan.initiative_id),
        "objective": plan.objective,
        "owner_id": str(plan.owner_id),
        "status": plan.status,
        "risk_notes": plan.risk_notes,
        "ai_generated": plan.ai_generated,
        "ai_suggestion": plan.ai_suggestion,
        "ai_approved_by": str(plan.ai_approved_by) if plan.ai_approved_by else None,
        "ai_approved_at": plan.ai_approved_at.isoformat() if plan.ai_approved_at else None,
        "created_by": str(plan.created_by),
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "progress": _progress_from_tasks(task_rows, milestone_rows),
        "tasks": [_task_payload(t) for t in task_rows],
        "milestones": [_milestone_payload(m) for m in milestone_rows],
    }


def _progress_from_tasks(
    tasks: Sequence[ActionTask], milestones: Sequence[ActionMilestone]
) -> dict[str, Any]:
    """Deterministic progress derived purely from entity state (never entered
    manually). Task weight = 70%, milestone weight = 30%."""
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "COMPLETED")
    milestone_total = len(milestones)
    milestone_done = sum(1 for m in milestones if m.status == "completed")
    task_pct = (done / total) if total else 0.0
    milestone_pct = (milestone_done / milestone_total) if milestone_total else 0.0
    if total and milestone_total:
        overall = round(task_pct * 0.7 + milestone_pct * 0.3, 4)
    elif total:
        overall = round(task_pct, 4)
    elif milestone_total:
        overall = round(milestone_pct, 4)
    else:
        overall = 0.0
    return {
        "tasks_total": total,
        "tasks_done": done,
        "milestones_total": milestone_total,
        "milestones_done": milestone_done,
        "overall": overall,
    }


def _task_payload(task: ActionTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "plan_id": str(task.plan_id),
        "title": task.title,
        "description": task.description,
        "created_by": str(task.created_by),
        "owner_id": str(task.owner_id),
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "priority": task.priority,
        "status": task.status,
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "location": task.location,
        "institution_id": str(task.institution_id) if task.institution_id else None,
        "checklist": task.checklist,
        "blocked_reason": task.blocked_reason,
        "blocked_at": task.blocked_at.isoformat() if task.blocked_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _milestone_payload(milestone: ActionMilestone) -> dict[str, Any]:
    return {
        "id": str(milestone.id),
        "plan_id": str(milestone.plan_id),
        "title": milestone.title,
        "description": milestone.description,
        "order_idx": milestone.order_idx,
        "status": milestone.status,
        "due_at": milestone.due_at.isoformat() if milestone.due_at else None,
        "completed_at": milestone.completed_at.isoformat() if milestone.completed_at else None,
    }


def _parse_dt(value: str | None, field: str) -> datetime | None:
    if value is None or value == "":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(f"{field} must be an ISO-8601 timestamp", 422, f"invalid_{field}") from exc


# ---------------------------------------------------------------------------
# Action plans
# ---------------------------------------------------------------------------


async def create_plan(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _require_uuid(data.get("initiative_id"), "initiative_id")
    initiative = await _get_initiative(session, initiative_id)
    if initiative.status not in ("approved", "active"):
        raise ApiError(
            "an action plan requires an approved initiative", 409, "initiative_not_approved"
        )
    objective = str(data.get("objective") or "").strip()
    if len(objective) < 10:
        raise ApiError("objective must be at least 10 characters", 422, "invalid_objective")
    existing = await session.scalar(
        select(ActionPlan.id).where(ActionPlan.initiative_id == initiative_id)
    )
    if existing is not None:
        raise ApiError("an action plan already exists for this initiative", 409, "plan_exists")
    owner_id = _coerce_uuid(data.get("owner_id"), "owner_id") or initiative.initiator_id
    plan = ActionPlan(
        initiative_id=initiative_id,
        objective=objective,
        owner_id=owner_id,
        status="PROPOSED",
        risk_notes=data.get("risk_notes") or [],
        ai_generated=False,
        created_by=actor.id,
    )
    session.add(plan)
    await session.flush()
    await audit(
        session,
        action="civic_action.plan_create",
        entity_type="action_plan",
        entity_id=plan.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _plan_payload(session, plan)


async def get_plan(session: AsyncSession, plan_id: uuid.UUID, viewer: User) -> dict[str, Any]:
    plan = await _get_plan(session, plan_id)
    initiative = await _get_initiative(session, plan.initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("action plan not found", 404, "action_plan_not_found")
    return await _plan_payload(session, plan)


async def list_plans(
    session: AsyncSession,
    *,
    viewer: User,
    initiative_id: uuid.UUID | None,
    status: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    stmt = select(ActionPlan).order_by(ActionPlan.created_at.desc())
    if initiative_id is not None:
        initiative = await _get_initiative(session, initiative_id)
        if not await _initiative_visibility(session, initiative, viewer):
            raise ApiError("action plan not found", 404, "action_plan_not_found")
        stmt = stmt.where(ActionPlan.initiative_id == initiative_id)
    if status:
        stmt = stmt.where(ActionPlan.status == status)
    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    items = []
    for plan in rows:
        initiative = await _get_initiative(session, plan.initiative_id)
        if await _initiative_visibility(session, initiative, viewer):
            items.append(await _plan_payload(session, plan))
    return {"items": items, "count": len(items)}


async def update_plan(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    plan = await _get_plan(session, plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this plan", 403, "forbidden")
    before = {"status": plan.status, "objective": plan.objective}
    if data.get("objective") is not None:
        objective = str(data["objective"]).strip()
        if len(objective) < 10:
            raise ApiError("objective must be at least 10 characters", 422, "invalid_objective")
        plan.objective = objective
    if data.get("risk_notes") is not None:
        plan.risk_notes = data["risk_notes"]
    new_status = data.get("status")
    if new_status is not None:
        if new_status not in {
            "PROPOSED",
            "OPEN",
            "ACTIVE",
            "BLOCKED",
            "COMPLETED",
            "VERIFICATION_PENDING",
            "VERIFIED",
            "CANCELLED",
        }:
            raise ApiError("invalid plan status", 422, "invalid_status")
        if new_status == "VERIFICATION_PENDING":
            tasks = (
                (await session.execute(select(ActionTask).where(ActionTask.plan_id == plan.id)))
                .scalars()
                .all()
            )
            if tasks and any(t.status != "COMPLETED" for t in tasks):
                raise ApiError(
                    "all tasks must be completed before verification", 409, "tasks_incomplete"
                )
        plan.status = new_status
    await audit(
        session,
        action="civic_action.plan_update",
        entity_type="action_plan",
        entity_id=plan.id,
        actor_id=actor.id,
        before=before,
        after={"status": plan.status, "objective": plan.objective},
        request=request,
    )
    await session.commit()
    return await _plan_payload(session, plan)


async def complete_plan_verification(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    actor: User,
    decision: str,
    request: Request,
) -> dict[str, Any]:
    """Human verification of an outcome: VERIFICATION_PENDING -> VERIFIED
    (approved) or -> ACTIVE (rejected, back to work)."""
    plan = await _get_plan(session, plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to verify this plan", 403, "forbidden")
    if plan.status != "VERIFICATION_PENDING":
        raise ApiError("plan is not awaiting verification", 409, "not_verification_pending")
    if decision == "approved":
        plan.status = "VERIFIED"
    elif decision == "rejected":
        plan.status = "ACTIVE"
    else:
        raise ApiError("decision must be approved or rejected", 422, "invalid_decision")
    await audit(
        session,
        action="civic_action.plan_verify",
        entity_type="action_plan",
        entity_id=plan.id,
        actor_id=actor.id,
        after={"status": plan.status, "decision": decision},
        request=request,
    )
    await session.commit()
    return await _plan_payload(session, plan)


async def store_ai_plan_suggestion(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    actor: User,
    suggestion: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    """Store an AI-produced draft suggestion (labeled AI GENERATED). The
    suggestion is never applied; a human must approve it to create tasks."""
    plan = await _get_plan(session, plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this plan", 403, "forbidden")
    plan.ai_suggestion = suggestion
    plan.ai_generated = False
    await audit(
        session,
        action="civic_action.plan_ai_suggestion",
        entity_type="action_plan",
        entity_id=plan.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return await _plan_payload(session, plan)


async def decide_ai_plan_suggestion(
    session: AsyncSession,
    *,
    plan_id: uuid.UUID,
    actor: User,
    decision: str,
    request: Request,
) -> dict[str, Any]:
    """Human approval gate: only an approved AI suggestion becomes tasks."""
    plan = await _get_plan(session, plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this plan", 403, "forbidden")
    if plan.ai_suggestion is None:
        raise ApiError("no AI suggestion to decide", 409, "no_ai_suggestion")
    if decision == "approve":
        plan.ai_generated = True
        plan.ai_approved_by = actor.id
        plan.ai_approved_at = datetime.now(UTC)
        if plan.status == "PROPOSED":
            plan.status = "OPEN"
    elif decision == "reject":
        plan.ai_suggestion = None
        plan.ai_generated = False
    else:
        raise ApiError("decision must be approve or reject", 422, "invalid_decision")
    await audit(
        session,
        action="civic_action.plan_ai_decision",
        entity_type="action_plan",
        entity_id=plan.id,
        actor_id=actor.id,
        after={"decision": decision},
        request=request,
    )
    await session.commit()
    return await _plan_payload(session, plan)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def create_task(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    plan_id = _require_uuid(data.get("plan_id"), "plan_id")
    plan = await _get_plan(session, plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to create tasks in this plan", 403, "forbidden")
    if plan.status not in ("PROPOSED", "OPEN", "ACTIVE", "BLOCKED"):
        raise ApiError("plan is not editable in its current status", 409, "plan_not_editable")
    title = str(data.get("title") or "").strip()
    if len(title) < 3:
        raise ApiError("title must be at least 3 characters", 422, "invalid_title")
    assignee_id = _coerce_uuid(data.get("assignee_id"), "assignee_id")
    task = ActionTask(
        plan_id=plan_id,
        title=title,
        description=data.get("description"),
        created_by=actor.id,
        owner_id=actor.id,
        assignee_id=assignee_id,
        priority=data.get("priority") or "MEDIUM",
        status="TODO",
        due_at=_parse_dt(data.get("due_at"), "due_at"),
        location=data.get("location"),
        institution_id=_coerce_uuid(data.get("institution_id"), "institution_id"),
        checklist=data.get("checklist") or [],
    )
    session.add(task)
    await session.flush()
    await audit(
        session,
        action="civic_action.task_create",
        entity_type="action_task",
        entity_id=task.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _task_payload(task)


async def update_task(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    task = await _get_task(session, task_id)
    plan = await _get_plan(session, task.plan_id)
    is_owner = await _can_edit_plan(session, plan, actor)
    is_assignee = task.assignee_id == actor.id or task.owner_id == actor.id
    if not (is_owner or is_assignee):
        raise ApiError("not permitted to edit this task", 403, "forbidden")
    before = {"status": task.status}
    if data.get("title") is not None:
        title = str(data["title"]).strip()
        if len(title) < 3:
            raise ApiError("title must be at least 3 characters", 422, "invalid_title")
        task.title = title
    if data.get("description") is not None:
        task.description = data["description"]
    if data.get("priority") is not None:
        task.priority = data["priority"]
    if data.get("due_at") is not None or "due_at" in data:
        task.due_at = _parse_dt(data.get("due_at"), "due_at")
    if data.get("location") is not None:
        task.location = data["location"]
    if data.get("institution_id") is not None:
        task.institution_id = _coerce_uuid(data["institution_id"], "institution_id")
    if data.get("checklist") is not None:
        task.checklist = data["checklist"]
    new_status = data.get("status")
    if new_status is not None:
        _apply_task_status_transition(task, new_status)
    if new_status == "BLOCKED":
        task.blocked_reason = data.get("blocked_reason")
        task.blocked_at = datetime.now(UTC)
    await audit(
        session,
        action="civic_action.task_update",
        entity_type="action_task",
        entity_id=task.id,
        actor_id=actor.id,
        before=before,
        after={"status": task.status},
        request=request,
    )
    await session.commit()
    return _task_payload(task)


def _apply_task_status_transition(task: ActionTask, new_status: str) -> None:
    allowed: dict[str, set[str]] = {
        "TODO": {"ASSIGNED", "IN_PROGRESS", "BLOCKED", "CANCELLED"},
        "ASSIGNED": {"IN_PROGRESS", "BLOCKED", "CANCELLED", "TODO"},
        "IN_PROGRESS": {"BLOCKED", "SUBMITTED", "CANCELLED"},
        "BLOCKED": {"IN_PROGRESS", "TODO", "ASSIGNED", "CANCELLED"},
        "SUBMITTED": {"COMPLETED", "IN_PROGRESS", "BLOCKED", "CANCELLED"},
        "VERIFICATION_PENDING": {"COMPLETED", "IN_PROGRESS", "BLOCKED"},
        "COMPLETED": set(),
        "CANCELLED": {"IN_PROGRESS", "TODO", "ASSIGNED"},
    }
    if task.status == new_status:
        return
    if new_status == "COMPLETED" and task.status != "VERIFICATION_PENDING":
        raise ApiError("task must be verified before completion", 409, "requires_verification")
    if new_status not in allowed.get(task.status, set()):
        raise ApiError(
            f"cannot transition task from {task.status} to {new_status}",
            409,
            "invalid_task_transition",
        )
    task.status = new_status
    if new_status == "COMPLETED":
        task.completed_at = datetime.now(UTC)


async def assign_task(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    actor: User,
    assignee_id: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    task = await _get_task(session, task_id)
    plan = await _get_plan(session, task.plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to assign this task", 403, "forbidden")
    assignee = await session.get(User, assignee_id)
    if assignee is None or assignee.status != "active":
        raise ApiError("assignee not found", 404, "assignee_not_found")
    old = task.assignee_id
    task.assignee_id = assignee_id
    if task.status == "TODO":
        task.status = "ASSIGNED"
    await audit(
        session,
        action="civic_action.task_assign",
        entity_type="action_task",
        entity_id=task.id,
        actor_id=actor.id,
        before={"assignee_id": str(old) if old else None},
        after={"assignee_id": str(assignee_id)},
        request=request,
    )
    await enqueue_for_users(
        session,
        user_ids=[assignee_id],
        event="civic_action.task_assigned",
        payload={"title": task.title, "task_id": str(task.id)},
        channels=["in_app"],
    )
    await session.commit()
    return _task_payload(task)


async def delete_task(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    task = await _get_task(session, task_id)
    plan = await _get_plan(session, task.plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to delete this task", 403, "forbidden")
    if task.status in ("VERIFICATION_PENDING", "COMPLETED"):
        raise ApiError("cannot delete a task that is verified or completed", 409, "task_locked")
    await audit(
        session,
        action="civic_action.task_delete",
        entity_type="action_task",
        entity_id=task.id,
        actor_id=actor.id,
        request=request,
    )
    await session.delete(task)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Milestones + dependencies
# ---------------------------------------------------------------------------


async def create_milestone(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    plan_id = _require_uuid(data.get("plan_id"), "plan_id")
    plan = await _get_plan(session, plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this plan", 403, "forbidden")
    milestone = ActionMilestone(
        plan_id=plan_id,
        title=str(data.get("title") or "").strip(),
        description=data.get("description"),
        order_idx=data.get("order_idx") or 0,
        status="pending",
        due_at=_parse_dt(data.get("due_at"), "due_at"),
    )
    if len(milestone.title) < 3:
        raise ApiError("title must be at least 3 characters", 422, "invalid_title")
    session.add(milestone)
    await session.flush()
    await audit(
        session,
        action="civic_action.milestone_create",
        entity_type="action_milestone",
        entity_id=milestone.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _milestone_payload(milestone)


async def update_milestone(
    session: AsyncSession,
    *,
    milestone_id: uuid.UUID,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    milestone = await session.get(ActionMilestone, milestone_id)
    if milestone is None:
        raise ApiError("milestone not found", 404, "milestone_not_found")
    plan = await _get_plan(session, milestone.plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this milestone", 403, "forbidden")
    if data.get("title") is not None:
        milestone.title = str(data["title"]).strip()
    if data.get("status") is not None:
        status = data["status"]
        if status not in {"pending", "in_progress", "completed", "cancelled"}:
            raise ApiError("invalid milestone status", 422, "invalid_status")
        milestone.status = status
        if status == "completed":
            milestone.completed_at = datetime.now(UTC)
    if data.get("order_idx") is not None:
        milestone.order_idx = data["order_idx"]
    if data.get("due_at") is not None or "due_at" in data:
        milestone.due_at = _parse_dt(data.get("due_at"), "due_at")
    await audit(
        session,
        action="civic_action.milestone_update",
        entity_type="action_milestone",
        entity_id=milestone.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _milestone_payload(milestone)


async def add_dependency(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    depends_on_task_id: uuid.UUID,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    task = await _get_task(session, task_id)
    prerequisite = await _get_task(session, depends_on_task_id)
    if task.plan_id != prerequisite.plan_id:
        raise ApiError("tasks must belong to the same plan", 422, "cross_plan_dependency")
    if task_id == depends_on_task_id:
        raise ApiError("a task cannot depend on itself", 422, "self_dependency")
    plan = await _get_plan(session, task.plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this plan", 403, "forbidden")
    dependency = ActionDependency(
        task_id=task_id, depends_on_task_id=depends_on_task_id, created_by=actor.id
    )
    session.add(dependency)
    try:
        await session.flush()
    except Exception as exc:
        await session.rollback()
        raise ApiError("dependency already exists", 409, "dependency_exists") from exc
    await audit(
        session,
        action="civic_action.dependency_add",
        entity_type="action_dependency",
        entity_id=dependency.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {"ok": True, "task_id": str(task_id), "depends_on_task_id": str(depends_on_task_id)}


async def remove_dependency(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    depends_on_task_id: uuid.UUID,
    actor: User,
    request: Request,
) -> dict[str, Any]:
    dependency = await session.scalar(
        select(ActionDependency).where(
            ActionDependency.task_id == task_id,
            ActionDependency.depends_on_task_id == depends_on_task_id,
        )
    )
    if dependency is None:
        raise ApiError("dependency not found", 404, "dependency_not_found")
    task = await _get_task(session, task_id)
    plan = await _get_plan(session, task.plan_id)
    if not await _can_edit_plan(session, plan, actor):
        raise ApiError("not permitted to edit this plan", 403, "forbidden")
    await audit(
        session,
        action="civic_action.dependency_remove",
        entity_type="action_dependency",
        entity_id=dependency.id,
        actor_id=actor.id,
        request=request,
    )
    await session.delete(dependency)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Task comments
# ---------------------------------------------------------------------------


async def add_task_comment(
    session: AsyncSession,
    *,
    task_id: uuid.UUID,
    actor: User,
    body: str,
    request: Request,
) -> dict[str, Any]:
    task = await _get_task(session, task_id)
    plan = await _get_plan(session, task.plan_id)
    initiative = await _get_initiative(session, plan.initiative_id)
    if not await _initiative_visibility(session, initiative, actor):
        raise ApiError("task not found", 404, "task_not_found")
    comment = TaskComment(task_id=task_id, author_id=actor.id, body=body.strip())
    if not comment.body:
        raise ApiError("comment body is required", 422, "invalid_comment")
    session.add(comment)
    await session.flush()
    recipients = {task.assignee_id, task.owner_id, plan.owner_id, plan.created_by} - {
        actor.id,
        None,
    }
    await enqueue_for_users(
        session,
        user_ids=[r for r in recipients if r is not None],
        event="civic_action.task_comment",
        payload={"title": task.title, "task_id": str(task.id)},
        channels=["in_app"],
    )
    await audit(
        session,
        action="civic_action.task_comment_add",
        entity_type="action_task",
        entity_id=task.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {
        "id": str(comment.id),
        "task_id": str(task_id),
        "author_id": str(actor.id),
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


async def list_task_comments(
    session: AsyncSession, task_id: uuid.UUID, viewer: User, limit: int
) -> dict[str, Any]:
    task = await _get_task(session, task_id)
    plan = await _get_plan(session, task.plan_id)
    initiative = await _get_initiative(session, plan.initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("task not found", 404, "task_not_found")
    rows = (
        (
            await session.execute(
                select(TaskComment)
                .where(TaskComment.task_id == task_id)
                .order_by(TaskComment.created_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(c.id),
                "task_id": str(c.task_id),
                "author_id": str(c.author_id),
                "body": c.body,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in rows
        ]
    }


# ---------------------------------------------------------------------------
# Action updates (initiative feed)
# ---------------------------------------------------------------------------


async def add_action_update(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _require_uuid(data.get("initiative_id"), "initiative_id")
    initiative = await _get_initiative(session, initiative_id)
    plan = await session.scalar(select(ActionPlan).where(ActionPlan.initiative_id == initiative_id))
    can_post = (
        _is_moderator(actor)
        or initiative.initiator_id == actor.id
        or (plan is not None and plan.owner_id == actor.id)
    )
    if not can_post:
        member = await session.scalar(
            select(InitiativeMember.id).where(
                InitiativeMember.initiative_id == initiative_id,
                InitiativeMember.user_id == actor.id,
            )
        )
        can_post = member is not None
    if not can_post:
        raise ApiError("not permitted to post updates for this initiative", 403, "forbidden")
    description = str(data.get("description") or "").strip()
    if len(description) < 5:
        raise ApiError("description must be at least 5 characters", 422, "invalid_description")
    snapshot = {}
    if plan is not None:
        snapshot = (await _plan_payload(session, plan)).get("progress", {})
    update = ActionUpdate(
        initiative_id=initiative_id,
        author_id=actor.id,
        description=description,
        status_snapshot=snapshot,
    )
    session.add(update)
    await session.flush()
    await audit(
        session,
        action="civic_action.update_add",
        entity_type="action_update",
        entity_id=update.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return {
        "id": str(update.id),
        "initiative_id": str(initiative_id),
        "author_id": str(actor.id),
        "description": update.description,
        "status_snapshot": update.status_snapshot,
        "created_at": update.created_at.isoformat() if update.created_at else None,
    }


async def list_action_updates(
    session: AsyncSession, initiative_id: uuid.UUID, viewer: User, limit: int, offset: int
) -> dict[str, Any]:
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    rows = (
        (
            await session.execute(
                select(ActionUpdate)
                .where(ActionUpdate.initiative_id == initiative_id)
                .order_by(ActionUpdate.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(u.id),
                "initiative_id": str(u.initiative_id),
                "author_id": str(u.author_id),
                "description": u.description,
                "status_snapshot": u.status_snapshot,
                "evidence_count": u.evidence_count,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in rows
        ]
    }
