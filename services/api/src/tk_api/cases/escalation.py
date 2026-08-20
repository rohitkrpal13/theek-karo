"""Escalation engine for civic cases (PRD §51-§54, ARCHITECTURE.md §10).

Rules are configuration (``escalation_rules``); the engine applies them
deterministically: on a breached SLA the *first* (lowest level) applicable
rule fires once per case, records an append-only ``case_escalations`` row and
notifies every member of the target role inside the case's department.
Manual escalation requires an explicit level and a reason.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CaseEscalation, CivicCase, EscalationRule
from tk_api.cases.sla import SLA_STATUS_BREACHED
from tk_api.core.errors import ApiError
from tk_api.notifications.service import enqueue

_MAX_LEVEL = 5


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def _rules_for(
    session: AsyncSession,
    *,
    threshold_type: str,
    case: CivicCase,
) -> list[EscalationRule]:
    rows = (
        (
            await session.execute(
                select(EscalationRule)
                .where(EscalationRule.is_active.is_(True))
                .order_by(EscalationRule.level.asc(), EscalationRule.priority_order.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        r
        for r in rows
        if r.threshold_type == threshold_type
        and (
            r.department_id is None
            or (
                case.primary_department_id is not None
                and r.department_id == case.primary_department_id
            )
        )
        and (r.category_id is None or r.category_id == getattr(case, "category_id", None))
        and (r.severity is None or r.severity == case.severity)
    ]


async def _current_level(session: AsyncSession, case: CivicCase) -> int:
    row = (
        await session.execute(
            select(CaseEscalation)
            .where(CaseEscalation.case_id == case.id, CaseEscalation.status == "active")
            .order_by(CaseEscalation.level.desc())
        )
    ).scalar_one_or_none()
    return row.level if row is not None else 0


async def _notify_targets(
    session: AsyncSession,
    case: CivicCase,
    rule: EscalationRule,
    *,
    reason: str,
    actor_id: uuid.UUID | None,
) -> None:
    """Notify every active user with the rule's role inside the department."""
    from tk_api.departments.models import DepartmentUser

    if case.primary_department_id is None:
        return
    rows = (
        (
            await session.execute(
                select(DepartmentUser).where(
                    DepartmentUser.department_id == case.primary_department_id,
                    DepartmentUser.is_active.is_(True),
                    DepartmentUser.role_in_department == rule.target_role,
                )
            )
        )
        .scalars()
        .all()
    )
    for member in rows:
        await enqueue(
            session,
            user_id=member.user_id,
            event="case.escalated",
            locale="en",
            payload={
                "ticket_no": case.case_no,
                "reason": reason,
                "level": rule.level,
            },
            channels=["in_app"],
            actor_id=actor_id,
            group_key=f"case:{case.id}:escalation:{rule.level}",
        )


async def escalate(
    session: AsyncSession,
    case: CivicCase,
    *,
    level: int,
    reason: str,
    actor_id: uuid.UUID | None = None,
    system: bool = False,
    threshold_type: str | None = None,
) -> CaseEscalation | None:
    """Apply an escalation at ``level``; returns the new row or None if none."""
    if not reason:
        raise ApiError("escalation requires a reason", 422, "reason_required")
    if level > _MAX_LEVEL:
        raise ApiError(f"escalation level cannot exceed {_MAX_LEVEL}", 422, "invalid_level")
    current = await _current_level(session, case)
    if level <= current:
        raise ApiError(f"already escalated to level {current}", 409, "already_escalated")

    kinds = ["manual"] if not system else ["sla_breached"]
    if threshold_type:
        kinds = [threshold_type]
    rules = [
        r for r in await _rules_for(session, threshold_type=kinds[0], case=case) if r.level == level
    ]
    if not rules:
        rules = [r for r in await _rules_for(session, threshold_type=kinds[0], case=case)]
    rule = rules[0] if rules else None

    escalation = CaseEscalation(
        case_id=case.id,
        level=level,
        previous_level=current,
        reason=reason,
        escalated_by=actor_id,
        escalated_by_system=system,
        status="active",
    )
    session.add(escalation)
    if rule is not None:
        await _notify_targets(session, case, rule, reason=reason, actor_id=actor_id)
    return escalation


async def escalate_on_breach(
    session: AsyncSession,
    case: CivicCase,
    *,
    now: datetime | None = None,
) -> CaseEscalation | None:
    """System escalation when the case SLA breaches; idempotent per level."""
    _ = now
    rules = await _rules_for(session, threshold_type="sla_breached", case=case)
    if not rules:
        return None
    current = await _current_level(session, case)
    for rule in rules:
        if rule.level > current:
            return await escalate(
                session,
                case,
                level=rule.level,
                reason=f"SLA breach automatic escalation (level {rule.level})",
                actor_id=None,
                system=True,
            )
    return None


async def resolve_escalation(
    session: AsyncSession,
    escalation: CaseEscalation,
    *,
    actor_id: uuid.UUID,
    resolution: str | None = None,
) -> None:
    """Mark the escalation resolved; caller commits."""
    if escalation.status != "active":
        raise ApiError("escalation is not active", 409, "escalation_not_active")
    escalation.status = "resolved"
    escalation.resolved_at = _utcnow()
    escalation.resolved_by = actor_id
    _ = resolution


def sla_status_is_breached(status: str) -> bool:
    return status == SLA_STATUS_BREACHED
