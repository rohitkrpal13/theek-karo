"""Report lifecycle, drafts, evidence, verification, and timeline (PRD §7-§14)."""

from __future__ import annotations

import base64
import math
import secrets
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import jsonschema
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.auth.authorization import AuthorizationService
from tk_api.civic.models import Campaign, Category, IssueType
from tk_api.core.audit import audit
from tk_api.core.errors import ApiError
from tk_api.gis.service import suggest_boundary_id
from tk_api.media.models import MediaObject
from tk_api.media.service import complete_upload as media_complete_upload
from tk_api.media.service import request_upload as media_request_upload
from tk_api.media.storage import StorageAdapter
from tk_api.notifications.events import (
    queue_comment,
    queue_status_change,
    queue_verification,
)
from tk_api.reports.models import (
    Report,
    ReportComment,
    ReportDuplicate,
    ReportEvidence,
    ReportFollower,
    ReportStatusHistory,
    ReportVerification,
)
from tk_api.reports.state import (
    REPORT_STATUSES,
    record_system_transition,
    transition_report,
)
from tk_api.users.models import User

TRUST_CONFIRM_STEP = Decimal("0.15")
TRUST_REFUTE_STEP = Decimal("0.20")
TRUST_MAX = Decimal("1.0")
TRUST_MIN = Decimal("0.0")


class ReportError(ApiError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _new_ticket_no() -> str:
    date_part = datetime.now(UTC).strftime("%Y%m%d")
    return f"TK-{date_part}-{secrets.token_hex(3).upper()}"


def _validate_fields(form_schema: dict[str, Any], fields: dict[str, Any]) -> None:
    try:
        jsonschema.validate(instance=fields, schema=form_schema)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(p) for p in exc.path) or "<root>"
        raise ReportError(
            f"field validation failed at '{path}': {exc.message}",
            422,
            "field_validation_failed",
        ) from exc


def _encode_cursor(dt: datetime, uid: uuid.UUID) -> str:
    payload = f"{dt.isoformat()}|{uid}"
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(raw: str) -> tuple[datetime, uuid.UUID]:
    try:
        decoded = base64.urlsafe_b64decode(raw.encode()).decode()
        iso, uid_str = decoded.split("|", 1)
        return datetime.fromisoformat(iso), uuid.UUID(uid_str)
    except Exception as exc:
        raise ReportError("invalid cursor format", 422, "invalid_cursor") from exc


