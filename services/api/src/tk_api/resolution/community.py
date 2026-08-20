"""Community confirmation on resolved cases (PRD §B.2, Phase 15).

After an independent reviewer verifies a resolution, citizens can post one
signal per case: ``observed_improvement`` (feeds the two-confirmer gate) or
``issue_still_exists`` (feeds the reopen signal). Signals are **review
triggers, never auto-closes/auto-reopens**: the gates only record state and
notify the people who act through the existing case FSM.

* Two-confirmer gate — ``confirm_threshold`` distinct citizens (reporter
  counts) confirm the improvement → followups marked ``confirmed`` and
  ``cases.community_confirmed_at`` set; the resolution reviewer closes via
  the existing ``resolved -> closed`` transition.
* Reopen signal — ``reopen_threshold`` distinct citizens report the issue
  persists → followups marked ``escalated`` and a ``ResolutionReopenSignal``
  queued; approving it reopens the case through the existing reopen-request
  machinery (``cases.service.review_reopen_request``).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CivicCase
from tk_api.cases.state import can_transition
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError, ConflictError, NotFoundError
from tk_api.departments import service as departments_service
from tk_api.notifications.service import enqueue
from tk_api.reports.models import Report
from tk_api.resolution.models import ResolutionFollowup, ResolutionReopenSignal

FOLLOWUP_SIGNALS = ("observed_improvement", "issue_still_exists")

# Cases a citizen can follow up on: independently verified and closed-ish.
FOLLOWUP_OPEN_STATUSES = frozenset({"resolved", "closed", "partially_resolved"})
# Reopen signals only make sense once the case is actually closed.
REOPEN_SIGNAL_STATUSES = frozenset({"resolved", "closed"})


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def get_followup(session: AsyncSession, followup_id: uuid.UUID) -> ResolutionFollowup:
    row = await session.get(ResolutionFollowup, followup_id)
    if row is None:
        raise NotFoundError("resolution follow-up not found", kind="followup_not_found")
    return row


async def _followup_users(
    session: AsyncSession, case_id: uuid.UUID, signal: str, statuses: tuple[str, ...]
) -> list[ResolutionFollowup]:
    rows = (
        (
            await session.execute(
                select(ResolutionFollowup)
                .where(
                    ResolutionFollowup.case_id == case_id,
                    ResolutionFollowup.signal == signal,
                    ResolutionFollowup.status.in_(statuses),
                )
                .order_by(ResolutionFollowup.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def create_followup(
    session: AsyncSession,
    *,
    case: CivicCase,
    report: Report,
    actor: Any,
    signal: str,
    observation: str | None,
    confirm_threshold: int,
    reopen_threshold: int,
    request: Any | None = None,
) -> ResolutionFollowup:
    """Record one citizen signal; apply the gates (no auto status changes)."""
    if signal not in FOLLOWUP_SIGNALS:
        raise ApiError(f"invalid signal: {signal}", 422, "invalid_signal")
    if case.status not in FOLLOWUP_OPEN_STATUSES:
        raise ApiError(
            "resolution follow-ups are only open on resolved/closed cases",
            409,
            "case_not_resolved",
        )
    if observation is not None and len(observation.strip()) > 1000:
        raise ApiError("observation is too long (max 1000 chars)", 422, "observation_too_long")

    existing = await session.scalar(
        select(ResolutionFollowup).where(
            ResolutionFollowup.case_id == case.id,
            ResolutionFollowup.user_id == actor.id,
        )
    )
    if existing is not None:
        raise ConflictError("you already responded to this resolution")

    row = ResolutionFollowup(
        case_id=case.id,
        report_id=report.id,
        user_id=actor.id,
        signal=signal,
        observation=observation.strip() if observation else None,
        status="pending",
    )
    session.add(row)
    await session.flush()

    if signal == "observed_improvement":
        confirmations = await _followup_users(
            session, case.id, "observed_improvement", ("pending", "confirmed")
        )
        if len(confirmations) >= max(1, confirm_threshold):
            for item in confirmations:
                item.status = "confirmed"
            case.community_confirmed_at = _utcnow()
            if report.reporter_id != actor.id:
                await enqueue(
                    session,
                    user_id=report.reporter_id,
                    event="resolution.followup_confirmed",
                    locale="en",
                    payload={"case_no": case.case_no},
                    channels=["in_app", "email"],
                    actor_id=actor.id,
                    group_key=f"case:{case.id}:followup",
                )
    elif signal == "issue_still_exists":
        signals = await _followup_users(
            session, case.id, "issue_still_exists", ("pending", "escalated")
        )
        if len(signals) >= max(1, reopen_threshold) and case.status in REOPEN_SIGNAL_STATUSES:
            for item in signals:
                item.status = "escalated"
            session.add(
                ResolutionReopenSignal(
                    case_id=case.id,
                    signal_count=len(signals),
                    raised_by_user_id=signals[0].user_id,
                    status="pending",
                )
            )
            payload = {"case_no": case.case_no, "count": len(signals)}
            if report.reporter_id != actor.id:
                await enqueue(
                    session,
                    user_id=report.reporter_id,
                    event="resolution.reopen_signal",
                    locale="en",
                    payload=payload,
                    channels=["in_app", "email"],
                    actor_id=actor.id,
                    group_key=f"case:{case.id}:reopen",
                )
            member_ids = await departments_service.department_member_user_ids(
                session, case.primary_department_id
            )
            for member_id in member_ids:
                if member_id != actor.id:
                    await enqueue(
                        session,
                        user_id=member_id,
                        event="resolution.reopen_signal",
                        locale="en",
                        payload=payload,
                        channels=["in_app"],
                        actor_id=actor.id,
                        group_key=f"case:{case.id}:reopen",
                    )

    await audit(
        session,
        action="resolution.followup",
        entity_type="resolution_followup",
        entity_id=row.id,
        actor_id=actor.id,
        after={
            "case_id": str(case.id),
            "signal": signal,
            "community_confirmed": case.community_confirmed_at is not None,
        },
        request=request,
    )
    return row


async def list_followups(
    session: AsyncSession,
    *,
    case: CivicCase,
    viewer: Any | None = None,
) -> dict[str, Any]:
    """Aggregate signal counts (no PII) + the viewer's own row + pending signal."""
    rows = (
        (
            await session.execute(
                select(ResolutionFollowup)
                .where(ResolutionFollowup.case_id == case.id)
                .order_by(ResolutionFollowup.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    confirmed = sum(1 for r in rows if r.signal == "observed_improvement")
    still_exists = sum(1 for r in rows if r.signal == "issue_still_exists")
    distinct_users = len({r.user_id for r in rows})

    my_followup = None
    if viewer is not None:
        mine = next((r for r in rows if r.user_id == viewer.id), None)
        if mine is not None:
            my_followup = {
                "id": str(mine.id),
                "signal": mine.signal,
                "observation": mine.observation,
                "status": mine.status,
                "created_at": mine.created_at,
            }

    pending_signal = await session.scalar(
        select(ResolutionReopenSignal).where(
            ResolutionReopenSignal.case_id == case.id,
            ResolutionReopenSignal.status == "pending",
        )
    )

    return {
        "case_id": str(case.id),
        "case_no": case.case_no,
        "community_confirmed_at": case.community_confirmed_at,
        "observed_improvement_count": confirmed,
        "issue_still_exists_count": still_exists,
        "distinct_contributors": distinct_users,
        "my_followup": my_followup,
        "pending_reopen_signal": (
            {
                "id": str(pending_signal.id),
                "signal_count": pending_signal.signal_count,
                "status": pending_signal.status,
                "created_at": pending_signal.created_at,
            }
            if pending_signal is not None
            else None
        ),
    }


async def list_reopen_signals(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    stmt = select(ResolutionReopenSignal).order_by(ResolutionReopenSignal.created_at.asc())
    if status is not None:
        if status not in ("pending", "approved", "dismissed"):
            raise ApiError("invalid signal status", 422, "invalid_status")
        stmt = stmt.where(ResolutionReopenSignal.status == status)
    rows = (await session.execute(stmt.limit(min(max(limit, 1), 200)))).scalars().all()
    items: list[dict[str, Any]] = []
    for row in rows:
        case = await session.get(CivicCase, row.case_id)
        items.append(
            {
                "id": str(row.id),
                "case_id": str(row.case_id),
                "case_no": case.case_no if case is not None else None,
                "signal_count": row.signal_count,
                "raised_by_user_id": str(row.raised_by_user_id) if row.raised_by_user_id else None,
                "status": row.status,
                "decision_note": row.decision_note,
                "created_at": row.created_at,
            }
        )
    return items


async def get_reopen_signal(session: AsyncSession, signal_id: uuid.UUID) -> ResolutionReopenSignal:
    row = await session.get(ResolutionReopenSignal, signal_id)
    if row is None:
        raise NotFoundError("reopen signal not found", kind="reopen_signal_not_found")
    return row


async def review_reopen_signal(
    session: AsyncSession,
    signal: ResolutionReopenSignal,
    *,
    decision: str,
    note: str | None,
    actor: Any,
    request: Any | None = None,
) -> ResolutionReopenSignal:
    """Human review of an aggregate reopen signal (approve reopens via FSM)."""
    if signal.status != "pending":
        raise ApiError("signal already reviewed", 409, "signal_already_reviewed")
    if decision not in ("approved", "dismissed"):
        raise ApiError("decision must be approved or dismissed", 422, "invalid_decision")

    case = await session.get(CivicCase, signal.case_id)
    if decision == "approved":
        if case is None or case.status not in REOPEN_SIGNAL_STATUSES:
            raise ApiError("case is no longer open to reopening", 409, "case_not_reopenable")
        roles = {getattr(r, "code", None) for r in getattr(actor, "roles", [])}
        if not can_transition(case.status, "reopened", {c for c in roles if isinstance(c, str)}):
            raise ApiError(
                "your role cannot reopen this case (closed cases require an admin)",
                409,
                "reopen_not_permitted",
            )
        reason = f"Community reopen signal ({signal.signal_count} citizens)"
        if note:
            reason += f": {note.strip()}"
        from tk_api.cases import service as cases_service

        reopen_request = await cases_service.request_reopen(
            session, case, reason=reason, evidence=None, actor=actor
        )
        await session.flush()  # apply the status column default before review
        await cases_service.review_reopen_request(
            session, reopen_request, decision="approved", actor=actor
        )
        from tk_api.reports.models import Report as TkReport

        report = await session.get(TkReport, case.report_id)
        if report is not None and report.reporter_id != actor.id:
            await enqueue(
                session,
                user_id=report.reporter_id,
                event="resolution.reopen_approved",
                locale="en",
                payload={"case_no": case.case_no},
                channels=["in_app", "email"],
                actor_id=actor.id,
                group_key=f"case:{case.id}:reopen",
            )

    signal.status = decision
    signal.decided_by = actor.id
    signal.decided_at = _utcnow()
    signal.decision_note = note

    await audit(
        session,
        action="resolution.reopen_signal.review",
        entity_type="resolution_reopen_signal",
        entity_id=signal.id,
        actor_id=actor.id,
        after={"decision": decision, "note": note, "case_id": str(case.id) if case else None},
        request=request,
    )
    return signal
