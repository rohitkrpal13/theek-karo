"""Resolution workflow service: submission, evidence, review (PRD §47-§54).

A department submits a resolution for a case with staged evidence; an
independent reviewer (``reviewer`` role, never the submitter) decides
verified / more evidence / rejected / partially verified. The review writes
the case state back through the case FSM; every write is audited.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.cases.models import CivicCase
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError, ForbiddenError, NotFoundError
from tk_api.notifications.service import enqueue
from tk_api.resolution.models import (
    ResolutionEvidence,
    ResolutionReview,
    ResolutionSubmission,
)

REVIEW_DECISIONS = frozenset(
    {"verified", "more_evidence_required", "rejected", "partially_verified"}
)

# decision -> case target status
_DECISION_TO_CASE_STATUS: dict[str, str] = {
    "verified": "resolved",
    "more_evidence_required": "resolution_rejected",
    "rejected": "resolution_rejected",
    "partially_verified": "partially_resolved",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def get_submission(session: AsyncSession, submission_id: uuid.UUID) -> ResolutionSubmission:
    row = await session.get(ResolutionSubmission, submission_id)
    if row is None:
        raise NotFoundError("resolution submission not found", kind="submission_not_found")
    return row


async def list_submissions(
    session: AsyncSession,
    *,
    case_id: uuid.UUID | None = None,
    status: str | None = None,
    ordering: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> list[ResolutionSubmission]:
    stmt = select(ResolutionSubmission).order_by(
        ResolutionSubmission.submitted_at.desc()
        if ordering == "desc"
        else ResolutionSubmission.submitted_at.asc()
    )
    if case_id is not None:
        stmt = stmt.where(ResolutionSubmission.case_id == case_id)
    if status is not None:
        stmt = stmt.where(ResolutionSubmission.status == status)
    return list((await session.execute(stmt.limit(limit).offset(offset))).scalars().all())


async def submit_resolution(
    session: AsyncSession,
    *,
    case: CivicCase,
    actor: Any,
    notes: str | None,
    responsible_party: str | None,
    explanation: str | None,
    resolution_date: datetime | None,
    reference_numbers: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
) -> ResolutionSubmission:
    """Submit a resolution for a case in an in-progress state."""
    if case.status not in ("in_progress", "resolution_rejected", "action_planned"):
        raise ApiError(
            "resolution can only be submitted from in-progress states",
            409,
            "invalid_case_status",
        )
    if not evidence:
        raise ApiError("at least one evidence item is required", 422, "evidence_required")
    if not explanation and not reference_numbers:
        raise ApiError(
            "an explanation or reference numbers are required", 422, "explanation_required"
        )

    submission = ResolutionSubmission(
        report_id=case.report_id,
        case_id=case.id,
        submitted_by=actor.id,
        status="submitted",
        notes=notes,
        responsible_party=responsible_party,
        explanation=explanation,
        resolution_date=resolution_date,
        reference_numbers=reference_numbers or {},
    )
    session.add(submission)
    await session.flush()

    for item in evidence:
        kind = item.get("kind", "after")
        if kind not in ("before", "after", "document", "other"):
            raise ApiError(f"invalid evidence kind: {kind}", 422, "invalid_kind")
        session.add(
            ResolutionEvidence(
                resolution_submission_id=submission.id,
                media_object_id=item.get("media_object_id"),
                kind=kind,
                notes=item.get("notes"),
                uploaded_by=actor.id,
                version_no=1,
                document_kind=item.get("document_kind"),
                before_after=item.get("before_after") or ("before" if kind == "before" else None),
                captured_at=item.get("captured_at"),
                checksum=item.get("checksum"),
                visibility=item.get("visibility", "public"),
            )
        )
    await session.flush()

    from tk_api.cases import service as cases_service

    await cases_service.transition(
        session,
        case,
        to_status="resolution_submitted",
        reason="resolution submitted with evidence",
        actor=actor,
    )

    await audit(
        session,
        action="resolution.submit",
        entity_type="resolution_submission",
        entity_id=submission.id,
        actor_id=actor.id,
        after={"case_id": str(case.id), "evidence_count": len(evidence)},
    )
    return submission


async def review_resolution(
    session: AsyncSession,
    submission: ResolutionSubmission,
    *,
    actor: Any,
    decision: str,
    reason: str | None,
    ai_assessment: dict[str, Any] | None = None,
    conflict_of_interest: bool = False,
) -> ResolutionReview:
    """Independent review: verified moves the case to resolved via the FSM."""
    if decision not in REVIEW_DECISIONS:
        raise ApiError(f"invalid decision: {decision}", 422, "invalid_decision")
    if submission.submitted_by == actor.id:
        raise ForbiddenError("reviewer cannot review their own submission")
    if submission.status == "verified":
        raise ApiError("submission already verified", 409, "submission_already_verified")

    case = (
        await session.get(CivicCase, submission.case_id) if submission.case_id is not None else None
    )
    if case is not None:
        if case.status not in ("resolution_submitted", "resolution_under_review"):
            raise ApiError(
                "case is not in the resolution review window", 409, "invalid_case_status"
            )
        from tk_api.cases.state import transition_case

        if case.status == "resolution_submitted":
            await transition_case(
                session,
                case,
                to_status="resolution_under_review",
                reason="submitted for independent review",
                actor=actor,
                actor_id=actor.id,
            )
        await transition_case(
            session,
            case,
            to_status=_DECISION_TO_CASE_STATUS[decision],
            reason=reason or f"review decision: {decision}",
            actor=actor,
            actor_id=actor.id,
        )
        if decision == "verified":
            case.resolution_verified_at = _utcnow()
            case.sla_status = "exempt"

    review = ResolutionReview(
        resolution_submission_id=submission.id,
        reviewer_id=actor.id,
        decision=decision,
        reason=reason,
        ai_assessment=ai_assessment,
        conflict_of_interest=conflict_of_interest,
    )
    session.add(review)
    submission.status = (
        "verified"
        if decision == "verified"
        else ("more_evidence_required" if decision == "more_evidence_required" else "rejected")
    )
    if decision == "partially_verified":
        submission.status = "partially_verified"
    submission.reviewed_by = actor.id
    submission.reviewed_at = _utcnow()

    await audit(
        session,
        action="resolution.review",
        entity_type="resolution_submission",
        entity_id=submission.id,
        actor_id=actor.id,
        after={"decision": decision, "reason": reason},
    )

    if case is not None:
        from tk_api.reports.models import Report

        report = await session.get(Report, case.report_id)
        if report is not None:
            await enqueue(
                session,
                user_id=report.reporter_id,
                event="case.resolution_reviewed",
                locale="en",
                payload={"ticket_no": case.case_no, "decision": decision, "reason": reason or ""},
                channels=["in_app", "email"],
                actor_id=actor.id,
                group_key=f"case:{case.id}:resolution",
            )
    return review


async def add_evidence_version(
    session: AsyncSession,
    submission: ResolutionSubmission,
    *,
    actor: Any,
    items: list[dict[str, Any]],
) -> list[ResolutionEvidence]:
    """Attach a new evidence version (e.g. after the next field visit)."""
    if submission.status not in ("rejected", "more_evidence_required", "submitted"):
        raise ApiError("submission not open for more evidence", 409, "submission_not_open")
    existing = (
        (
            await session.execute(
                select(ResolutionEvidence)
                .where(ResolutionEvidence.resolution_submission_id == submission.id)
                .order_by(ResolutionEvidence.version_no.desc())
            )
        )
        .scalars()
        .first()
    )
    version = (existing.version_no if existing is not None else 0) + 1
    rows: list[ResolutionEvidence] = []
    for item in items:
        row = ResolutionEvidence(
            resolution_submission_id=submission.id,
            media_object_id=item.get("media_object_id"),
            kind=item.get("kind", "other"),
            notes=item.get("notes"),
            uploaded_by=actor.id,
            version_no=version,
            document_kind=item.get("document_kind"),
            before_after=item.get("before_after"),
            captured_at=item.get("captured_at"),
            checksum=item.get("checksum"),
            visibility=item.get("visibility", "public"),
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows
