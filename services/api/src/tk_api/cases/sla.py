"""Deterministic SLA clocks for cases (PRD §45-§50, DATABASE.md §14).

The clock is data-driven and never per-department hard-coded: a ``SlaPolicy``
is matched by specificity (department → category → issue type → severity → a
default policy with no constraints). Pauses are explicit and audited, and
``evaluate_case_sla`` is a pure function of (started_at, target, paused
seconds, now) so a worker tick can be replayed without side effects.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CivicCase, SlaInstance, SlaPause, SlaPolicy
from tk_api.core.errors import ApiError

SLA_STATUS_NOT_STARTED = "not_started"
SLA_STATUS_WITHIN = "within_sla"
SLA_STATUS_AT_RISK = "at_risk"
SLA_STATUS_BREACHED = "breached"
SLA_STATUS_PAUSED = "paused"
SLA_STATUS_EXEMPT = "exempt"

_PAUSEABLE = ("within_sla", "at_risk")


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def select_sla_policy(
    session: AsyncSession,
    *,
    category_id: uuid.UUID | None,
    issue_type_id: uuid.UUID | None,
    severity: str | None,
    department_id: uuid.UUID | None,
) -> SlaPolicy | None:
    """Best-match active policy: exact department match wins, then default."""
    clauses: list[Any] = []
    if department_id is not None:
        clauses.append(SlaPolicy.department_id == department_id)
    if category_id is not None:
        clauses.append(SlaPolicy.category_id == category_id)
    if issue_type_id is not None:
        clauses.append(SlaPolicy.issue_type_id == issue_type_id)
    if severity is not None:
        clauses.append(SlaPolicy.severity == severity)

    rows = (
        (
            await session.execute(
                select(SlaPolicy)
                .where(SlaPolicy.is_active.is_(True))
                .order_by(SlaPolicy.priority_order.asc(), SlaPolicy.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    matched = None
    best_specificity = -1
    default_policy: SlaPolicy | None = None
    for policy in rows:
        score = 0
        if policy.department_id is not None:
            score += 8
        if policy.category_id is not None:
            score += 4
        if policy.issue_type_id is not None:
            score += 2
        if policy.severity is not None:
            score += 1
        if score == 0:
            default_policy = policy
            continue
        if not clauses and score > 0:
            continue
        if policy.department_id is not None and department_id != policy.department_id:
            continue
        if policy.category_id is not None and category_id != policy.category_id:
            continue
        if policy.issue_type_id is not None and issue_type_id != policy.issue_type_id:
            continue
        if policy.severity is not None and severity != policy.severity:
            continue
        if score > best_specificity:
            best_specificity = score
            matched = policy
    return matched if matched is not None else default_policy


async def start_sla(
    session: AsyncSession,
    case: CivicCase,
    *,
    policy: SlaPolicy | None,
    start: datetime | None = None,
) -> SlaInstance:
    """Create or restart the SLA clock; idempotent per case. Caller commits.

    A reopened case restarts its clock; one SLA instance per case exists and
    ``paused_seconds`` keeps the clock honest across pauses.
    """
    now = start or _utcnow()
    instance = (
        await session.execute(select(SlaInstance).where(SlaInstance.case_id == case.id))
    ).scalar_one_or_none()
    if instance is None:
        instance = SlaInstance(case_id=case.id, policy_id=policy.id if policy else None)
        session.add(instance)

    if policy is None:
        instance.status = SLA_STATUS_EXEMPT
        instance.target_resolution_at = None
        case.sla_policy_id = None
        case.sla_status = SLA_STATUS_EXEMPT
        case.sla_started_at = None
        case.sla_due_at = None
        return instance

    resolution_hours = float(policy.resolution_hours)
    instance.policy_id = policy.id
    instance.status = SLA_STATUS_WITHIN
    instance.started_at = now
    instance.paused_seconds = 0
    instance.breached_at = None
    instance.target_resolution_at = now + timedelta(hours=resolution_hours)

    case.sla_policy_id = policy.id
    case.sla_started_at = now
    case.sla_due_at = instance.target_resolution_at
    case.sla_status = SLA_STATUS_WITHIN
    return instance


async def pause_sla(
    session: AsyncSession,
    case: CivicCase,
    *,
    reason: str,
    actor_id: uuid.UUID | None,
    expected_resume_condition: str | None = None,
    paused_at: datetime | None = None,
) -> SlaPause:
    """Pause the clock with an audited reason; errors when already paused."""
    instance = (
        await session.execute(select(SlaInstance).where(SlaInstance.case_id == case.id))
    ).scalar_one_or_none()
    if instance is None:
        raise ApiError("no SLA instance on case", 409, "sla_not_started")
    if instance.status == SLA_STATUS_PAUSED:
        raise ApiError("SLA clock already paused", 409, "sla_already_paused")
    if instance.status == SLA_STATUS_EXEMPT:
        raise ApiError("SLA clock is exempt", 409, "sla_exempt")
    open_pause = (
        await session.execute(
            select(SlaPause).where(
                SlaPause.sla_instance_id == instance.id, SlaPause.resumed_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if open_pause is not None:
        raise ApiError("an open SLA pause already exists", 409, "sla_already_paused")
    now = paused_at or _utcnow()
    pause = SlaPause(
        sla_instance_id=instance.id,
        reason=reason,
        paused_by=actor_id,
        expected_resume_condition=expected_resume_condition,
        paused_at=now,
    )
    session.add(pause)
    instance.status = SLA_STATUS_PAUSED
    case.sla_status = SLA_STATUS_PAUSED
    return pause


async def resume_sla(
    session: AsyncSession,
    case: CivicCase,
    *,
    actor_id: uuid.UUID | None = None,
    resumed_at: datetime | None = None,
) -> SlaPause:
    """Resume the clock, adding the paused duration to ``paused_seconds``."""
    instance = (
        await session.execute(select(SlaInstance).where(SlaInstance.case_id == case.id))
    ).scalar_one_or_none()
    if instance is None or instance.status != SLA_STATUS_PAUSED:
        raise ApiError("SLA clock is not paused", 409, "sla_not_paused")
    pause = (
        await session.execute(
            select(SlaPause).where(
                SlaPause.sla_instance_id == instance.id, SlaPause.resumed_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if pause is None:
        raise ApiError("missing open SLA pause record", 409, "sla_pause_missing")
    now = resumed_at or _utcnow()
    pause.resumed_at = now
    elapsed = max(0.0, (_as_aware(now) - _as_aware(pause.paused_at)).total_seconds())
    instance.paused_seconds += int(elapsed)
    instance.status = SLA_STATUS_WITHIN
    case.sla_status = SLA_STATUS_WITHIN
    return pause


def _as_aware(value: datetime) -> datetime:
    """SQLite returns naive UTC datetimes; Postgres returns aware ones."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _clock(instance: SlaInstance, now: datetime) -> tuple[float, float] | None:
    """Return (elapsed_seconds, total_seconds) for a started instance."""
    if instance.started_at is None or instance.target_resolution_at is None:
        return None
    started = _as_aware(instance.started_at)
    target = _as_aware(instance.target_resolution_at)
    now = _as_aware(now)
    elapsed = max(0.0, (now - started).total_seconds() - instance.paused_seconds)
    total = max(0.0, (target - started).total_seconds())
    return elapsed, total


