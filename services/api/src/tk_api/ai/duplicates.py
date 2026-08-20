"""Duplicate matching + human review queue (AI-ARCHITECTURE.md §4.4, ADR-018).

AI only *suggests* duplicates: when similarity crosses the threshold an
``ai_reviews`` row is queued and the report is flagged ``merged_by_ai``. Only a
reviewer (volunteer/admin) approves the merge — applied as ``duplicate_of`` +
``duplicate_merged`` transition — or rejects it (flag cleared). Every decision
is audited.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.ai.models import AiReview
from tk_api.ai.similarity import similarity
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.notifications.events import queue_ai_review_admin
from tk_api.reports.models import Report
from tk_api.reports.state import transition_report

QUEUE_WINDOW = 200  # candidate scan window for MVP (ADR-030: replace at scale)


class DuplicateError(ApiError):
    pass


async def find_duplicates(
    session: AsyncSession,
    report: Report,
    *,
    threshold: float,
    min_report_age_days: int,
) -> list[tuple[Report, float]]:
    """Similar reports in the same category, ranked (MVP: window + Jaccard)."""
    candidates = (
        (
            await session.execute(
                select(Report)
                .where(
                    Report.category_id == report.category_id,
                    Report.id != report.id,
                    Report.deleted_at.is_(None),
                    Report.duplicate_of.is_(None),
                )
                .order_by(Report.created_at.desc())
                .limit(QUEUE_WINDOW)
            )
        )
        .scalars()
        .all()
    )
    scored = sorted(
        (
            (
                candidate,
                similarity(
                    f"{candidate.title} {candidate.description}",
                    f"{report.title} {report.description}",
                ),
            )
            for candidate in candidates
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return [(c, s) for c, s in scored if s >= threshold][:3]


async def queue_for_review(
    session: AsyncSession,
    *,
    report: Report,
    annotation_id: uuid.UUID | None,
    matches: list[tuple[Report, float]],
) -> int:
    """Create pending ai_reviews for strong matches; flags the report (ADR-018)."""
    created = 0
    for candidate, score in matches:
        review = await session.scalar(
            select(AiReview).where(
                AiReview.kind == "duplicate_merge",
                AiReview.report_id == report.id,
                AiReview.suggested_report_id == candidate.id,
                AiReview.status == "pending",
            )
        )
        if review is not None:
            continue
        session.add(
            AiReview(
                kind="duplicate_merge",
                report_id=report.id,
                annotation_id=annotation_id,
                suggested_report_id=candidate.id,
                similarity=Decimal(str(round(score, 3))),
                status="pending",
            )
        )
        created += 1
    if matches and not report.merged_by_ai:
        report.merged_by_ai = True
    if created:
        await queue_ai_review_admin(
            session, report=report, actor_id=uuid.UUID(str(report.reporter_id))
        )
    return created


async def review_queue(session: AsyncSession, *, limit: int) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(AiReview)
                .where(AiReview.status == "pending")
                .order_by(AiReview.created_at.asc())
                .limit(max(1, min(limit, 100)))
            )
        )
        .scalars()
        .all()
    )
    items: list[dict[str, Any]] = []
    for review in rows:
        report = await session.get(Report, review.report_id)
        suggested = (
            await session.get(Report, review.suggested_report_id)
            if review.suggested_report_id
            else None
        )
        items.append(
            {
                "id": str(review.id),
                "kind": review.kind,
                "status": review.status,
                "similarity": float(review.similarity) if review.similarity is not None else None,
                "created_at": review.created_at,
                "report": {
                    "ticket_no": report.ticket_no if report else None,
                    "id": str(review.report_id),
                },
                "suggested": {
                    "ticket_no": suggested.ticket_no if suggested else None,
                },
            }
        )
    return items


async def decide_review(
    session: AsyncSession,
    *,
    review_id: uuid.UUID,
    approve: bool,
    reason: str | None,
    reviewer: Any,
    request: Request,
) -> dict[str, Any]:
    review = await session.get(AiReview, review_id)
    if review is None:
        raise DuplicateError("review not found", 404, "review_not_found")
    if review.status != "pending":
        raise DuplicateError("review already decided", 409, "review_decided")

    report = await session.get(Report, review.report_id)
    suggested = (
        await session.get(Report, review.suggested_report_id)
        if review.suggested_report_id
        else None
    )
    if report is None:
        raise DuplicateError("report not found", 404, "report_not_found")

    if approve and not reviewer.has_role("admin"):
        # the merge applies an admin-gated state transition (DATABASE.md §5)
        raise DuplicateError("approving a merge requires admin", 403, "forbidden")

    if approve:
        if suggested is None:
            raise DuplicateError("suggested report missing", 409, "suggested_missing")
        if suggested.id == report.id:
            raise DuplicateError("cannot merge a report with itself", 422, "self_merge")
        if report.status in ("submitted", "under_verification", "verified"):
            await transition_report(
                session,
                report,
                to_status="duplicate_merged",
                reason=reason or "AI-suggested merge approved",
                actor=reviewer,
            )
        report.duplicate_of = suggested.id
        report.merged_by_ai = True
        review.status = "approved"
    else:
        report.merged_by_ai = False
        review.status = "rejected"

    review.reviewed_by = reviewer.id
    review.reviewed_at = datetime.now(UTC)
    review.reason = reason
    await audit(
        session,
        action=f"ai.review.{'approve' if approve else 'reject'}",
        entity_type="ai_review",
        entity_id=review.id,
        actor_id=reviewer.id,
        before={
            "report_id": str(report.id),
            "suggested_report_id": str(review.suggested_report_id)
            if review.suggested_report_id
            else None,
        },
        after={
            "status": review.status,
            "duplicate_of": str(report.duplicate_of) if report.duplicate_of else None,
        },
        request=request,
    )
    await session.commit()
    return {"id": str(review.id), "status": review.status, "report_id": str(report.id)}