def _report_out(
    report: Report, evidence_list: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    acc = float(report.location_accuracy_m) if report.location_accuracy_m is not None else 15.0
    return {
        "id": str(report.id),
        "ticket_no": report.ticket_no,
        "category_id": str(report.category_id),
        "campaign_id": str(report.campaign_id) if report.campaign_id else None,
        "institution_id": str(report.institution_id) if report.institution_id else None,
        "issue_type_id": str(report.issue_type_id) if report.issue_type_id else None,
        "reporter_id": str(report.reporter_id),
        "title": report.title,
        "description": report.description,
        "location": report.location,
        "location_accuracy_m": acc,
        "coordinate_source": report.coordinate_source,
        "observed_at": report.observed_at.isoformat() if report.observed_at else None,
        "address_hint": report.address_hint,
        "boundary_id": str(report.boundary_id) if report.boundary_id else None,
        "status": report.status,
        "severity": report.severity,
        "visibility": report.visibility,
        "source": report.source,
        "priority": report.priority,
        "info_class": report.info_class,
        "trust_score": float(report.trust_score),
        "duplicate_of": str(report.duplicate_of) if report.duplicate_of else None,
        "merged_by_ai": report.merged_by_ai,
        "fields": report.fields or {},
        "evidence": evidence_list or [],
        "resolved_at": report.resolved_at.isoformat() if report.resolved_at else None,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


def can_view_report(report: Report, viewer: Any | None) -> bool:
    """Visibility gate for report detail (IDOR hardening, Phase 16).

    Public reports are world-readable; private reports are only visible to the
    reporter, staff (admin/moderator/super_admin), or roles carrying
    ``reports.read_private``. Returns False for everyone else (the router maps
    this to 404 so report IDs do not leak existence).
    """
    if report.visibility == "public":
        return True
    if viewer is None:
        return False
    if str(viewer.id) == str(report.reporter_id):
        return True
    roles = viewer.role_codes()
    if any(role in {"super_admin", "admin", "moderator"} for role in roles):
        return True
    perms = AuthorizationService.get_user_permissions(viewer)
    return "reports.read_private" in perms or "*" in perms


def _evidence_out(ev: ReportEvidence, media: MediaObject | None = None) -> dict[str, Any]:
    thumb_url = f"/api/v1/media/{ev.media_object_id}/thumbnail" if ev.media_object_id else None
    download_url = f"/api/v1/media/{ev.media_object_id}/download" if ev.media_object_id else ev.url
    return {
        "id": str(ev.id),
        "report_id": str(ev.report_id),
        "kind": ev.kind,
        "media_object_id": str(ev.media_object_id) if ev.media_object_id else None,
        "url": download_url,
        "thumbnail_url": thumb_url,
        "mime_type": media.mime_type if media else None,
        "size_bytes": media.size_bytes if media else None,
        "width": media.width if media else None,
        "height": media.height if media else None,
        "moderation_status": ev.moderation_status,
        "verification_status": ev.verification_status,
        "created_at": ev.created_at.isoformat(),
    }


# -----------------------------------------------------------------------------
# 1. Draft Management
# -----------------------------------------------------------------------------


async def create_draft(
    session: AsyncSession,
    *,
    reporter_id: uuid.UUID,
    category_slug: str | None = None,
    campaign_id: uuid.UUID | None = None,
    institution_id: uuid.UUID | None = None,
    issue_type_id: uuid.UUID | None = None,
    title: str | None = None,
    description: str | None = None,
    location: dict[str, Any] | None = None,
    location_accuracy_m: float | None = None,
    coordinate_source: str | None = None,
    observed_at: datetime | None = None,
    address_hint: str | None = None,
    severity: str | None = None,
    visibility: str = "public",
    fields: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    category_id = None
    if category_slug:
        cat = await session.scalar(select(Category).where(Category.slug == category_slug))
        if cat is not None:
            category_id = cat.id

    if category_id is None:
        first_cat = await session.scalar(select(Category).order_by(Category.slug).limit(1))
        if first_cat is None:
            raise ReportError("no category configured in system", 500, "category_missing")
        category_id = first_cat.id

    loc_dict = location or {"type": "Point", "coordinates": [75.7873, 26.9124]}
    acc = Decimal(str(location_accuracy_m)) if location_accuracy_m is not None else Decimal("15.0")

    report = Report(
        ticket_no=_new_ticket_no(),
        category_id=category_id,
        campaign_id=campaign_id,
        institution_id=institution_id,
        issue_type_id=issue_type_id,
        reporter_id=reporter_id,
        title=title or "Draft Report",
        description=description or "",
        location=loc_dict,
        location_accuracy_m=acc,
        coordinate_source=coordinate_source or "USER_SELECTED",
        observed_at=observed_at or _utcnow(),
        address_hint=address_hint,
        severity=severity or "medium",
        visibility=visibility,
        status="draft",
        info_class="CITIZEN_REPORT",
        fields=fields or {},
    )
    session.add(report)
    await session.flush()

    session.add(
        ReportStatusHistory(
            report_id=report.id,
            from_status=None,
            to_status="draft",
            actor_id=reporter_id,
            reason="Draft created",
        )
    )
    await audit(
        session,
        action="report.draft_create",
        entity_type="report",
        entity_id=report.id,
        actor_id=reporter_id,
        request=request,
    )
    await session.commit()
    return _report_out(report)


async def update_draft(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    changes: dict[str, Any],
    actor: User,
    request: Request | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, draft_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("draft not found", 404, "draft_not_found")
    if report.status != "draft":
        raise ReportError("cannot edit non-draft report as draft", 409, "not_a_draft")
    if report.reporter_id != actor.id and not actor.has_role("admin"):
        raise ReportError("forbidden: only report owner can edit draft", 403, "forbidden")

    if changes.get("category_slug"):
        cat_slug = str(changes["category_slug"])
        cat = await session.scalar(select(Category).where(Category.slug == cat_slug))
        if cat is not None:
            report.category_id = cat.id

    for key, val in changes.items():
        if key in ("category_slug",):
            continue
        if key == "location" and isinstance(val, dict):
            report.location = val
        elif hasattr(report, key) and val is not None:
            setattr(report, key, val)

    report.updated_at = _utcnow()
    await session.commit()
    return _report_out(report)


async def list_drafts(session: AsyncSession, *, user: User) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                select(Report)
                .where(
                    Report.reporter_id == user.id,
                    Report.status == "draft",
                    Report.deleted_at.is_(None),
                )
                .order_by(Report.updated_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_report_out(r) for r in rows]


async def delete_draft(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    user: User,
    request: Request | None = None,
) -> None:
    report = await session.get(Report, draft_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("draft not found", 404, "draft_not_found")
    if report.status != "draft":
        raise ReportError("only draft reports can be deleted directly", 409, "not_a_draft")
    if report.reporter_id != user.id and not user.has_role("admin"):
        raise ReportError("forbidden: only report owner can delete draft", 403, "forbidden")

    await session.execute(delete(ReportEvidence).where(ReportEvidence.report_id == report.id))
    await session.execute(
        delete(ReportStatusHistory).where(ReportStatusHistory.report_id == report.id)
    )
    await session.delete(report)
    await audit(
        session,
        action="report.draft_delete",
        entity_type="report",
        entity_id=draft_id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()


async def submit_draft(
    session: AsyncSession,
    draft_id: uuid.UUID,
    *,
    user: User,
    overrides: dict[str, Any] | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, draft_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("draft not found", 404, "draft_not_found")
    if report.status != "draft":
        raise ReportError("report is already submitted", 409, "already_submitted")
    if report.reporter_id != user.id and not user.has_role("admin"):
        raise ReportError("forbidden: only report owner can submit draft", 403, "forbidden")

    if overrides:
        for k, v in overrides.items():
            if v is not None and hasattr(report, k):
                setattr(report, k, v)

    # Validate category and schema
    category = await session.get(Category, report.category_id)
    if category is None:
        raise ReportError("category not found", 404, "category_not_found")
    if not category.is_active:
        raise ReportError("category is inactive", 409, "category_inactive")

    if len(report.title.strip()) < 5:
        raise ReportError("title must be at least 5 characters", 422, "title_too_short")
    if len(report.description.strip()) < 10:
        raise ReportError("description must be >= 10 characters", 422, "description_too_short")

    if category.form_schema:
        _validate_fields(category.form_schema, report.fields or {})

    # Boundary detection
    if report.boundary_id is None and isinstance(report.location, dict):
        coords = report.location.get("coordinates")
        if coords and len(coords) >= 2:
            report.boundary_id = await suggest_boundary_id(session, lon=coords[0], lat=coords[1])

    report.status = "submitted"
    report.updated_at = _utcnow()

    session.add(
        ReportStatusHistory(
            report_id=report.id,
            from_status="draft",
            to_status="submitted",
            actor_id=user.id,
            reason="Submitted from draft",
        )
    )
    await audit(
        session,
        action="report.submit",
        entity_type="report",
        entity_id=report.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return _report_out(report)


# -----------------------------------------------------------------------------
# 2. One-Shot Report Creation
# -----------------------------------------------------------------------------


async def submit_report(
    session: AsyncSession,
    *,
    category_slug: str,
    campaign_id: uuid.UUID | None = None,
    institution_id: uuid.UUID | None = None,
    issue_type_id: uuid.UUID | None = None,
    title: str,
    description: str,
    location: dict[str, Any],
    location_accuracy_m: float,
    coordinate_source: str | None = None,
    observed_at: datetime | None = None,
    address_hint: str | None = None,
    severity: str | None = "medium",
    visibility: str = "public",
    source: str | None = None,
    fields: dict[str, Any] | None = None,
    media_ids: list[uuid.UUID] | None = None,
    reporter_id: uuid.UUID,
    request: Request | None = None,
) -> dict[str, Any]:
    category = await session.scalar(select(Category).where(Category.slug == category_slug))
    if category is None:
        raise ReportError(f"unknown category: {category_slug}", 404, "category_not_found")
    if not category.is_active:
        raise ReportError(f"category is inactive: {category_slug}", 409, "category_inactive")

    if campaign_id is not None:
        campaign = await session.get(Campaign, campaign_id)
        if campaign is None:
            raise ReportError("campaign not found", 404, "campaign_not_found")
        if campaign.status == "closed":
            raise ReportError("campaign is closed", 409, "campaign_closed")
        if campaign.status not in ("active", "live", "planned"):
            msg = f"campaign is not active: {campaign.status}"
            raise ReportError(msg, 409, "campaign_inactive")
        if campaign.category_id != category.id:
            raise ReportError(
                "campaign does not belong to this category", 422, "campaign_category_mismatch"
            )

    if issue_type_id is not None:
        issue_type = await session.get(IssueType, issue_type_id)
        if issue_type is None or not issue_type.is_active:
            raise ReportError("issue type not found or inactive", 404, "issue_type_not_found")

    fields_dict = fields or {}
    if category.form_schema:
        _validate_fields(category.form_schema, fields_dict)

    coords = location.get("coordinates", [0, 0])
    boundary_id = await suggest_boundary_id(session, lon=coords[0], lat=coords[1])

    report = Report(
        ticket_no=_new_ticket_no(),
        category_id=category.id,
        campaign_id=campaign_id,
        institution_id=institution_id,
        issue_type_id=issue_type_id,
        reporter_id=reporter_id,
        title=title.strip(),
        description=description.strip(),
        location=location,
        location_accuracy_m=Decimal(str(location_accuracy_m)),
        coordinate_source=coordinate_source or "USER_SELECTED",
        observed_at=observed_at or _utcnow(),
        address_hint=address_hint,
        boundary_id=boundary_id,
        status="submitted",
        severity=severity or "medium",
        visibility=visibility,
        source=source,
        info_class="CITIZEN_REPORT",
        fields=fields_dict,
    )
    session.add(report)
    await session.flush()

    # Link staged media objects if provided
    evidence_items = []
    if media_ids:
        for mid in media_ids:
            media_obj = await session.get(MediaObject, mid)
            if media_obj is not None and media_obj.uploaded_by == reporter_id:
                kind = "video" if "video" in media_obj.mime_type else "image"
                ev = ReportEvidence(
                    report_id=report.id,
                    kind=kind,
                    media_object_id=media_obj.id,
                    uploaded_by=reporter_id,
                    moderation_status="approved" if media_obj.scan_status == "clean" else "pending",
                )
                session.add(ev)
                await session.flush()
                evidence_items.append(_evidence_out(ev, media_obj))

    session.add(
        ReportStatusHistory(
            report_id=report.id,
            from_status=None,
            to_status="submitted",
            actor_id=reporter_id,
            reason="Report submitted by citizen",
        )
    )
    await audit(
        session,
        action="report.create",
        entity_type="report",
        entity_id=report.id,
        actor_id=reporter_id,
        request=request,
    )
    # Phase 19 outbox (spec §57-§59): external consumers learn about the new
    # report in the same transaction as the report itself. Payload is
    # public-safe only — never reporter identity or private fields.
    from tk_api.integrations.webhooks import emit_outbox_event

    await emit_outbox_event(
        session,
        event="report.created",
        aggregate_type="report",
        aggregate_id=report.id,
        payload={
            "report_id": str(report.id),
            "ticket_no": report.ticket_no,
            "title": report.title[:200],
            "category_id": str(report.category_id),
            "institution_id": str(report.institution_id) if report.institution_id else None,
            "status": report.status,
            "severity": report.severity,
            "visibility": report.visibility,
        },
    )
    await session.commit()
    return _report_out(report, evidence_items)


# -----------------------------------------------------------------------------
# 3. Media Evidence Pipeline & Attachment
# -----------------------------------------------------------------------------


async def request_evidence_upload(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    settings: Any,
    storage: StorageAdapter,
    mime_type: str,
    size_bytes: int,
    kind: str,
    user: User,
    request: Request,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")
    is_owner = report.reporter_id == user.id
    if not is_owner and not user.has_role("admin") and not user.has_role("volunteer"):
        raise ReportError("forbidden: cannot attach media to this report", 403, "forbidden")

    return await media_request_upload(
        session,
        settings=settings,
        storage=storage,
        mime_type=mime_type,
        size_bytes=size_bytes,
        uploaded_by=user.id,
        request=request,
    )


async def complete_evidence_upload(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    media_id: uuid.UUID,
    settings: Any,
    storage: StorageAdapter,
    checksum_sha256: str | None = None,
    user: User,
    request: Request,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")
    is_owner = report.reporter_id == user.id
    if not is_owner and not user.has_role("admin") and not user.has_role("volunteer"):
        raise ReportError("forbidden", 403, "forbidden")

    media_out = await media_complete_upload(
        session,
        media_id=media_id,
        settings=settings,
        storage=storage,
        checksum_sha256=checksum_sha256,
        actor=user,
        request=request,
    )

    media_obj = await session.get(MediaObject, media_id)
    kind = "video" if media_obj and "video" in media_obj.mime_type else "image"

    evidence = ReportEvidence(
        report_id=report.id,
        kind=kind,
        media_object_id=media_id,
        uploaded_by=user.id,
        moderation_status="approved" if media_out.get("scan_status") == "clean" else "pending",
    )
    session.add(evidence)
    await session.commit()
    return _evidence_out(evidence, media_obj)


async def list_report_evidence(
    session: AsyncSession,
    report_id: uuid.UUID,
    viewer: Any | None = None,
) -> list[dict[str, Any]]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")
    if not can_view_report(report, viewer):
        raise ReportError("report not found", 404, "report_not_found")

    rows = (
        (
            await session.execute(
                select(ReportEvidence)
                .where(ReportEvidence.report_id == report_id)
                .order_by(ReportEvidence.created_at.asc())
            )
        )
        .scalars()
        .all()
    )

    items = []
    for ev in rows:
        m = await session.get(MediaObject, ev.media_object_id) if ev.media_object_id else None
        items.append(_evidence_out(ev, m))
    return items


async def delete_report_evidence(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    evidence_id: uuid.UUID,
    user: User,
    request: Request,
) -> None:
    ev = await session.get(ReportEvidence, evidence_id)
    if ev is None or ev.report_id != report_id:
        raise ReportError("evidence not found", 404, "evidence_not_found")
    if ev.uploaded_by != user.id and not user.has_role("admin"):
        raise ReportError("forbidden: cannot delete this evidence", 403, "forbidden")

    await session.delete(ev)
    await audit(
        session,
        action="report.evidence_delete",
        entity_type="report_evidence",
        entity_id=evidence_id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()


# -----------------------------------------------------------------------------
# 4. Verification Workflow
# -----------------------------------------------------------------------------


async def verify_report(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    kind: str,
    evidence: str | None = None,
    notes: str | None = None,
    location_independent: bool = False,
    verifier: User,
    request: Request | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")
    if report.reporter_id == verifier.id:
        raise ReportError(
            "reporter cannot verify own report", 403, "own_report_verification_forbidden"
        )
    if report.status in ("draft", "archived", "closed"):
        raise ReportError(f"cannot verify report in '{report.status}' state", 409, "invalid_state")

    existing = await session.scalar(
        select(ReportVerification).where(
            ReportVerification.report_id == report.id,
            ReportVerification.verifier_id == verifier.id,
        )
    )
    if existing is not None:
        raise ReportError("user already verified this report", 409, "duplicate_verification")

    row = ReportVerification(
        report_id=report.id,
        verifier_id=verifier.id,
        kind=kind,
        evidence=evidence or notes,
        location_independent=location_independent,
    )
    session.add(row)

    # Recalculate Trust Score & Auto-Promotion
    if kind == "confirm":
        report.trust_score = min(TRUST_MAX, report.trust_score + TRUST_CONFIRM_STEP)
    elif kind == "refute":
        report.trust_score = max(TRUST_MIN, report.trust_score - TRUST_REFUTE_STEP)

    promoted = False
    is_promotable = (
        kind == "confirm"
        and report.trust_score >= Decimal("0.30")
        and report.status in ("submitted", "under_verification")
    )
    if is_promotable:
        await record_system_transition(
            session,
            report,
            to_status="verified",
            reason=f"Trust score threshold reached ({report.trust_score})",
            actor_id=verifier.id,
        )
        promoted = True
    elif kind == "needs_information" and verifier.has_role("volunteer"):
        await record_system_transition(
            session,
            report,
            to_status="needs_information",
            reason=notes or "Additional verification information requested",
            actor_id=verifier.id,
        )
        promoted = True
    elif report.status == "submitted":
        await record_system_transition(
            session,
            report,
            to_status="under_verification",
            reason="Verification in progress",
            actor_id=verifier.id,
        )
        promoted = True

    await queue_verification(session, report=report, actor_id=verifier.id)
    await audit(
        session,
        action="report.verify",
        entity_type="report",
        entity_id=report.id,
        actor_id=verifier.id,
        after={"kind": kind, "trust_score": float(report.trust_score), "promoted": promoted},
        request=request,
    )
    await session.commit()
    return {
        "id": str(row.id),
        "report_id": str(row.report_id),
        "verifier_id": str(row.verifier_id),
        "kind": row.kind,
        "evidence": row.evidence,
        "location_independent": row.location_independent,
        "trust_score": float(report.trust_score),
        "status": report.status,
        "created_at": row.created_at.isoformat(),
    }


async def list_verifications(
    session: AsyncSession,
    report_id: uuid.UUID,
) -> dict[str, Any]:
    rows = (
        (
            await session.execute(
                select(ReportVerification)
                .where(ReportVerification.report_id == report_id)
                .order_by(ReportVerification.created_at.desc())
            )
        )
        .scalars()
        .all()
    )

    confirm_count = sum(1 for r in rows if r.kind == "confirm")
    refute_count = sum(1 for r in rows if r.kind == "refute")

    return {
        "items": [
            {
                "id": str(r.id),
                "verifier_id": str(r.verifier_id),
                "kind": r.kind,
                "evidence": r.evidence,
                "location_independent": r.location_independent,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ],
        "confirmations_count": confirm_count,
        "refutations_count": refute_count,
        "total_count": len(rows),
    }


# -----------------------------------------------------------------------------
# 5. Duplicate Detection & Linking Foundation
# -----------------------------------------------------------------------------


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def detect_duplicates(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    radius_km: float = 0.5,
) -> list[dict[str, Any]]:
    report = await session.get(Report, report_id)
    if report is None:
        return []

    coords = report.location.get("coordinates") if isinstance(report.location, dict) else None
    if not coords or len(coords) < 2:
        return []

    r_lon, r_lat = float(coords[0]), float(coords[1])

    candidates = (
        (
            await session.execute(
                select(Report)
                .where(
                    Report.id != report.id,
                    Report.category_id == report.category_id,
                    Report.status.notin_(["draft", "rejected", "closed"]),
                    Report.deleted_at.is_(None),
                )
                .order_by(Report.created_at.desc())
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    matches = []
    for cand in candidates:
        cand_coords = cand.location.get("coordinates") if isinstance(cand.location, dict) else None
        if not cand_coords or len(cand_coords) < 2:
            continue
        dist = _haversine_distance_km(r_lat, r_lon, float(cand_coords[1]), float(cand_coords[0]))
        if dist <= radius_km:
            score = max(0.5, min(0.95, round(1.0 - (dist / radius_km) * 0.5, 2)))
            matches.append(
                {
                    "candidate_report_id": str(cand.id),
                    "candidate_ticket_no": cand.ticket_no,
                    "candidate_title": cand.title,
                    "similarity_score": score,
                    "confidence": "high" if score > 0.8 else "medium",
                    "status": "possible",
                    "suggested_by": "heuristic_geo",
                }
            )
    return matches


async def link_duplicate(
    session: AsyncSession,
    *,
    report_id: uuid.UUID,
    candidate_report_id: uuid.UUID,
    status: str,
    user: User,
    request: Request | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    cand = await session.get(Report, candidate_report_id)
    if report is None or cand is None:
        raise ReportError("one or both reports not found", 404, "report_not_found")

    dup = ReportDuplicate(
        report_id=report.id,
        candidate_report_id=cand.id,
        similarity_score=Decimal("0.85"),
        confidence="high",
        status=status,
        suggested_by="user",
        decided_by=user.id,
        decided_at=_utcnow(),
    )
    session.add(dup)

    if status == "confirmed":
        report.duplicate_of = cand.id

    await audit(
        session,
        action="report.duplicate_link",
        entity_type="report_duplicate",
        entity_id=dup.id,
        actor_id=user.id,
        request=request,
    )
    await session.commit()
    return {
        "id": str(dup.id),
        "report_id": str(report.id),
        "candidate_report_id": str(cand.id),
        "status": dup.status,
    }


# -----------------------------------------------------------------------------
# 6. Report Querying, Details & Timeline
# -----------------------------------------------------------------------------


async def get_report(
    session: AsyncSession, report_id: uuid.UUID, viewer: Any | None = None
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")
    if not can_view_report(report, viewer):
        # 404 (not 403) so private report IDs do not leak existence
        raise ReportError("report not found", 404, "report_not_found")

    evidence_items = await list_report_evidence(session, report.id, viewer=viewer)

    verifications = (
        (
            await session.execute(
                select(ReportVerification).where(ReportVerification.report_id == report_id)
            )
        )
        .scalars()
        .all()
    )
    confirm_count = sum(1 for v in verifications if v.kind == "confirm")
    refute_count = sum(1 for v in verifications if v.kind == "refute")

    verifications_out = [
        {
            "id": str(v.id),
            "verifier_id": str(v.verifier_id),
            "kind": v.kind,
            "evidence": v.evidence,
            "location_independent": v.location_independent,
            "created_at": v.created_at.isoformat(),
        }
        for v in verifications
    ]

    timeline_entries = await session.execute(
        select(ReportStatusHistory)
        .where(ReportStatusHistory.report_id == report_id)
        .order_by(ReportStatusHistory.created_at.asc())
    )
    timeline_items = [
        {
            "id": str(h.id),
            "report_id": str(h.report_id),
            "from_status": h.from_status,
            "to_status": h.to_status,
            "actor_id": str(h.actor_id) if h.actor_id else None,
            "reason": h.reason,
            "created_at": h.created_at.isoformat(),
        }
        for h in timeline_entries.scalars()
    ]

    out = _report_out(report, evidence_items)
    out["verifications"] = verifications_out
    out["verifications_count"] = len(verifications)
    out["confirmations_count"] = confirm_count
    out["refutations_count"] = refute_count
    out["timeline"] = timeline_items
    return out


async def list_reports(
    session: AsyncSession,
    *,
    category_slug: str | None = None,
    campaign_id: uuid.UUID | None = None,
    institution_id: uuid.UUID | None = None,
    issue_type_id: uuid.UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    visibility: str | None = "public",
    boundary_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    if status is not None and status not in REPORT_STATUSES:
        raise ReportError(f"invalid report status filter: '{status}'", 422, "invalid_status")

    stmt = select(Report).where(Report.deleted_at.is_(None))

    if category_slug:
        cat = await session.scalar(select(Category).where(Category.slug == category_slug))
        if cat is None:
            raise ReportError(f"category not found: {category_slug}", 404, "category_not_found")
        stmt = stmt.where(Report.category_id == cat.id)

    if campaign_id:
        stmt = stmt.where(Report.campaign_id == campaign_id)
    if institution_id:
        stmt = stmt.where(Report.institution_id == institution_id)
    if issue_type_id:
        stmt = stmt.where(Report.issue_type_id == issue_type_id)
    stmt = stmt.where(Report.status == status) if status else stmt.where(Report.status != "draft")
    if severity:
        stmt = stmt.where(Report.severity == severity)
    if visibility:
        stmt = stmt.where(Report.visibility == visibility)
    if boundary_id:
        stmt = stmt.where(Report.boundary_id == boundary_id)

    if cursor:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Report.created_at < cursor_dt)
            | ((Report.created_at == cursor_dt) & (Report.id < cursor_id))
        )

    stmt = stmt.order_by(Report.created_at.desc(), Report.id.desc()).limit(limit + 1)
    rows = list((await session.execute(stmt)).scalars().all())

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = _encode_cursor(last.created_at, last.id)

    return {
        "items": [_report_out(r) for r in items],
        "next_cursor": next_cursor,
        "total_count": len(items),
    }


async def update_fields(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    changes: dict[str, Any],
    actor: User,
    request: Request | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")
    if report.reporter_id != actor.id and not actor.has_role("admin"):
        raise ReportError("forbidden: only report owner can edit fields", 403, "forbidden")
    if report.status not in ("draft", "submitted", "needs_information"):
        raise ReportError(f"fields are locked in status: {report.status}", 409, "fields_locked")

    for k, v in changes.items():
        if v is not None and hasattr(report, k):
            setattr(report, k, v)

    report.updated_at = _utcnow()
    await audit(
        session,
        action="report.fields_update",
        entity_type="report",
        entity_id=report.id,
        actor_id=actor.id,
        request=request,
    )
    await session.commit()
    return _report_out(report)


async def transition(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    to_status: str,
    reason: str | None,
    actor: User,
    request: Request | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")

    await transition_report(session, report, to_status=to_status, reason=reason, actor=actor)
    await queue_status_change(session, report=report, actor_id=actor.id, to_status=to_status)
    await audit(
        session,
        action="report.transition",
        entity_type="report",
        entity_id=report.id,
        actor_id=actor.id,
        after={"to_status": to_status, "reason": reason},
        request=request,
    )
    await session.commit()
    return _report_out(report)


# -----------------------------------------------------------------------------
# 7. Comments & Following
# -----------------------------------------------------------------------------


async def add_comment(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    body: str,
    parent_id: uuid.UUID | None = None,
    author: User,
    mention_usernames: list[str] | None = None,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")

    if parent_id is not None:
        parent = await session.get(ReportComment, parent_id)
        if parent is None or parent.report_id != report.id:
            raise ReportError("parent comment not found on this report", 404, "comment_not_found")
        if parent.parent_id is not None:
            raise ReportError(
                "comments are limited to 2 levels (a reply has no replies)",
                422,
                "max_comment_depth",
            )

    row = ReportComment(
        report_id=report.id,
        author_id=author.id,
        parent_id=parent_id,
        body=body.strip(),
    )
    session.add(row)
    await queue_comment(session, report=report, actor_id=author.id)
    if parent_id is not None and parent is not None:
        from tk_api.notifications.events import queue_reply

        await queue_reply(session, report=report, parent=parent, actor_id=author.id)
    if mention_usernames:
        from tk_api.notifications.events import queue_mention
        from tk_api.users.models import User as TkUser

        mentioned = (
            (
                await session.execute(
                    select(TkUser.id).where(
                        TkUser.username.in_([u.strip() for u in mention_usernames if u.strip()]),
                        TkUser.status == "active",
                    )
                )
            )
            .scalars()
            .all()
        )
        await queue_mention(
            session, report=report, mentionee_ids=list(mentioned), actor_id=author.id
        )
    await session.commit()
    return {
        "id": str(row.id),
        "report_id": str(row.report_id),
        "author_id": str(row.author_id),
        "author_name": author.display_name or "Citizen",
        "parent_id": str(row.parent_id) if row.parent_id else None,
        "body": row.body,
        "created_at": row.created_at.isoformat(),
    }


async def list_comments(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            select(ReportComment, User)
            .join(User, ReportComment.author_id == User.id)
            .where(ReportComment.report_id == report_id)
            .order_by(ReportComment.created_at.asc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "id": str(c.id),
            "report_id": str(c.report_id),
            "author_id": str(c.author_id),
            "author_name": u.display_name or "Citizen",
            "parent_id": str(c.parent_id) if c.parent_id else None,
            "body": c.body,
            "created_at": c.created_at.isoformat(),
        }
        for c, u in rows
    ]


async def follow_report(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    notify_level: str,
    user: User,
) -> dict[str, Any]:
    report = await session.get(Report, report_id)
    if report is None or report.deleted_at is not None:
        raise ReportError("report not found", 404, "report_not_found")

    existing = await session.scalar(
        select(ReportFollower).where(
            ReportFollower.report_id == report.id,
            ReportFollower.user_id == user.id,
        )
    )
    if existing is None:
        session.add(ReportFollower(report_id=report.id, user_id=user.id, notify_level=notify_level))
    else:
        existing.notify_level = notify_level

    await session.commit()
    return {"status": "following", "notify_level": notify_level}


async def unfollow_report(
    session: AsyncSession,
    report_id: uuid.UUID,
    *,
    user: User,
) -> None:
    existing = await session.scalar(
        select(ReportFollower).where(
            ReportFollower.report_id == report_id,
            ReportFollower.user_id == user.id,
        )
    )
    if existing is None:
        raise ReportError("not following this report", 404, "follower_not_found")
    await session.delete(existing)
    await session.commit()
