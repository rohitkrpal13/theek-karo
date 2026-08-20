"""Civil case orchestration: lifecycle, assignment, responses, reopen (PRD §38-§57).

The case layer is the *routing and accountability* layer on top of the
immutable report record. It owns the case FSM, jurisdiction-scoped
assignment, SLA clocks, reopen requests and the public timeline, and pushes
notifications to the reporter and internal targets.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases import sla as sla_engine
from tk_api.cases.models import (
    CaseAction,
    CaseAssignment,
    CaseReopenRequest,
    CaseResponse,
    CivicCase,
)
from tk_api.cases.state import transition_case
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError, ConflictError, NotFoundError
from tk_api.departments import service as departments_service
from tk_api.notifications.service import enqueue

CaseStatuses = tuple[str, ...]
_CASE_NO_ALPHABET = "0123456789ABCDEFGHJKLMNPQRSTUVWXYZ"

_INTERNAL_KINDS = frozenset({"internal_note"})

RESOLUTION_SUBMITTED_STATUSES = frozenset(
    {"resolution_submitted", "resolution_under_review", "partially_resolved"}
)
CLOSED_STATUSES = frozenset({"resolved", "closed"})
OPEN_STATUSES = frozenset(
    {
        "submitted",
        "under_review",
        "needs_information",
        "verified",
        "assigned",
        "acknowledged",
        "action_planned",
        "in_progress",
        "waiting_for_information",
        "resolution_submitted",
        "resolution_under_review",
        "resolution_rejected",
        "partially_resolved",
        "reopened",
    }
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _make_case_no() -> str:
    """Short, human-friendly case number with negligible collision chance."""
    import random

    n = random.SystemRandom().getrandbits(84)
    chars: list[str] = []
    for _ in range(12):
        chars.append(_CASE_NO_ALPHABET[n % len(_CASE_NO_ALPHABET)])
        n //= len(_CASE_NO_ALPHABET)
    now = _utcnow()
    return f"TK-{now:%y}-{''.join(chars)}"


def is_department_actor(user: Any) -> bool:
    roles = {getattr(r, "code", None) for r in getattr(user, "roles", [])}
    return bool(roles & {"department_representative", "department_manager", "reviewer", "official"})


def _user_locale(user: Any) -> str:
    locale = getattr(user, "locale", None)
    return locale if isinstance(locale, str) and locale in ("en", "hi") else "en"


# ---------------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------------


def _case_payload(case: CivicCase, *, include_internal: bool) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "case_no": case.case_no,
        "report_id": str(case.report_id),
        "status": case.status,
        "primary_department_id": str(case.primary_department_id)
        if case.primary_department_id
        else None,
        "assigned_geography_id": str(case.assigned_geography_id)
        if case.assigned_geography_id
        else None,
        "severity": case.severity,
        "priority": case.priority,
        "sla_policy_id": str(case.sla_policy_id) if case.sla_policy_id else None,
        "sla_started_at": case.sla_started_at,
        "sla_due_at": case.sla_due_at,
        "created_at": case.created_at,
        "updated_at": case.updated_at,
        "closed_at": case.closed_at,
        "reopened_at": case.reopened_at,
        "resolution_verified_at": case.resolution_verified_at,
        "internal": {
            "sla_status": case.sla_status,
        }
        if include_internal
        else None,
    }


async def get_case(session: AsyncSession, case_id: uuid.UUID) -> CivicCase:
    case = await session.get(CivicCase, case_id)
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    return case


async def get_case_by_no(session: AsyncSession, case_no: str) -> CivicCase:
    case = await session.scalar(select(CivicCase).where(CivicCase.case_no == case_no))
    if case is None:
        raise NotFoundError("case not found", kind="case_not_found")
    return case


async def list_cases(
    session: AsyncSession,
    *,
    status: str | None = None,
    department_id: uuid.UUID | None = None,
    reporter_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[CivicCase]:
    stmt = select(CivicCase).order_by(CivicCase.created_at.desc())
    if status is not None:
        stmt = stmt.where(CivicCase.status == status)
    if department_id is not None:
        stmt = stmt.where(CivicCase.primary_department_id == department_id)
    if reporter_id is not None:
        from tk_api.reports.models import Report

        stmt = stmt.join(Report, Report.id == CivicCase.report_id).where(
            Report.reporter_id == reporter_id
        )
    if q:
        stmt = stmt.where(CivicCase.case_no.ilike(f"%{q}%"))
    return list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())


async def get_public_timeline(
    session: AsyncSession,
    case: CivicCase,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """The citizen-visible timeline: status history + public responses + actions."""
    from tk_api.cases.models import CaseStatusHistory

    rows = (
        (
            await session.execute(
                select(CaseStatusHistory)
                .where(CaseStatusHistory.case_id == case.id)
                .order_by(CaseStatusHistory.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.to_status in ("closed", "resolved"):
            continue
        items.append(
            {
                "type": "status_change",
                "at": row.created_at,
                "from_status": row.from_status,
                "to_status": row.to_status,
                "reason": row.reason,
                "actor_id": str(row.actor_id) if row.actor_id else None,
            }
        )
    responses = (
        (
            await session.execute(
                select(CaseResponse)
                .where(CaseResponse.case_id == case.id, CaseResponse.visibility == "public")
                .order_by(CaseResponse.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    for resp in responses:
        items.append(
            {
                "type": "response",
                "at": resp.created_at,
                "kind": resp.kind,
                "body": resp.body,
                "department_id": str(resp.department_id) if resp.department_id else None,
            }
        )
    items.sort(key=lambda i: i["at"], reverse=True)
    return {"case_no": case.case_no, "status": case.status, "items": items[:limit]}


# ---------------------------------------------------------------------------
# creation
# ---------------------------------------------------------------------------


async def create_case(
    session: AsyncSession,
    *,
    report: Any,
    actor: Any,
    department_id: uuid.UUID | None = None,
    severity: str | None = None,
    priority: str = "medium",
) -> CivicCase:
    """Create a case for a verified report; starts the SLA clock."""
    existing = await session.scalar(select(CivicCase).where(CivicCase.report_id == report.id))
    if existing is not None:
        raise ConflictError("a case already exists for this report")
    if priority not in ("low", "medium", "high", "critical"):
        raise ApiError("invalid priority", 422, "invalid_priority")

    category_id = getattr(report, "category_id", None)
    issue_type_id = getattr(report, "issue_type_id", None)
    report_severity = getattr(report, "severity", None) or severity

    policy = await sla_engine.select_sla_policy(
        session,
        category_id=category_id,
        issue_type_id=issue_type_id,
        severity=report_severity,
        department_id=department_id,
    )
    case = CivicCase(
        case_no=_make_case_no(),
        report_id=report.id,
        status="submitted",
        primary_department_id=department_id,
        severity=report_severity,
        priority=priority,
        created_by=actor.id,
    )
    session.add(case)
    await session.flush()
    await sla_engine.start_sla(session, case, policy=policy)
    await audit(
        session,
        action="case.create",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor.id,
        after={
            "case_no": case.case_no,
            "report_id": str(report.id),
            "department_id": str(department_id) if department_id else None,
        },
    )
    return case


# ---------------------------------------------------------------------------
# transitions
# ---------------------------------------------------------------------------


async def transition(
    session: AsyncSession,
    case: CivicCase,
    *,
    to_status: str,
    reason: str | None,
    actor: Any,
) -> CivicCase:
    """Apply and record a case transition, notify the reporter, audit."""
    from tk_api.reports.models import Report

    await transition_case(
        session, case, to_status=to_status, reason=reason, actor=actor, actor_id=actor.id
    )

    if to_status == "resolution_submitted":
        await sla_engine.evaluate_case_sla(session, case)

    if to_status in ("in_progress", "reopened") and case.sla_status in (
        "not_started",
        "exempt",
    ):
        policy = await sla_engine.select_sla_policy(
            session,
            category_id=None,
            issue_type_id=None,
            severity=case.severity,
            department_id=case.primary_department_id,
        )
        await sla_engine.start_sla(session, case, policy=policy)

    if to_status in CLOSED_STATUSES:
        case.sla_status = "exempt"

    await audit(
        session,
        action="case.transition",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor.id,
        after={"from": case.status, "to": to_status, "reason": reason},
    )

    report = await session.get(Report, case.report_id)
    reporter_locale = "en"
    if report is not None:
        from tk_api.users.models import User

        reporter = await session.get(User, report.reporter_id)
        reporter_locale = _user_locale(reporter) if reporter is not None else "en"
        await enqueue(
            session,
            user_id=report.reporter_id,
            event="case.status_change",
            locale=reporter_locale,
            payload={
                "ticket_no": case.case_no,
                "status": to_status,
                "reason": reason or "",
            },
            channels=["in_app", "email"],
            actor_id=actor.id,
            group_key=f"case:{case.id}:status",
        )
    return case


# ---------------------------------------------------------------------------
# assignment
# ---------------------------------------------------------------------------


async def assign(
    session: AsyncSession,
    case: CivicCase,
    *,
    department_id: uuid.UUID,
    reason: str | None,
    actor: Any,
    assignee_user_id: uuid.UUID | None = None,
    geography_id: uuid.UUID | None = None,
) -> CaseAssignment:
    """(Re)assign the case to a department; append-only assignment record."""
    from tk_api.reports.models import Report

    dept = await departments_service.get_department(session, department_id)
    if assignee_user_id is not None and not await departments_service.user_in_department(
        session, assignee_user_id, department_id
    ):
        raise ApiError("assignee must be a member of the department", 422, "invalid_assignee")

    previous = (
        (
            await session.execute(
                select(CaseAssignment).where(
                    CaseAssignment.case_id == case.id, CaseAssignment.is_current.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )

    was_first_assignment = case.primary_department_id is None
    prev_dept = case.primary_department_id
    prev_assignee: uuid.UUID | None = None
    prev_geo = case.assigned_geography_id
    prev_queue: str | None = None
    for old in previous:
        old.is_current = False
        prev_assignee = old.assigned_to_user_id or prev_assignee
        prev_queue = old.queue or prev_queue

    row = CaseAssignment(
        case_id=case.id,
        department_id=dept.id,
        geography_id=geography_id,
        assigned_to_user_id=assignee_user_id,
        assigned_by=actor.id,
        previous_department_id=prev_dept,
        previous_geography_id=prev_geo,
        previous_queue=prev_queue,
        previous_assignee_id=prev_assignee,
        reason=reason,
        is_primary=True,
        is_current=True,
    )
    session.add(row)
    case.primary_department_id = dept.id
    case.assigned_geography_id = geography_id
    if case.status == "verified":
        from tk_api.cases.state import transition_case

        await transition_case(
            session, case, to_status="assigned", reason=reason, actor=actor, actor_id=actor.id
        )

    await audit(
        session,
        action="case.assign",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor.id,
        after={
            "department_id": str(dept.id),
            "assignee_user_id": str(assignee_user_id) if assignee_user_id else None,
            "reason": reason,
        },
    )

    report = await session.get(Report, case.report_id)
    if report is not None:
        await enqueue(
            session,
            user_id=report.reporter_id,
            event="case.assigned",
            locale="en",
            payload={"ticket_no": case.case_no, "department_name": dept.name},
            channels=["in_app", "email"],
            actor_id=actor.id,
            group_key=f"case:{case.id}:assigned",
        )
    if was_first_assignment:
        members = await departments_service.department_member_user_ids(session, dept.id)
        for member_id in members:
            await enqueue(
                session,
                user_id=member_id,
                event="case.assigned",
                locale="en",
                payload={"ticket_no": case.case_no, "department_name": dept.name},
                channels=["in_app"],
                actor_id=actor.id,
                group_key=f"case:{case.id}:team",
            )
    return row


# ---------------------------------------------------------------------------
# responses & actions
# ---------------------------------------------------------------------------


async def add_response(
    session: AsyncSession,
    case: CivicCase,
    *,
    kind: str,
    visibility: str,
    body: str,
    actor: Any,
    department_id: uuid.UUID | None = None,
) -> CaseResponse:
    from tk_api.reports.models import Report

    if kind not in (
        "acknowledgement",
        "public_response",
        "internal_note",
        "progress_update",
    ):
        raise ApiError("invalid response kind", 422, "invalid_kind")
    if visibility not in ("public", "internal"):
        raise ApiError("invalid visibility", 422, "invalid_visibility")
    if kind in _INTERNAL_KINDS or visibility == "internal":
        roles = {getattr(r, "code", None) for r in getattr(actor, "roles", [])}
        allowed = {
            "department_representative",
            "department_manager",
            "reviewer",
            "admin",
            "super_admin",
        }
        if not (roles & allowed):
            raise ApiError("internal notes are department-only", 403, "forbidden")
    if visibility == "internal" and department_id is None:
        department_id = case.primary_department_id

    row = CaseResponse(
        case_id=case.id,
        kind=kind,
        visibility=visibility,
        body=body,
        author_id=actor.id,
        department_id=department_id,
    )
    session.add(row)
    await audit(
        session,
        action="case.response",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor.id,
        after={"kind": kind, "visibility": visibility},
    )
    if visibility == "public":
        report = await session.get(Report, case.report_id)
        if report is not None:
            await enqueue(
                session,
                user_id=report.reporter_id,
                event="case.response",
                locale="en",
                payload={"ticket_no": case.case_no},
                channels=["in_app", "email"],
                actor_id=actor.id,
                group_key=f"case:{case.id}:response",
            )
    return row


async def list_responses(
    session: AsyncSession, case: CivicCase, *, include_internal: bool
) -> list[CaseResponse]:
    stmt = select(CaseResponse).where(CaseResponse.case_id == case.id)
    if not include_internal:
        stmt = stmt.where(CaseResponse.visibility == "public")
    return list(
        (await session.execute(stmt.order_by(CaseResponse.created_at.desc()))).scalars().all()
    )


async def add_action(
    session: AsyncSession,
    case: CivicCase,
    *,
    title: str,
    description: str | None,
    responsible_team: str | None,
    target_date: datetime | None,
    actor: Any,
) -> CaseAction:
    if not title.strip():
        raise ApiError("title is required", 422, "invalid_payload")
    row = CaseAction(
        case_id=case.id,
        title=title.strip(),
        description=description,
        responsible_team=responsible_team,
        target_date=target_date,
        created_by=actor.id,
    )
    session.add(row)
    await audit(
        session,
        action="case.action.create",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor.id,
        after={"title": title},
    )
    return row


async def update_action(
    session: AsyncSession,
    action: CaseAction,
    *,
    status: str | None,
    notes: str | None,
    actor: Any,
) -> CaseAction:
    if status is not None:
        if status not in ("planned", "in_progress", "completed", "cancelled", "blocked"):
            raise ApiError("invalid action status", 422, "invalid_status")
        action.status = status
        if status == "completed":
            action.completed_at = _utcnow()
    if notes is not None:
        action.notes = notes
    await audit(
        session,
        action="case.action.update",
        entity_type="case",
        entity_id=action.case_id,
        actor_id=actor.id,
        after={"action_id": str(action.id), "status": action.status},
    )
    return action


# ---------------------------------------------------------------------------
# reopen requests
# ---------------------------------------------------------------------------


async def request_reopen(
    session: AsyncSession,
    case: CivicCase,
    *,
    reason: str,
    evidence: str | None,
    actor: Any,
) -> CaseReopenRequest:
    if case.status not in CLOSED_STATUSES:
        raise ApiError("only resolved/closed cases can be reopened", 409, "case_not_closed")
    if not reason.strip():
        raise ApiError("reason is required", 422, "reason_required")
    row = CaseReopenRequest(
        case_id=case.id,
        requested_by=actor.id,
        reason=reason.strip(),
        evidence=evidence,
    )
    session.add(row)
    await audit(
        session,
        action="case.reopen.request",
        entity_type="case",
        entity_id=case.id,
        actor_id=actor.id,
        after={},
    )
    return row


async def review_reopen_request(
    session: AsyncSession,
    request: CaseReopenRequest,
    *,
    decision: str,
    actor: Any,
) -> CaseReopenRequest:
    if request.status != "pending":
        raise ApiError("reopen request already reviewed", 409, "request_already_reviewed")
    if decision not in ("approved", "rejected"):
        raise ApiError("decision must be approved or rejected", 422, "invalid_decision")
    request.status = decision
    request.reviewed_by = actor.id
    request.reviewed_at = _utcnow()
    if decision == "approved":
        case = await get_case(session, request.case_id)
        await transition_case(
            session,
            case,
            to_status="reopened",
            reason=request.reason,
            actor=actor,
            actor_id=actor.id,
        )
        policy = await sla_engine.select_sla_policy(
            session,
            category_id=None,
            issue_type_id=None,
            severity=case.severity,
            department_id=case.primary_department_id,
        )
        await sla_engine.start_sla(session, case, policy=policy)
    await audit(
        session,
        action="case.reopen.review",
        entity_type="case_reopen_request",
        entity_id=request.id,
        actor_id=actor.id,
        after={"decision": decision},
    )
    return request
