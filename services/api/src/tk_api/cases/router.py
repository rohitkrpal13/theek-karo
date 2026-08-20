"""Civil case API: lifecycle, assignment, responses, SLA, reopen (PRD §38-§57)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from tk_api.api.deps import CurrentUser, DbSession
from tk_api.auth.authorization import require_any_permission, require_permission
from tk_api.cases import escalation
from tk_api.cases import service as cases_service
from tk_api.cases import sla as sla_engine
from tk_api.cases.models import (
    CaseAction,
    CaseEscalation,
    CaseReopenRequest,
    CivicCase,
    SlaInstance,
)
from tk_api.cases.schemas import (
    CaseActionCreate,
    CaseActionUpdate,
    CaseAssignRequest,
    CaseCreateRequest,
    CaseEscalateRequest,
    CaseReopenRequestCreate,
    CaseReopenReview,
    CaseResponseCreate,
    CaseTransitionRequest,
    SlaPauseRequest,
)
from tk_api.core.errors import ApiError, ForbiddenError, NotFoundError
from tk_api.departments import service as departments_service

cases_router = APIRouter(prefix="/api/v1/cases", tags=["cases"])

DepCasesRead = Annotated[Any, Depends(require_permission("cases.read"))]
DepCasesCreate = Annotated[Any, Depends(require_permission("cases.create"))]
DepCasesInternal = Annotated[Any, Depends(require_permission("cases.read_internal"))]
DepCasesAssign = Annotated[Any, Depends(require_permission("cases.assign"))]
DepCasesRespond = Annotated[Any, Depends(require_permission("cases.respond"))]
DepCasesActions = Annotated[Any, Depends(require_permission("cases.actions.manage"))]
DepCasesReopen = Annotated[Any, Depends(require_permission("cases.reopen.request"))]
DepCasesEscalate = Annotated[Any, Depends(require_permission("cases.escalate"))]
DepSlaRead = Annotated[Any, Depends(require_permission("sla.read"))]
DepSlaManage = Annotated[Any, Depends(require_permission("sla.manage"))]
DepCasesTransition = Annotated[
    Any,
    Depends(require_any_permission("cases.acknowledge", "cases.manage", "resolution.review")),
]
DepReopenReview = Annotated[
    Any,
    Depends(require_any_permission("cases.manage", "departments.members.manage")),
]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, "invalid_id") from exc


async def _resolve_case(session: DbSession, raw_id: str) -> CivicCase:
    return await cases_service.get_case(session, _parse_id(raw_id, kind="case"))


async def _user_can_access_case(session: DbSession, user: CurrentUser, case: CivicCase) -> bool:
    """Department users only access cases inside their departments; the
    reporter, moderators and admins have global access."""
    roles = {getattr(r, "code", None) for r in user.roles}
    if roles & {"super_admin", "admin", "moderator"}:
        return True
    if user.id == case.created_by:
        return True
    if case.primary_department_id is not None and await departments_service.user_in_department(
        session, user.id, case.primary_department_id
    ):
        return True
    from tk_api.reports.models import Report

    report = await session.get(Report, case.report_id)
    return report is not None and report.reporter_id == user.id


async def _require_case_scope(session: DbSession, user: CurrentUser, case: CivicCase) -> None:
    if not await _user_can_access_case(session, user, case):
        raise ForbiddenError("you do not have access to this case")


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------


@cases_router.post("", status_code=201, summary="Create a case from a verified report")
async def create_case(
    body: CaseCreateRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesCreate,
) -> dict[str, Any]:
    from tk_api.reports.models import Report

    report = await session.get(Report, body.report_id)
    if report is None:
        raise NotFoundError("report not found", kind="report_not_found")
    if report.status not in ("verified", "assigned", "in_progress"):
        raise ApiError("case creation requires a verified report", 409, "report_not_verified")
    case = await cases_service.create_case(
        session,
        report=report,
        actor=user,
        department_id=body.department_id,
        severity=body.severity,
        priority=body.priority,
    )
    await session.commit()
    return cases_service._case_payload(case, include_internal=True)


@cases_router.get("", summary="List cases")
async def list_cases(
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesRead,
    status: Annotated[str | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    roles = {getattr(r, "code", None) for r in user.roles}
    is_internal_role = bool(
        roles
        & {
            "super_admin",
            "admin",
            "reviewer",
            "department_manager",
            "department_representative",
            "moderator",
        }
    )
    dept_ids: list[uuid.UUID] = []
    if not is_internal_role:
        rows = await cases_service.list_cases(
            session,
            status=status,
            reporter_id=user.id,
            q=q,
            limit=limit,
            offset=offset,
        )
        return {
            "items": [cases_service._case_payload(c, include_internal=False) for c in rows],
            "count": len(rows),
        }
    if roles & {"department_representative", "department_manager", "reviewer"}:
        memberships = await departments_service.get_user_departments(session, user.id)
        dept_ids = [m.department_id for m in memberships]
        if department_id is not None and department_id not in dept_ids:
            raise ForbiddenError("not a member of that department")
    if department_id is not None:
        dept_ids = [department_id]
    if dept_ids and not (roles & {"super_admin", "admin", "moderator"}):
        rows = []
        for dept_id in dept_ids:
            rows.extend(
                await cases_service.list_cases(
                    session,
                    status=status,
                    department_id=dept_id,
                    q=q,
                    limit=limit,
                    offset=offset,
                )
            )
        rows.sort(key=lambda c: c.created_at, reverse=True)
        rows = rows[:limit]
    else:
        rows = await cases_service.list_cases(
            session, status=status, department_id=department_id, q=q, limit=limit, offset=offset
        )
    return {
        "items": [cases_service._case_payload(c, include_internal=is_internal_role) for c in rows],
        "count": len(rows),
    }


@cases_router.get("/{case_id}", summary="Case detail")
async def get_case(
    case_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesRead,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    roles = {getattr(r, "code", None) for r in user.roles}
    include_internal = bool(
        roles
        & {
            "super_admin",
            "admin",
            "reviewer",
            "department_manager",
            "department_representative",
            "moderator",
        }
    )
    payload = cases_service._case_payload(case, include_internal=include_internal)
    if include_internal:
        payload["responses"] = [
            {
                "id": str(r.id),
                "kind": r.kind,
                "visibility": r.visibility,
                "body": r.body,
                "author_id": str(r.author_id),
                "department_id": str(r.department_id) if r.department_id else None,
                "created_at": r.created_at,
            }
            for r in await cases_service.list_responses(session, case, include_internal=True)
        ]
        escalations = (
            (
                await session.execute(
                    select(CaseEscalation)
                    .where(CaseEscalation.case_id == case.id)
                    .order_by(CaseEscalation.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        payload["escalations"] = [
            {
                "id": str(e.id),
                "level": e.level,
                "status": e.status,
                "reason": e.reason,
                "escalated_by_system": e.escalated_by_system,
                "created_at": e.created_at,
            }
            for e in escalations
        ]
    else:
        payload["responses"] = [
            {
                "id": str(r.id),
                "kind": r.kind,
                "body": r.body,
                "department_id": str(r.department_id) if r.department_id else None,
                "created_at": r.created_at,
            }
            for r in await cases_service.list_responses(session, case, include_internal=False)
        ]
    payload["actions"] = [
        {
            "id": str(a.id),
            "title": a.title,
            "description": a.description,
            "status": a.status,
            "target_date": a.target_date,
            "completed_at": a.completed_at,
        }
        for a in (
            await session.execute(
                select(CaseAction)
                .where(CaseAction.case_id == case.id)
                .order_by(CaseAction.created_at.desc())
            )
        )
        .scalars()
        .all()
    ]
    return payload


@cases_router.get("/{case_id}/timeline", summary="Public case timeline")
async def get_timeline(
    case_id: str,
    session: DbSession,
    _user: DepCasesRead,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    return await cases_service.get_public_timeline(session, case, limit=limit)


@cases_router.post("/{case_id}/transition", summary="Transition case status")
async def transition(
    case_id: str,
    body: CaseTransitionRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesTransition,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    await cases_service.transition(
        session, case, to_status=body.to_status, reason=body.reason, actor=user
    )
    await session.commit()
    return {"id": str(case.id), "status": case.status}


@cases_router.post("/{case_id}/assign", summary="Assign a case to a department")
async def assign(
    case_id: str,
    body: CaseAssignRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesAssign,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    await cases_service.assign(
        session,
        case,
        department_id=body.department_id,
        reason=body.reason,
        actor=user,
        assignee_user_id=body.assignee_user_id,
        geography_id=body.geography_id,
    )
    await session.commit()
    return {"id": str(case.id), "primary_department_id": str(case.primary_department_id)}


# ---------------------------------------------------------------------------
# responses & actions
# ---------------------------------------------------------------------------


@cases_router.post("/{case_id}/respond", summary="Post a case response")
async def respond(
    case_id: str,
    body: CaseResponseCreate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesRespond,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    row = await cases_service.add_response(
        session,
        case,
        kind=body.kind,
        visibility=body.visibility,
        body=body.body,
        actor=user,
    )
    await session.commit()
    return {"id": str(row.id), "created_at": row.created_at}


@cases_router.post("/{case_id}/actions", status_code=201, summary="Create an action item")
async def create_action(
    case_id: str,
    body: CaseActionCreate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesActions,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    row = await cases_service.add_action(
        session,
        case,
        title=body.title,
        description=body.description,
        responsible_team=body.responsible_team,
        target_date=body.target_date,
        actor=user,
    )
    await session.commit()
    return {"id": str(row.id)}


@cases_router.patch("/{case_id}/actions/{action_id}", summary="Update an action item")
async def update_action(
    case_id: str,
    action_id: str,
    body: CaseActionUpdate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesActions,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    action = await session.get(CaseAction, _parse_id(action_id, kind="action"))
    if action is None or action.case_id != case.id:
        raise NotFoundError("action not found", kind="action_not_found")
    row = await cases_service.update_action(
        session, action, status=body.status, notes=body.notes, actor=user
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


# ---------------------------------------------------------------------------
# reopen
# ---------------------------------------------------------------------------


@cases_router.post("/{case_id}/reopen-requests", status_code=201, summary="Request case reopening")
async def request_reopen(
    case_id: str,
    body: CaseReopenRequestCreate,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesReopen,
) -> dict[str, Any]:
    from tk_api.reports.models import Report

    case = await _resolve_case(session, case_id)
    report = await session.get(Report, case.report_id)
    roles = {getattr(r, "code", None) for r in user.roles}
    is_reporter = report is not None and report.reporter_id == user.id
    is_staff = bool(roles & {"moderator", "admin", "super_admin"})
    if not (is_reporter or is_staff):
        raise ForbiddenError("only the reporter may request reopening")
    row = await cases_service.request_reopen(
        session, case, reason=body.reason, evidence=body.evidence, actor=user
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


@cases_router.post(
    "/{case_id}/reopen-requests/{request_id}/review", summary="Review a reopen request"
)
async def review_reopen(
    case_id: str,
    request_id: str,
    body: CaseReopenReview,
    session: DbSession,
    user: CurrentUser,
    _perm: DepReopenReview,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    request = await session.get(CaseReopenRequest, _parse_id(request_id, kind="reopen_request"))
    if request is None or request.case_id != case.id:
        raise NotFoundError("reopen request not found", kind="reopen_request_not_found")
    row = await cases_service.review_reopen_request(
        session, request, decision=body.decision, actor=user
    )
    await session.commit()
    return {"id": str(row.id), "status": row.status}


# ---------------------------------------------------------------------------
# SLA + escalation
# ---------------------------------------------------------------------------


@cases_router.get("/{case_id}/sla", summary="SLA instance for a case")
async def get_sla(
    case_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepSlaRead,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    instance = (
        await session.execute(select(SlaInstance).where(SlaInstance.case_id == case.id))
    ).scalar_one_or_none()
    if instance is None:
        return {"case_id": case_id, "status": case.sla_status}
    now = datetime.now(UTC)
    return {
        "case_id": str(instance.case_id),
        "status": instance.status,
        "started_at": instance.started_at,
        "target_resolution_at": instance.target_resolution_at,
        "paused_seconds": instance.paused_seconds,
        "breached_at": instance.breached_at,
        "remaining_hours": sla_engine.remaining_hours(instance, now),
    }


@cases_router.post("/{case_id}/sla/pause", summary="Pause the case SLA clock")
async def pause_sla(
    case_id: str,
    body: SlaPauseRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepSlaManage,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    pause = await sla_engine.pause_sla(
        session,
        case,
        reason=body.reason,
        actor_id=user.id,
        expected_resume_condition=body.expected_resume_condition,
    )
    await session.commit()
    return {"id": str(pause.id), "status": "paused"}


@cases_router.post("/{case_id}/sla/resume", summary="Resume the case SLA clock")
async def resume_sla(
    case_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepSlaManage,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    pause = await sla_engine.resume_sla(session, case, actor_id=user.id)
    await session.commit()
    return {"id": str(pause.id), "status": "within_sla"}


@cases_router.post("/{case_id}/escalate", summary="Escalate a case manually")
async def escalate_case(
    case_id: str,
    body: CaseEscalateRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepCasesEscalate,
) -> dict[str, Any]:
    case = await _resolve_case(session, case_id)
    await _require_case_scope(session, user, case)
    row = await escalation.escalate(
        session,
        case,
        level=body.level,
        reason=body.reason,
        actor_id=user.id,
        system=False,
        threshold_type="manual",
    )
    await session.commit()
    return {"id": str(row.id) if row else None, "level": body.level}
