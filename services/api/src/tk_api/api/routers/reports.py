"""Report lifecycle, drafts, evidence, verification, duplicates (PRD §7-§14)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from tk_api.ai import analysis as ai_analysis
from tk_api.ai import service as ai_service
from tk_api.api.deps import DbSession, OptionalUser, require_active
from tk_api.core.db import create_session_factory
from tk_api.core.errors import ApiError
from tk_api.core.idempotency import IDEMPOTENCY_TTL_SECONDS, IdempotencyRecord
from tk_api.core.logging import log_extra
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.reports import service as reports_service
from tk_api.reports.schemas import (
    AiIntakeSuggestRequest,
    CommentCreate,
    DraftCreate,
    DraftSubmitRequest,
    DraftUpdate,
    DuplicateLinkRequest,
    FollowRequest,
    ReportCreate,
    ReportEvidenceCompleteRequest,
    ReportEvidenceUploadRequest,
    ReportFieldsUpdate,
    TransitionRequest,
    VerificationCreate,
)
from tk_api.reports.state import timeline

logger = logging.getLogger("tk_api.reports")

_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()

reports_router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

ReporterUser = Annotated[Any, Depends(require_active())]


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


async def _apply_idempotency(request: Request, user: Any) -> tuple[str | None, Any | None]:
    header = request.headers.get("idempotency-key")
    if header is None:
        return None, None
    try:
        key_id = uuid.UUID(header)
    except ValueError as exc:
        raise ApiError("Idempotency-Key must be a UUID", 422, "invalid_idempotency_key") from exc
    key = f"reports:{user.id}:{key_id}"
    store = request.app.state.idempotency_store
    cached = await store.get(key)
    if cached is not None:
        return key, cached
    return key, None


async def _schedule_analysis(request: Request, report_id: uuid.UUID) -> None:
    settings = request.app.state.settings
    if settings.celery_enabled:
        try:
            from tk_api.worker import celery_app as worker_app

            worker_app.send_task("tk_worker.analyze_report", args=[str(report_id)])
            return
        except Exception:
            logger.warning("celery enqueue failed; falling back to inline analysis")

    engine = request.app.state.engine
    gateway = request.app.state.ai_gateway
    threshold = settings.ai_dedup_similarity_threshold
    min_age = settings.ai_dedup_min_report_age_days

    async def job() -> None:
        try:
            factory = create_session_factory(engine)
            async with factory() as session:
                await ai_service.process_report(
                    session,
                    report_id=report_id,
                    gateway=gateway,
                    threshold=threshold,
                    min_report_age_days=min_age,
                )
        except Exception:
            logger.error("auto analysis failed", extra=log_extra(report_id=str(report_id)))

    task = asyncio.create_task(job())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


# -----------------------------------------------------------------------------
# 1. Draft Endpoints
# -----------------------------------------------------------------------------


@reports_router.post("/drafts", status_code=201, summary="Create a draft report")
async def create_draft(
    body: DraftCreate,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="reports", key=f"draft:{client_ip(request)}", limit=30, window_seconds=60
    )
    return await reports_service.create_draft(
        session,
        reporter_id=user.id,
        category_slug=body.category_slug,
        campaign_id=body.campaign_id,
        institution_id=body.institution_id,
        issue_type_id=body.issue_type_id,
        title=body.title,
        description=body.description,
        location=body.location.model_dump() if body.location else None,
        location_accuracy_m=body.location_accuracy_m,
        coordinate_source=body.coordinate_source,
        observed_at=body.observed_at,
        address_hint=body.address_hint,
        severity=body.severity,
        visibility=body.visibility,
        fields=body.fields,
        request=request,
    )


@reports_router.get("/drafts", summary="List user's own draft reports")
async def list_drafts(
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    items = await reports_service.list_drafts(session, user=user)
    return {"items": items}


@reports_router.get("/drafts/{draft_id}", summary="Get draft report detail")
async def get_draft(
    draft_id: str,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(draft_id, kind="draft", error_kind="invalid_draft_id")
    report = await reports_service.get_report(session, parsed, viewer=user)
    if report["reporter_id"] != str(user.id) and not user.has_role("admin"):
        raise ApiError("forbidden: only draft owner can view draft", 403, "forbidden")
    return report


@reports_router.patch("/drafts/{draft_id}", summary="Update draft report fields")
async def update_draft(
    draft_id: str,
    body: DraftUpdate,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(draft_id, kind="draft", error_kind="invalid_draft_id")
    changes = body.model_dump(exclude_unset=True)
    if "location" in changes and changes["location"] is not None:
        changes["location"] = body.location.model_dump() if body.location else None
    return await reports_service.update_draft(
        session, parsed, changes=changes, actor=user, request=request
    )


@reports_router.delete("/drafts/{draft_id}", status_code=204, summary="Delete draft report")
async def delete_draft(
    draft_id: str,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> None:
    parsed = _parse_id(draft_id, kind="draft", error_kind="invalid_draft_id")
    await reports_service.delete_draft(session, parsed, user=user, request=request)


@reports_router.post("/drafts/{draft_id}/submit", summary="Submit a draft report")
async def submit_draft(
    draft_id: str,
    body: DraftSubmitRequest,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="reports", key=f"submit:{client_ip(request)}", limit=20, window_seconds=60
    )
    parsed = _parse_id(draft_id, kind="draft", error_kind="invalid_draft_id")
    overrides = body.model_dump(exclude_unset=True)
    result = await reports_service.submit_draft(
        session, parsed, user=user, overrides=overrides, request=request
    )
    if request.app.state.settings.ai_auto_analysis:
        await _schedule_analysis(request, parsed)
    return result


# -----------------------------------------------------------------------------
# 2. Main Report Creation & Querying
# -----------------------------------------------------------------------------


@reports_router.post("", status_code=201, summary="Submit a report directly (idempotent)")
async def create_report(
    body: ReportCreate,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> Any:
    await rate_limit(
        request, bucket="reports", key=f"write:{client_ip(request)}", limit=30, window_seconds=60
    )
    idem_key, cached = await _apply_idempotency(request, user)
    if cached is not None:
        return JSONResponse(status_code=200, content=jsonable_encoder(cached.payload))

    result = await reports_service.submit_report(
        session,
        category_slug=body.category_slug,
        campaign_id=body.campaign_id,
        institution_id=body.institution_id,
        issue_type_id=body.issue_type_id,
        title=body.title,
        description=body.description,
        location=body.location.model_dump(),
        location_accuracy_m=body.location_accuracy_m,
        coordinate_source=body.coordinate_source,
        observed_at=body.observed_at,
        address_hint=body.address_hint,
        severity=body.severity,
        visibility=body.visibility,
        source=body.source,
        fields=body.fields,
        media_ids=body.media_ids,
        reporter_id=user.id,
        request=request,
    )
    if idem_key is not None:
        await request.app.state.idempotency_store.put(
            idem_key, IdempotencyRecord(201, result), IDEMPOTENCY_TTL_SECONDS
        )
    if request.app.state.settings.ai_auto_analysis:
        await _schedule_analysis(request, uuid.UUID(result["id"]))
    return result


@reports_router.get("", summary="List reports with category/status/severity/geo filters")
async def list_reports(
    request: Request,
    session: DbSession,
    category_slug: str | None = None,
    campaign_id: str | None = None,
    institution_id: uuid.UUID | None = None,
    issue_type_id: uuid.UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    visibility: str | None = None,
    boundary_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="reports_read",
        key=f"list:{client_ip(request)}",
        limit=120,
        window_seconds=60,
    )
    campaign_uuid = (
        _parse_id(campaign_id, kind="campaign", error_kind="invalid_campaign_id")
        if campaign_id is not None
        else None
    )
    boundary_uuid = (
        _parse_id(boundary_id, kind="boundary", error_kind="invalid_boundary_id")
        if boundary_id is not None
        else None
    )
    return await reports_service.list_reports(
        session,
        category_slug=category_slug,
        campaign_id=campaign_uuid,
        institution_id=institution_id,
        issue_type_id=issue_type_id,
        status=status,
        severity=severity,
        visibility=visibility,
        boundary_id=boundary_uuid,
        cursor=cursor,
        limit=limit,
    )


@reports_router.get("/{report_id}", summary="Report detail incl. timeline and verifications")
async def get_report(
    report_id: str,
    request: Request,
    session: DbSession,
    viewer: OptionalUser = None,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="reports_read",
        key=f"detail:{client_ip(request)}",
        limit=120,
        window_seconds=60,
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.get_report(session, parsed, viewer=viewer)


@reports_router.patch("/{report_id}/fields", summary="Edit fields while draft/submitted")
async def update_fields(
    report_id: str,
    body: ReportFieldsUpdate,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise ApiError("no fields to update", 422, "empty_update")
    return await reports_service.update_fields(
        session, parsed, changes=changes, actor=user, request=request
    )


# -----------------------------------------------------------------------------
# 3. Media Evidence Endpoints
# -----------------------------------------------------------------------------


@reports_router.post("/{report_id}/media/upload-url", summary="Request pre-signed upload slot")
async def request_media_upload_slot(
    report_id: str,
    body: ReportEvidenceUploadRequest,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="media", key=f"upload:{client_ip(request)}", limit=20, window_seconds=60
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    storage = request.app.state.storage
    settings = request.app.state.settings
    return await reports_service.request_evidence_upload(
        session,
        report_id=parsed,
        settings=settings,
        storage=storage,
        mime_type=body.mime_type,
        size_bytes=body.size_bytes,
        kind=body.kind,
        user=user,
        request=request,
    )


@reports_router.post("/{report_id}/media/complete", summary="Complete evidence upload")
async def complete_media_upload_slot(
    report_id: str,
    body: ReportEvidenceCompleteRequest,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    storage = request.app.state.storage
    settings = request.app.state.settings
    return await reports_service.complete_evidence_upload(
        session,
        report_id=parsed,
        media_id=body.media_id,
        settings=settings,
        storage=storage,
        checksum_sha256=body.checksum_sha256,
        user=user,
        request=request,
    )


@reports_router.get("/{report_id}/media", summary="List media evidence items attached to report")
async def list_media_evidence(
    report_id: str,
    session: DbSession,
    viewer: OptionalUser = None,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    items = await reports_service.list_report_evidence(session, parsed, viewer=viewer)
    return {"items": items}


@reports_router.delete(
    "/{report_id}/media/{evidence_id}", status_code=204, summary="Delete evidence item"
)
async def delete_media_evidence(
    report_id: str,
    evidence_id: str,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> None:
    parsed_report = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    parsed_ev = _parse_id(evidence_id, kind="evidence", error_kind="invalid_evidence_id")
    await reports_service.delete_report_evidence(
        session, report_id=parsed_report, evidence_id=parsed_ev, user=user, request=request
    )


# -----------------------------------------------------------------------------
# 4. Verification Endpoints
# -----------------------------------------------------------------------------


@reports_router.post(
    "/{report_id}/verifications", status_code=201, summary="Submit verification decision"
)
async def add_verification(
    report_id: str,
    body: VerificationCreate,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="reports",
        key=f"verify:{client_ip(request)}",
        limit=20,
        window_seconds=60,
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.verify_report(
        session,
        parsed,
        kind=body.kind,
        evidence=body.evidence,
        notes=body.notes,
        location_independent=body.location_independent,
        verifier=user,
        request=request,
    )


@reports_router.get("/{report_id}/verifications", summary="List community verification decisions")
async def list_verifications(
    report_id: str,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.list_verifications(session, parsed)


# -----------------------------------------------------------------------------
# 5. Duplicates & AI Suggestions
# -----------------------------------------------------------------------------


@reports_router.get("/{report_id}/duplicates", summary="List candidate duplicates for report")
async def list_duplicate_candidates(
    report_id: str,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    items = await reports_service.detect_duplicates(session, parsed)
    return {"items": items}


@reports_router.post("/{report_id}/duplicates/link", summary="Link or confirm duplicate report")
async def link_duplicate_report(
    report_id: str,
    body: DuplicateLinkRequest,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.link_duplicate(
        session,
        report_id=parsed,
        candidate_report_id=body.candidate_report_id,
        status=body.status,
        user=user,
        request=request,
    )


@reports_router.post("/ai/suggest", summary="Get AI-assisted suggestions for category, title")
async def ai_suggest_intake(
    body: AiIntakeSuggestRequest,
    session: DbSession,
    request: Request,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai", key=f"suggest:{client_ip(request)}", limit=30, window_seconds=60
    )
    gateway = getattr(request.app.state, "ai_gateway", None)
    return await ai_service.suggest_intake(
        session,
        description=body.description,
        title=body.title,
        category_slug=body.category_slug,
        location=body.location.model_dump() if body.location else None,
        gateway=gateway,
    )


# -----------------------------------------------------------------------------
# 6. Comments, Follow & Lifecycle Transitions
# -----------------------------------------------------------------------------


@reports_router.post("/{report_id}/comments", status_code=201, summary="Add collaboration comment")
async def add_comment(
    report_id: str,
    body: CommentCreate,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request,
        bucket="community",
        key=f"comment:{client_ip(request)}",
        limit=20,
        window_seconds=60,
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    parent = (
        _parse_id(body.parent_id, kind="comment", error_kind="invalid_comment_id")
        if body.parent_id
        else None
    )
    return await reports_service.add_comment(
        session,
        parsed,
        body=body.body,
        parent_id=parent,
        author=user,
        mention_usernames=body.mentions,
    )


@reports_router.get("/{report_id}/comments", summary="List report comments")
async def list_comments(
    report_id: str,
    request: Request,
    session: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    await rate_limit(
        request,
        bucket="comments_read",
        key=f"list:{client_ip(request)}",
        limit=120,
        window_seconds=60,
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.list_comments(session, parsed, limit=limit)


@reports_router.post("/{report_id}/follow", status_code=201, summary="Follow a report")
async def follow_report(
    report_id: str,
    body: FollowRequest,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.follow_report(
        session, parsed, notify_level=body.notify_level, user=user
    )


@reports_router.delete("/{report_id}/follow", status_code=204, summary="Unfollow a report")
async def unfollow_report(
    report_id: str,
    user: ReporterUser,
    session: DbSession,
) -> None:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    await reports_service.unfollow_report(session, parsed, user=user)


@reports_router.post("/{report_id}/transition", summary="Status transition (state machine)")
async def transition_report(
    report_id: str,
    body: TransitionRequest,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await reports_service.transition(
        session,
        parsed,
        to_status=body.to_status,
        reason=body.reason,
        actor=user,
        request=request,
    )


@reports_router.get("/{report_id}/timeline", summary="Append-only status history")
async def report_timeline(
    report_id: str,
    session: DbSession,
    viewer: OptionalUser = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    await reports_service.get_report(session, parsed, viewer=viewer)
    return {
        "items": await timeline(session, parsed, limit=limit),
        "next_cursor": None,
    }


@reports_router.get("/{report_id}/analysis", summary="T4 analysis envelope for a report")
async def report_analysis(
    report_id: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    return await ai_analysis.annotation_out(session, parsed)


@reports_router.post(
    "/{report_id}/analysis/refresh", summary="Re-run analysis (versioned, keeps the old)"
)
async def refresh_analysis(
    report_id: str,
    request: Request,
    user: ReporterUser,
    session: DbSession,
) -> dict[str, Any]:
    await rate_limit(
        request, bucket="ai", key=f"analyze:{client_ip(request)}", limit=10, window_seconds=60
    )
    parsed = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    report = await reports_service.get_report(session, parsed, viewer=user)
    if report["reporter_id"] != str(user.id) and not user.has_role("admin"):
        raise ApiError("only the reporter or an admin may refresh analysis", 403, "forbidden")
    gateway = request.app.state.ai_gateway
    settings = request.app.state.settings
    return await ai_service.process_report(
        session,
        report_id=parsed,
        gateway=gateway,
        threshold=settings.ai_dedup_similarity_threshold,
        min_report_age_days=settings.ai_dedup_min_report_age_days,
        request=request,
        actor_id=user.id,
        refresh=True,
    )
