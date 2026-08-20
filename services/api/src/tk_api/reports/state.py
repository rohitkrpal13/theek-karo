"""Report status state machine (DATABASE.md §5).

Every edge carries a minimum role. ``system`` edges (auto promotion by the
verification policy) go through :func:`record_system_transition` instead of the
actor-driven transition endpoint. Violations raise 409
``invalid_status_transition``; every applied transition appends to
``report_status_history`` (append-only audit for reports).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.errors import ApiError
from tk_api.reports.models import Report, ReportStatusHistory

ROLE_RANK = {
    "citizen": 0,
    "volunteer": 1,
    "official": 2,
    "department_representative": 2,
    "department_manager": 2,
    "institution_representative": 2,
    "reviewer": 3,
    "admin": 3,
    "super_admin": 4,
}

REPORT_STATUSES: tuple[str, ...] = (
    "draft",
    "submitted",
    "under_verification",
    "verified",
    "assigned",
    "in_progress",
    "resolution_submitted",
    "resolution_review",
    "resolved",
    "reopened",
    "resolution_verified",
    "community_verified",
    "closed",
    "rejected",
    "duplicate_merged",
    "needs_information",
    "archived",
)

# from_status -> {to_status: min_role} (actors with that role rank or higher).
_TRANSITIONS: dict[str, dict[str, str]] = {
    "draft": {"submitted": "citizen"},
    "submitted": {
        "under_verification": "volunteer",
        "verified": "volunteer",
        "assigned": "official",
        "rejected": "volunteer",
        "duplicate_merged": "admin",
        "needs_information": "volunteer",
    },
    "under_verification": {
        "verified": "volunteer",
        "rejected": "volunteer",
        "duplicate_merged": "admin",
        "needs_information": "volunteer",
    },
    "verified": {
        "assigned": "official",
        "in_progress": "official",
        "duplicate_merged": "admin",
    },
    "assigned": {
        "in_progress": "official",
        "rejected": "official",
    },
    "in_progress": {
        "resolution_submitted": "official",
        "resolved": "official",
    },
    "resolution_submitted": {
        "resolution_review": "volunteer",
        "resolved": "official",
        "in_progress": "volunteer",
    },
    "resolution_review": {
        "resolved": "official",
        "resolution_verified": "volunteer",
        "community_verified": "volunteer",
        "in_progress": "volunteer",
        "rejected": "official",
    },
    "resolved": {
        "community_verified": "volunteer",
        "resolution_verified": "volunteer",
        "reopened": "volunteer",
        "closed": "admin",
    },
    "community_verified": {
        "closed": "admin",
        "reopened": "volunteer",
    },
    "resolution_verified": {
        "closed": "admin",
        "reopened": "volunteer",
    },
    "reopened": {
        "assigned": "official",
        "in_progress": "official",
        "resolved": "official",
        "under_verification": "volunteer",
    },
    "needs_information": {
        "submitted": "citizen",
        "under_verification": "volunteer",
        "rejected": "volunteer",
    },
    "rejected": {
        "reopened": "admin",
    },
    "duplicate_merged": {},
    "closed": {
        "archived": "admin",
    },
    "archived": {},
}

# to_status -> column set (and cleared) on the report row.
_TIMESTAMP_ON_ENTER = {
    "resolved": "resolved_at",
    "reopened": "resolved_at",
    "resolution_verified": "resolution_verified_at",
}
_TIMESTAMP_CLEAR = {"reopened": "resolved_at", "resolved": "resolution_verified_at"}


class ReportStateError(ApiError):
    pass


def _max_role(user: Any) -> str | None:
    best: str | None = None
    roles = getattr(user, "roles", None)
    if roles is None:
        return None
    for role in roles:
        code = getattr(role, "code", None)
        if code and code in ROLE_RANK and (best is None or ROLE_RANK[code] > ROLE_RANK[best]):
            best = code
    return best


def _apply(report: Report, to_status: str) -> None:
    report.status = to_status
    if (set_attr := _TIMESTAMP_ON_ENTER.get(to_status)) is not None:
        setattr(report, set_attr, datetime.now(UTC))
    if (clear_attr := _TIMESTAMP_CLEAR.get(to_status)) is not None:
        setattr(report, clear_attr, None)


async def transition_report(
    session: AsyncSession,
    report: Report,
    *,
    to_status: str,
    reason: str | None,
    actor: Any,
) -> None:
    """Validate and apply an actor-driven transition; caller commits."""
    if to_status not in REPORT_STATUSES:
        raise ReportStateError(f"unknown report status: {to_status}", 422, "invalid_status")
    min_role = _TRANSITIONS.get(report.status, {}).get(to_status)
    if min_role is None:
        raise ReportStateError(
            f"cannot transition report from '{report.status}' to '{to_status}'",
            409,
            "invalid_status_transition",
        )
    actor_best = _max_role(actor)
    if actor_best is None or ROLE_RANK[actor_best] < ROLE_RANK[min_role]:
        raise ReportStateError("insufficient role for this transition", 403, "forbidden")
    if to_status in ("rejected", "reopened") and not reason:
        raise ReportStateError(
            f"transition to '{to_status}' requires a reason", 422, "reason_required"
        )

    from_status = report.status
    report.status = to_status
    _apply(report, to_status)
    session.add(
        ReportStatusHistory(
            report_id=report.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor.id,
            reason=reason,
        )
    )


async def record_system_transition(
    session: AsyncSession,
    report: Report,
    *,
    to_status: str,
    reason: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    """Apply an automatic transition (verification policy); caller commits."""
    from_status = report.status
    _apply(report, to_status)
    session.add(
        ReportStatusHistory(
            report_id=report.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            reason=reason,
        )
    )


async def timeline(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(ReportStatusHistory)
                .where(ReportStatusHistory.report_id == report_id)
                .order_by(ReportStatusHistory.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(row.id),
            "from_status": row.from_status,
            "to_status": row.to_status,
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "reason": row.reason,
            "created_at": row.created_at,
        }
        for row in rows
    ]
