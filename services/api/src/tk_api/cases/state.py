"""Civic case state machine (PRD §38-§44, ARCHITECTURE.md §9).

The case lifecycle mirrors the government workflow: intake review,
assignment, acknowledgement, action planning, field work, resolution
submission with evidence, independent review, verified closure and a
controlled reopen path. Every edge lists the global roles allowed to drive
it; jurisdictional *scope* is enforced separately by the service layer,
and the citizen never mutates the case directly (their agency is the
reopen request + dispute flow).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CaseStatusHistory, CivicCase
from tk_api.core.errors import ApiError

CASE_STATUSES: tuple[str, ...] = (
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
    "resolved",
    "closed",
    "reopened",
    "rejected",
    "duplicate",
)

# Roles that participate in the case workflow at all (any other role is a no-op).
CASE_ROLE_UNIVERSE = frozenset(
    {
        "super_admin",
        "admin",
        "reviewer",
        "department_manager",
        "department_representative",
        "official",
        "moderator",
        "institution_representative",
    }
)

# Roles allowed to move the case between states; "citizen" only appears via
# reopen requests, never as a direct transition.
_TRANSITIONS: dict[str, dict[str, frozenset[str]]] = {
    "submitted": {
        "under_review": frozenset(
            {"department_representative", "department_manager", "reviewer", "official", "admin"}
        ),
        "needs_information": frozenset({"department_representative", "department_manager"}),
        "rejected": frozenset(
            {"department_representative", "department_manager", "reviewer", "admin"}
        ),
        "duplicate": frozenset({"admin"}),
    },
    "under_review": {
        "verified": frozenset(
            {"department_representative", "department_manager", "reviewer", "admin"}
        ),
        "needs_information": frozenset({"department_representative", "department_manager"}),
        "in_progress": frozenset({"department_representative", "department_manager"}),
        "rejected": frozenset({"department_representative", "department_manager", "admin"}),
        "duplicate": frozenset({"admin"}),
    },
    "needs_information": {
        "under_review": frozenset({"department_representative", "department_manager"}),
        "rejected": frozenset({"department_representative", "department_manager", "admin"}),
        "duplicate": frozenset({"admin"}),
    },
    "verified": {
        "assigned": frozenset({"department_manager", "admin"}),
        "duplicate": frozenset({"admin"}),
    },
    "assigned": {
        "acknowledged": frozenset(
            {"department_representative", "department_manager", "reviewer", "official", "admin"}
        ),
        "rejected": frozenset({"department_manager", "admin"}),
        "duplicate": frozenset({"admin"}),
    },
    "acknowledged": {
        "action_planned": frozenset({"department_representative", "department_manager"}),
        "in_progress": frozenset({"department_representative", "department_manager"}),
    },
    "action_planned": {
        "in_progress": frozenset({"department_representative", "department_manager"}),
    },
    "in_progress": {
        "waiting_for_information": frozenset({"department_representative", "department_manager"}),
        "resolution_submitted": frozenset({"department_representative", "department_manager"}),
    },
    "waiting_for_information": {
        "in_progress": frozenset({"department_representative", "department_manager"}),
    },
    "resolution_submitted": {
        "resolution_under_review": frozenset({"reviewer", "department_manager", "admin"}),
        "resolution_rejected": frozenset({"reviewer", "admin"}),
        "in_progress": frozenset({"reviewer", "department_manager", "admin"}),
    },
    "resolution_under_review": {
        "resolved": frozenset({"reviewer", "admin"}),
        "partially_resolved": frozenset({"reviewer", "admin"}),
        "resolution_rejected": frozenset({"reviewer", "admin"}),
    },
    "resolution_rejected": {
        "in_progress": frozenset({"department_representative", "department_manager"}),
        "resolution_submitted": frozenset({"department_representative", "department_manager"}),
    },
    "partially_resolved": {
        "in_progress": frozenset({"department_representative", "department_manager"}),
        "resolved": frozenset({"reviewer", "admin"}),
        "closed": frozenset({"reviewer", "admin"}),
    },
    "resolved": {
        "closed": frozenset({"reviewer", "department_manager", "admin"}),
        "reopened": frozenset({"reviewer", "department_manager", "admin"}),
    },
    "closed": {
        "reopened": frozenset({"admin"}),
    },
    "reopened": {
        "assigned": frozenset({"department_manager", "admin"}),
        "in_progress": frozenset({"department_representative", "department_manager"}),
    },
    "rejected": {
        "closed": frozenset({"admin"}),
        "reopened": frozenset({"admin"}),
    },
    "duplicate": {
        "closed": frozenset({"admin"}),
    },
}

TERMINAL_STATUSES = frozenset({"closed"})

# to_status -> column set on the case row.
_TIMESTAMP_ON_ENTER: dict[str, str] = {
    "resolved": "resolution_verified_at",
    "reopened": "reopened_at",
    "closed": "closed_at",
}


class CaseStateError(ApiError):
    pass


def _effective_roles(actor: object) -> set[str]:
    roles = getattr(actor, "roles", None)
    if not roles:
        return set()
    codes = {getattr(role, "code", None) for role in roles}
    return {c for c in codes if isinstance(c, str)}


def is_terminal(status: str) -> bool:
    return status in TERMINAL_STATUSES


def allowed_transitions(current: str) -> list[str]:
    return sorted(_TRANSITIONS.get(current, {}).keys())


def can_transition(current: str, to_status: str, actor_roles: set[str]) -> bool:
    allowed = _TRANSITIONS.get(current, {}).get(to_status)
    if allowed is None:
        return False
    return bool(actor_roles & allowed)


async def transition_case(
    session: AsyncSession,
    case: CivicCase,
    *,
    to_status: str,
    reason: str | None,
    actor: object,
    actor_id: uuid.UUID,
) -> None:
    """Validate and apply an actor-driven case transition; caller commits."""
    if to_status not in CASE_STATUSES:
        raise CaseStateError(f"unknown case status: {to_status}", 422, "invalid_status")
    roles = _effective_roles(actor)
    if not can_transition(case.status, to_status, roles):
        raise CaseStateError(
            f"cannot transition case '{case.status}' to '{to_status}' for these roles",
            409,
            "invalid_status_transition",
        )
    if to_status in ("rejected", "reopened") and not reason:
        raise CaseStateError(
            f"transition to '{to_status}' requires a reason", 422, "reason_required"
        )

    from_status = case.status
    case.status = to_status
    if (set_attr := _TIMESTAMP_ON_ENTER.get(to_status)) is not None:
        setattr(case, set_attr, datetime.now(UTC))
    if to_status in ("reopened", "closed") and from_status == "resolved":
        case.resolution_verified_at = None
    session.add(
        CaseStatusHistory(
            case_id=case.id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            reason=reason,
        )
    )
