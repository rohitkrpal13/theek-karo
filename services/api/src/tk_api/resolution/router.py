"""Resolution workflow API: submit, evidence, independent review (PRD §47-§54).

Phase 15 adds the community confirmation layer over verified resolutions:
citizen follow-up signals under ``/reports/{id}/resolution-followups`` and
the reopen-signal review queue under ``/resolutions/reopen-signals``.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from tk_api.api.deps import CurrentUser, DbSession, OptionalUser, require_active
from tk_api.auth.authorization import require_permission
from tk_api.cases.models import CivicCase
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import rate_limit
from tk_api.reports import service as reports_service
from tk_api.resolution import community as community_service
from tk_api.resolution import service as resolution_service
from tk_api.resolution.schemas import (
    ReopenSignalReviewRequest,
    ResolutionEvidenceAddRequest,
    ResolutionFollowupCreate,
    ResolutionReviewRequest,
    ResolutionSubmitRequest,
)

resolution_router = APIRouter(prefix="/api/v1/resolutions", tags=["resolutions"])

# Community follow-up signals live under the report resource.
followup_router = APIRouter(prefix="/api/v1/reports", tags=["resolution-followups"])
FollowupUser = Annotated[Any, Depends(require_active())]

DepSubmit = Annotated[Any, Depends(require_permission("resolution.submit"))]
DepReview = Annotated[Any, Depends(require_permission("resolution.review"))]
DepVerify = Annotated[Any, Depends(require_permission("resolution.verify"))]


def _parse_id(raw: str, *, kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, "invalid_id") from exc


def _submission_payload(sub: Any, *, include_evidence: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(sub.id),
        "report_id": str(sub.report_id),
        "case_id": str(sub.case_id) if sub.case_id else None,
        "status": sub.status,
        "notes": sub.notes,
        "responsible_party": sub.responsible_party,
        "explanation": sub.explanation,
        "resolution_date": sub.resolution_date,
        "reference_numbers": sub.reference_numbers or {},
        "submitted_by": str(sub.submitted_by),
        "submitted_at": sub.submitted_at,
        "reviewed_by": str(sub.reviewed_by) if sub.reviewed_by else None,
        "reviewed_at": sub.reviewed_at,
        "created_at": sub.created_at,
    }
    return payload


@resolution_router.post("", status_code=201, summary="Submit a resolution with evidence")
async def submit_resolution(
    body: ResolutionSubmitRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepSubmit,
) -> dict[str, Any]:
    from tk_api.cases import service as cases_service

    case = await cases_service.get_case(session, body.case_id)
    sub = await resolution_service.submit_resolution(
        session,
        case=case,
        actor=user,
        notes=body.notes,
        responsible_party=body.responsible_party,
        explanation=body.explanation,
        resolution_date=body.resolution_date,
        reference_numbers=body.reference_numbers,
        evidence=[item.model_dump() for item in body.evidence],
    )
    await session.commit()
    return _submission_payload(sub)


@resolution_router.get("", summary="List resolution submissions")
async def list_resolutions(
    session: DbSession,
    user: CurrentUser,
    _submit: DepSubmit,
    case_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    rows = await resolution_service.list_submissions(session, case_id=case_id, status=status)
    return {
        "items": [_submission_payload(r, include_evidence=False) for r in rows],
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# Phase 15: community reopen-signal review queue (must precede /{submission_id}
# so the literal "reopen-signals" segment wins over the UUID path param)
# ---------------------------------------------------------------------------


@resolution_router.get("/reopen-signals", summary="List community reopen signals (review queue)")
async def list_reopen_signals(
    session: DbSession,
    user: CurrentUser,
    _perm: DepReview,
    status: Annotated[str | None, Query()] = None,
) -> dict[str, Any]:
    items = await community_service.list_reopen_signals(session, status=status)
    return {"items": items, "count": len(items)}


@resolution_router.post(
    "/reopen-signals/{signal_id}/review", summary="Review a community reopen signal"
)
async def review_reopen_signal(
    signal_id: str,
    body: ReopenSignalReviewRequest,
    request: Request,
    session: DbSession,
    user: CurrentUser,
    _perm: DepReview,
) -> dict[str, Any]:
    signal = await community_service.get_reopen_signal(session, _parse_id(signal_id, kind="signal"))
    await community_service.review_reopen_signal(
        session,
        signal,
        decision=body.decision,
        note=body.note,
        actor=user,
        request=request,
    )
    await session.commit()
    case = await session.get(CivicCase, signal.case_id)
    return {
        "id": str(signal.id),
        "status": signal.status,
        "case_status": case.status if case is not None else None,
    }


# ---------------------------------------------------------------------------
# Phase 15: citizen follow-up signals on a report's resolution
# ---------------------------------------------------------------------------


@followup_router.post(
    "/{report_id}/resolution-followups",
    status_code=201,
    summary="Post a resolution follow-up signal (observed / still exists)",
)
async def create_followup(
    report_id: str,
    body: ResolutionFollowupCreate,
    request: Request,
    user: FollowupUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community",
        key=f"resolution_followup:{user.id}",
        limit=10,
        window_seconds=3600,
    )
    parsed = _parse_id(report_id, kind="report")
    # Visibility gate first (404 for private reports the user cannot see).
    await reports_service.get_report(session, parsed, viewer=user)
    from tk_api.reports.models import Report

    report = await session.get(Report, parsed)
    if report is None:
        raise ApiError("report not found", 404, "report_not_found")
    case = await session.scalar(select(CivicCase).where(CivicCase.report_id == parsed))
    if case is None:
        raise ApiError("no case exists for this report", 404, "case_not_found")
    settings = request.app.state.settings
    row = await community_service.create_followup(
        session,
        case=case,
        report=report,
        actor=user,
        signal=body.signal,
        observation=body.observation,
        confirm_threshold=settings.resolution_confirm_threshold,
        reopen_threshold=settings.resolution_reopen_threshold,
        request=request,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "case_id": str(row.case_id),
        "signal": row.signal,
        "observation": row.observation,
        "status": row.status,
        "created_at": row.created_at,
    }


@followup_router.get(
    "/{report_id}/resolution-followups",
    summary="Community follow-up summary on a report's resolution",
)
async def list_followups(
    report_id: str,
    session: DbSession,
    viewer: OptionalUser = None,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report")
    await reports_service.get_report(session, parsed, viewer=viewer)
    case = await session.scalar(select(CivicCase).where(CivicCase.report_id == parsed))
    if case is None:
        raise ApiError("no case exists for this report", 404, "case_not_found")
    return await community_service.list_followups(session, case=case, viewer=viewer)


@resolution_router.get("/{submission_id}", summary="Resolution detail")
async def get_resolution(
    submission_id: str,
    session: DbSession,
    user: CurrentUser,
    _perm: DepVerify,
) -> dict[str, Any]:
    from sqlalchemy import select

    from tk_api.resolution.models import ResolutionEvidence, ResolutionReview

    sub = await resolution_service.get_submission(
        session, _parse_id(submission_id, kind="submission")
    )
    evidence = (
        (
            await session.execute(
                select(ResolutionEvidence).where(
                    ResolutionEvidence.resolution_submission_id == sub.id
                )
            )
        )
        .scalars()
        .all()
    )
    reviews = (
        (
            await session.execute(
                select(ResolutionReview).where(ResolutionReview.resolution_submission_id == sub.id)
            )
        )
        .scalars()
        .all()
    )
    payload = _submission_payload(sub)
    payload["evidence"] = [
        {
            "id": str(e.id),
            "kind": e.kind,
            "notes": e.notes,
            "version_no": e.version_no,
            "document_kind": e.document_kind,
            "before_after": e.before_after,
            "captured_at": e.captured_at,
            "checksum": e.checksum,
            "visibility": e.visibility,
            "media_object_id": str(e.media_object_id) if e.media_object_id else None,
        }
        for e in evidence
    ]
    payload["reviews"] = [
        {
            "id": str(r.id),
            "decision": r.decision,
            "reason": r.reason,
            "reviewer_id": str(r.reviewer_id),
            "conflict_of_interest": r.conflict_of_interest,
            "ai_assessment": r.ai_assessment,
            "reviewed_at": r.reviewed_at,
        }
        for r in reviews
    ]
    return payload


@resolution_router.post("/{submission_id}/review", summary="Review a resolution")
async def review_resolution(
    submission_id: str,
    body: ResolutionReviewRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepReview,
) -> dict[str, Any]:
    sub = await resolution_service.get_submission(
        session, _parse_id(submission_id, kind="submission")
    )
    review = await resolution_service.review_resolution(
        session,
        sub,
        actor=user,
        decision=body.decision,
        reason=body.reason,
        ai_assessment=body.ai_assessment,
    )
    await session.commit()
    return {
        "id": str(review.id),
        "decision": review.decision,
        "submission_status": sub.status,
    }


@resolution_router.post(
    "/{submission_id}/evidence", status_code=201, summary="Add evidence version"
)
async def add_evidence(
    submission_id: str,
    body: ResolutionEvidenceAddRequest,
    session: DbSession,
    user: CurrentUser,
    _perm: DepSubmit,
) -> dict[str, Any]:
    sub = await resolution_service.get_submission(
        session, _parse_id(submission_id, kind="submission")
    )
    rows = await resolution_service.add_evidence_version(
        session, sub, actor=user, items=[item.model_dump() for item in body.items]
    )
    await session.commit()
    return {"count": len(rows), "version_no": rows[0].version_no if rows else None}