async def evaluate_case_sla(
    session: AsyncSession,
    case: CivicCase,
    *,
    now: datetime | None = None,
) -> tuple[SlaInstance | None, str]:
    """Pure evaluation of the case clock; persists only the outcome flags.

    Returns (instance, status) so callers can decide notification/escalation
    without relying on a side effect.
    """
    instance = (
        await session.execute(select(SlaInstance).where(SlaInstance.case_id == case.id))
    ).scalar_one_or_none()
    if instance is None:
        if case.sla_status == SLA_STATUS_EXEMPT:
            return None, SLA_STATUS_EXEMPT
        return None, SLA_STATUS_NOT_STARTED
    if instance.status == SLA_STATUS_PAUSED:
        return instance, SLA_STATUS_PAUSED
    if instance.status == SLA_STATUS_EXEMPT:
        return instance, SLA_STATUS_EXEMPT

    ts = now or _utcnow()
    clock = _clock(instance, ts)
    if clock is None:
        return instance, SLA_STATUS_NOT_STARTED
    elapsed, total = clock
    if total <= 0:
        return instance, SLA_STATUS_BREACHED

    policy: SlaPolicy | None = (
        (
            await session.execute(select(SlaPolicy).where(SlaPolicy.id == instance.policy_id))
        ).scalar_one_or_none()
        if instance.policy_id
        else None
    )
    at_risk_fraction = float(policy.at_risk_pct) if policy else 0.8

    if elapsed >= total:
        status = SLA_STATUS_BREACHED
    elif elapsed >= total * at_risk_fraction:
        status = SLA_STATUS_AT_RISK
    else:
        status = SLA_STATUS_WITHIN

    if status != instance.status:
        instance.status = status
        if status == SLA_STATUS_BREACHED:
            instance.breached_at = ts
        instance.last_checked_at = ts
    case.sla_status = status
    if status == SLA_STATUS_BREACHED:
        case.sla_due_at = instance.target_resolution_at
    return instance, status


def remaining_hours(instance: SlaInstance, now: datetime) -> float | None:
    """Remaining whole-clock hours (for dashboards); None when not started."""
    clock = _clock(instance, now)
    if clock is None:
        return None
    elapsed, total = clock
    return round(max(0.0, (total - elapsed) / 3600.0), 2)


def active_work_time(exempt: bool = False) -> None:
    """Placeholder hook kept for future business-hours policies."""
    if exempt:
        return None
    return None
