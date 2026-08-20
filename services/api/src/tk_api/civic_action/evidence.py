"""Phase 21 evidence, verification, and impact measurement services.

Design rules:

* Evidence bytes are stored through the existing media pipeline (scan gate,
  checksums); only the uploader's own MediaObjects can be attached.
* ``verification_status`` is set by humans only (evidence_reviewer team role,
  plan owner, or moderator); a rejected item can be re-submitted.
* Impact measurements are never self-verified: they require an approved
  human review, and "verified" impact requires approved evidence.
* Progress/impact rollups are deterministic derivations of stored state.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.civic_action.models import (
    ActionEvidence,
    ActionMilestone,
    ActionPlan,
    ActionReview,
    ActionTask,
    ImpactMeasurement,
    ImpactMetric,
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
from tk_api.media.models import MediaObject
from tk_api.notifications.events import enqueue_for_users
from tk_api.users.models import User

EVIDENCE_STATUSES = ("unverified", "pending", "approved", "rejected")
IMPACT_DECISIONS = ("approved", "rejected")


async def _can_verify_evidence(
    session: AsyncSession, initiative_id: uuid.UUID, actor: User
) -> bool:
    """Evidence reviewers, plan owners, initiative initiators, moderators."""
    if _is_moderator(actor):
        return True
    initiative = await _get_initiative(session, initiative_id)
    if initiative.initiator_id == actor.id:
        return True
    plan = await session.scalar(select(ActionPlan).where(ActionPlan.initiative_id == initiative_id))
    if plan is not None and plan.owner_id == actor.id:
        return True
    from tk_api.civic_action.models import CivicTeamMember

    role = await session.scalar(
        select(CivicTeamMember.role).where(CivicTeamMember.user_id == actor.id)
    )
    return role == "evidence_reviewer"


async def _can_approve_impact(session: AsyncSession, plan_id: uuid.UUID, actor: User) -> bool:
    """Data reviewers, plan owners, initiative initiators, moderators."""
    if _is_moderator(actor):
        return True
    plan = await _get_plan(session, plan_id)
    initiative = await _get_initiative(session, plan.initiative_id)
    if initiative.initiator_id == actor.id or plan.owner_id == actor.id:
        return True
    from tk_api.civic_action.models import CivicTeamMember

    role = await session.scalar(
        select(CivicTeamMember.role).where(CivicTeamMember.user_id == actor.id)
    )
    return role == "data_reviewer"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


async def attach_evidence(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    initiative_id = _require_uuid(data.get("initiative_id"), "initiative_id")
    media_id = _require_uuid(data.get("media_id"), "media_id")
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, actor):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    media = await session.get(MediaObject, media_id)
    if media is None:
        raise ApiError("media not found", 404, "media_not_found")
    if media.uploaded_by != actor.id:
        raise ApiError("media was not uploaded by you", 403, "media_not_owned")
    if media.status != "ready":
        raise ApiError("media is not ready (scan still processing)", 409, "media_not_ready")
    task_id = _coerce_uuid(data.get("task_id"), "task_id")
    plan_id = _coerce_uuid(data.get("plan_id"), "plan_id")
    if task_id is not None:
        task = await _get_task(session, task_id)
        plan = await _get_plan(session, task.plan_id)
        if plan.initiative_id != initiative_id:
            raise ApiError("task does not belong to this initiative", 422, "task_mismatch")
        plan_id = plan.id
    elif plan_id is not None:
        plan = await _get_plan(session, plan_id)
        if plan.initiative_id != initiative_id:
            raise ApiError("plan does not belong to this initiative", 422, "plan_mismatch")
    evidence = ActionEvidence(
        initiative_id=initiative_id,
        plan_id=plan_id,
        task_id=task_id,
        uploader_id=actor.id,
        media_id=media_id,
        kind=data.get("kind") or "general",
        notes=data.get("notes"),
        checklist_snapshot={},
        location=data.get("location"),
        sha256=media.checksum_sha256 or "",
        mime_type=media.mime_type or "",
        size_bytes=media.size_bytes or 0,
        verification_status="unverified",
    )
    session.add(evidence)
    await session.flush()
    if task_id is not None:
        task = await _get_task(session, task_id)
        if task.status in ("SUBMITTED", "IN_PROGRESS", "ASSIGNED", "TODO"):
            task.status = "VERIFICATION_PENDING"
            task.completed_at = None
    await audit(
        session,
        action="civic_action.evidence_attach",
        entity_type="action_evidence",
        entity_id=evidence.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _evidence_payload(evidence)


def _evidence_payload(evidence: ActionEvidence) -> dict[str, Any]:
    return {
        "id": str(evidence.id),
        "initiative_id": str(evidence.initiative_id),
        "plan_id": str(evidence.plan_id) if evidence.plan_id else None,
        "task_id": str(evidence.task_id) if evidence.task_id else None,
        "uploader_id": str(evidence.uploader_id),
        "media_id": str(evidence.media_id),
        "kind": evidence.kind,
        "notes": evidence.notes,
        "checklist_snapshot": evidence.checklist_snapshot,
        "location": evidence.location,
        "sha256": evidence.sha256,
        "mime_type": evidence.mime_type,
        "size_bytes": evidence.size_bytes,
        "verification_status": evidence.verification_status,
        "reviewed_by": str(evidence.reviewed_by) if evidence.reviewed_by else None,
        "reviewed_at": evidence.reviewed_at.isoformat() if evidence.reviewed_at else None,
        "review_note": evidence.review_note,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
    }


async def list_evidence(
    session: AsyncSession,
    *,
    viewer: User,
    initiative_id: uuid.UUID,
    task_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    stmt = select(ActionEvidence).where(ActionEvidence.initiative_id == initiative_id)
    if task_id is not None:
        stmt = stmt.where(ActionEvidence.task_id == task_id)
    rows = (
        (
            await session.execute(
                stmt.order_by(ActionEvidence.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return {"items": [_evidence_payload(e) for e in rows]}


async def review_evidence(
    session: AsyncSession,
    *,
    evidence_id: uuid.UUID,
    actor: User,
    decision: str,
    note: str | None,
    request: Request,
) -> dict[str, Any]:
    evidence = await session.get(ActionEvidence, evidence_id)
    if evidence is None:
        raise ApiError("evidence not found", 404, "evidence_not_found")
    if not await _can_verify_evidence(session, evidence.initiative_id, actor):
        raise ApiError("not permitted to review evidence", 403, "forbidden")
    if evidence.verification_status == "approved":
        raise ApiError("evidence is already approved", 409, "already_approved")
    if decision not in ("approved", "rejected"):
        raise ApiError("decision must be approved or rejected", 422, "invalid_decision")
    evidence.verification_status = decision
    evidence.reviewed_by = actor.id
    evidence.reviewed_at = datetime.now(UTC)
    evidence.review_note = note
    await enqueue_for_users(
        session,
        user_ids=[evidence.uploader_id],
        event="civic_action.evidence_reviewed",
        payload={"status": decision, "evidence_id": str(evidence.id)},
        channels=["in_app"],
    )
    await audit(
        session,
        action="civic_action.evidence_review",
        entity_type="action_evidence",
        entity_id=evidence.id,
        actor_id=actor.id,
        after={"decision": decision, "note": note},
        request=request,
    )
    await session.commit()
    return _evidence_payload(evidence)


# ---------------------------------------------------------------------------
# Outcome reviews
# ---------------------------------------------------------------------------


async def create_review(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    entity_type = data.get("entity_type")
    entity_id = _require_uuid(data.get("entity_id"), "entity_id")
    decision = data.get("decision") or "approved"
    if entity_type == "task":
        task = await _get_task(session, entity_id)
        plan = await _get_plan(session, task.plan_id)
        initiative_id = plan.initiative_id
        if not await _can_verify_evidence(session, initiative_id, actor):
            raise ApiError("not permitted to review outcomes", 403, "forbidden")
        if task.status != "VERIFICATION_PENDING":
            raise ApiError("task is not awaiting review", 409, "not_verification_pending")
        review = ActionReview(
            entity_type="task",
            entity_id=entity_id,
            decision=decision,
            reviewer_id=actor.id,
            note=data.get("note"),
            evidence_ids=[
                str(_require_uuid(e, "evidence_ids")) for e in data.get("evidence_ids") or []
            ],
        )
        session.add(review)
        await session.flush()
        if decision == "approved":
            task.status = "COMPLETED"
            task.completed_at = datetime.now(UTC)
        elif decision == "rejected":
            task.status = "IN_PROGRESS"
        await enqueue_for_users(
            session,
            user_ids=[task.assignee_id] if task.assignee_id else [],
            event="civic_action.evidence_reviewed",
            payload={"status": decision, "task_id": str(task.id)},
            channels=["in_app"],
        )
    elif entity_type == "initiative":
        initiative = await _get_initiative(session, entity_id)
        if not await _can_verify_evidence(session, initiative.id, actor):
            raise ApiError("not permitted to review outcomes", 403, "forbidden")
        review = ActionReview(
            entity_type="initiative",
            entity_id=entity_id,
            decision=decision,
            reviewer_id=actor.id,
            note=data.get("note"),
            evidence_ids=[
                str(_require_uuid(e, "evidence_ids")) for e in data.get("evidence_ids") or []
            ],
        )
        session.add(review)
        await session.flush()
        if decision == "approved":
            plan_row: ActionPlan | None = await session.scalar(
                select(ActionPlan).where(ActionPlan.initiative_id == entity_id)
            )
            if plan_row is not None:
                plan_row.status = "VERIFICATION_PENDING"
        await enqueue_for_users(
            session,
            user_ids=[initiative.initiator_id],
            event="civic_action.evidence_reviewed",
            payload={"status": decision, "initiative_id": str(initiative.id)},
            channels=["in_app"],
        )
    else:
        raise ApiError("entity_type must be task or initiative", 422, "invalid_entity_type")
    if decision not in ("approved", "rejected"):
        raise ApiError("decision must be approved or rejected", 422, "invalid_decision")
    await audit(
        session,
        action="civic_action.review_create",
        entity_type=f"action_review_{entity_type}",
        entity_id=review.id,
        actor_id=actor.id,
        after={"decision": decision},
        request=request,
    )
    await session.commit()
    return {
        "id": str(review.id),
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "decision": decision,
        "reviewer_id": str(actor.id),
        "note": review.note,
        "evidence_ids": [str(e) for e in review.evidence_ids],
    }


async def list_reviews(
    session: AsyncSession, *, viewer: User, entity_type: str, entity_id: uuid.UUID, limit: int
) -> dict[str, Any]:
    if entity_type == "task":
        task = await _get_task(session, entity_id)
        plan = await _get_plan(session, task.plan_id)
        initiative_id = plan.initiative_id
    elif entity_type == "initiative":
        initiative = await _get_initiative(session, entity_id)
        initiative_id = initiative.id
    else:
        raise ApiError("entity_type must be task or initiative", 422, "invalid_entity_type")
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("not found", 404, "not_found")
    rows = (
        (
            await session.execute(
                select(ActionReview)
                .where(ActionReview.entity_type == entity_type, ActionReview.entity_id == entity_id)
                .order_by(ActionReview.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": str(r.id),
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id),
                "decision": r.decision,
                "reviewer_id": str(r.reviewer_id),
                "note": r.note,
                "evidence_ids": [str(e) for e in r.evidence_ids],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Impact metrics + measurements
# ---------------------------------------------------------------------------


async def create_impact_metric(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    plan_id = _require_uuid(data.get("plan_id"), "plan_id")
    plan = await _get_plan(session, plan_id)
    if plan.owner_id != actor.id and not _is_moderator(actor):
        raise ApiError("not permitted to create impact metrics", 403, "forbidden")
    name = str(data.get("name") or "").strip()
    if len(name) < 3:
        raise ApiError("name must be at least 3 characters", 422, "invalid_name")
    metric = ImpactMetric(
        plan_id=plan_id,
        name=name,
        description=data.get("description"),
        baseline=data.get("baseline") or 0.0,
        target=data.get("target"),
        unit=data.get("unit"),
        source=data.get("source"),
        methodology=data.get("methodology"),
        created_by=actor.id,
    )
    session.add(metric)
    await session.flush()
    await audit(
        session,
        action="civic_action.impact_metric_create",
        entity_type="impact_metric",
        entity_id=metric.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _impact_metric_payload(metric)


def _impact_metric_payload(metric: ImpactMetric) -> dict[str, Any]:
    return {
        "id": str(metric.id),
        "plan_id": str(metric.plan_id),
        "name": metric.name,
        "description": metric.description,
        "baseline": metric.baseline,
        "target": metric.target,
        "unit": metric.unit,
        "source": metric.source,
        "methodology": metric.methodology,
        "created_by": str(metric.created_by),
    }


async def list_impact_metrics(
    session: AsyncSession, *, viewer: User, plan_id: uuid.UUID
) -> dict[str, Any]:
    plan = await _get_plan(session, plan_id)
    initiative = await _get_initiative(session, plan.initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("plan not found", 404, "plan_not_found")
    rows = (
        (await session.execute(select(ImpactMetric).where(ImpactMetric.plan_id == plan_id)))
        .scalars()
        .all()
    )
    return {"items": [_impact_metric_payload(m) for m in rows]}


async def record_measurement(
    session: AsyncSession,
    *,
    actor: User,
    data: dict[str, Any],
    request: Request,
) -> dict[str, Any]:
    metric_id = _require_uuid(data.get("metric_id"), "metric_id")
    metric = await session.get(ImpactMetric, metric_id)
    if metric is None:
        raise ApiError("impact metric not found", 404, "metric_not_found")
    plan = await _get_plan(session, metric.plan_id)
    if plan.owner_id != actor.id and not _is_moderator(actor):
        raise ApiError("not permitted to record measurements", 403, "forbidden")
    evidence_id = _coerce_uuid(data.get("evidence_id"), "evidence_id")
    if evidence_id is not None:
        evidence = await session.get(ActionEvidence, evidence_id)
        if evidence is None:
            raise ApiError("evidence not found", 404, "evidence_not_found")
        if evidence.verification_status != "approved":
            raise ApiError("measurement requires approved evidence", 409, "evidence_not_approved")
    measurement = ImpactMeasurement(
        metric_id=metric_id,
        value=data.get("value", 0.0),
        source=data.get("source"),
        methodology_note=data.get("methodology_note"),
        evidence_id=evidence_id,
        status="pending",
        created_by=actor.id,
    )
    session.add(measurement)
    await session.flush()
    await audit(
        session,
        action="civic_action.impact_measurement_record",
        entity_type="impact_measurement",
        entity_id=measurement.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _measurement_payload(measurement)


def _measurement_payload(m: ImpactMeasurement) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "metric_id": str(m.metric_id),
        "value": m.value,
        "source": m.source,
        "methodology_note": m.methodology_note,
        "evidence_id": str(m.evidence_id) if m.evidence_id else None,
        "status": m.status,
        "reviewer_id": str(m.reviewer_id) if m.reviewer_id else None,
        "reviewed_at": m.reviewed_at.isoformat() if m.reviewed_at else None,
        "created_by": str(m.created_by),
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def decide_measurement(
    session: AsyncSession,
    *,
    measurement_id: uuid.UUID,
    actor: User,
    decision: str,
    request: Request,
) -> dict[str, Any]:
    measurement = await session.get(ImpactMeasurement, measurement_id)
    if measurement is None:
        raise ApiError("measurement not found", 404, "measurement_not_found")
    metric = await session.get(ImpactMetric, measurement.metric_id)
    if metric is None:
        raise ApiError("impact metric not found", 404, "metric_not_found")
    if not await _can_approve_impact(session, metric.plan_id, actor):
        raise ApiError("not permitted to review measurements", 403, "forbidden")
    if measurement.status != "pending":
        raise ApiError("measurement is already decided", 409, "already_decided")
    if decision not in IMPACT_DECISIONS:
        raise ApiError("decision must be approved or rejected", 422, "invalid_decision")
    measurement.status = decision
    measurement.reviewer_id = actor.id
    measurement.reviewed_at = datetime.now(UTC)
    await audit(
        session,
        action="civic_action.impact_measurement_decision",
        entity_type="impact_measurement",
        entity_id=measurement.id,
        actor_id=actor.id,
        after={"decision": decision},
        request=request,
    )
    await session.commit()
    return _measurement_payload(measurement)


# ---------------------------------------------------------------------------
# Analytics (deterministic rollups)
# ---------------------------------------------------------------------------


async def plan_progress(
    session: AsyncSession, *, viewer: User, plan_id: uuid.UUID
) -> dict[str, Any]:
    """Task/milestone/evidence status rollup for a plan."""
    plan = await _get_plan(session, plan_id)
    initiative = await _get_initiative(session, plan.initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("plan not found", 404, "plan_not_found")
    tasks = (
        (await session.execute(select(ActionTask).where(ActionTask.plan_id == plan_id)))
        .scalars()
        .all()
    )
    evidence = await session.scalar(
        select(func.count(ActionEvidence.id)).where(
            ActionEvidence.plan_id == plan_id,
            ActionEvidence.verification_status == "approved",
        )
    )
    from tk_api.civic_action.models import ActionMilestone

    milestones = (
        (await session.execute(select(ActionMilestone).where(ActionMilestone.plan_id == plan_id)))
        .scalars()
        .all()
    )
    return {
        "plan_id": str(plan_id),
        "status": plan.status,
        "progress": _progress_from_tasks(tasks, milestones),
        "approved_evidence_count": evidence or 0,
    }


def _progress_from_tasks(
    tasks: Sequence[ActionTask], milestones: Sequence[ActionMilestone]
) -> dict[str, Any]:
    total = len(tasks)
    done = sum(1 for t in tasks if t.status == "COMPLETED")
    ms_total = len(milestones)
    ms_done = sum(1 for m in milestones if m.status == "completed")
    task_pct = (done / total) if total else 0.0
    ms_pct = (ms_done / ms_total) if ms_total else 0.0
    if total and ms_total:
        overall = round(task_pct * 0.7 + ms_pct * 0.3, 4)
    elif total:
        overall = round(task_pct, 4)
    elif ms_total:
        overall = round(ms_pct, 4)
    else:
        overall = 0.0
    return {
        "tasks_total": total,
        "tasks_done": done,
        "milestones_total": ms_total,
        "milestones_done": ms_done,
        "overall": overall,
    }


async def impact_dashboard(
    session: AsyncSession, *, viewer: User, initiative_id: uuid.UUID
) -> dict[str, Any]:
    """Per-metric verified impact summary. Only approved measurements count."""
    initiative = await _get_initiative(session, initiative_id)
    if not await _initiative_visibility(session, initiative, viewer):
        raise ApiError("initiative not found", 404, "initiative_not_found")
    plan = await session.scalar(select(ActionPlan).where(ActionPlan.initiative_id == initiative_id))
    if plan is None:
        return {"items": [], "summary": {"verified_metrics": 0, "verified_measurements": 0}}
    metrics = (
        (await session.execute(select(ImpactMetric).where(ImpactMetric.plan_id == plan.id)))
        .scalars()
        .all()
    )
    items: list[dict[str, Any]] = []
    verified_measurements = 0
    for metric in metrics:
        measurements = (
            (
                await session.execute(
                    select(ImpactMeasurement).where(ImpactMeasurement.metric_id == metric.id)
                )
            )
            .scalars()
            .all()
        )
        approved = [m for m in measurements if m.status == "approved"]
        verified_measurements += len(approved)
        latest = max(approved, key=lambda m: m.created_at) if approved else None
        items.append(
            {
                "metric_id": str(metric.id),
                "name": metric.name,
                "unit": metric.unit,
                "baseline": metric.baseline,
                "target": metric.target,
                "latest_value": latest.value if latest else None,
                "verified_measurements": len(approved),
                "measurements": [_measurement_payload(m) for m in measurements],
            }
        )
    verified_metrics = sum(1 for i in items if i["verified_measurements"] > 0)
    return {
        "items": items,
        "summary": {
            "verified_metrics": verified_metrics,
            "verified_measurements": verified_measurements,
        },
    }
