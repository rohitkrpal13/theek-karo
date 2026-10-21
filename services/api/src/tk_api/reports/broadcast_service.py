"""Social broadcast orchestration service (PRD §8, §14).

Handles durable broadcast creation, idempotency, state transitions, re-validation,
and execution across Celery tasks or in-process fallbacks.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.core.audit import audit
from tk_api.core.config import Settings
from tk_api.core.errors import ApiError
from tk_api.core.logging import log_extra
from tk_api.reports.models import Report, SocialBroadcast
from tk_api.reports.publisher import XPublisherProtocol, get_social_publisher
from tk_api.reports.social import build_social_post_package

logger = logging.getLogger("tk_api.social_broadcast")


async def create_broadcast_request(
    session: AsyncSession,
    *,
    report: dict[str, Any],
    requester_id: uuid.UUID,
    network: str = "x",
    tone: str = "urgent",
    idempotency_key: str | None = None,
    settings: Settings,
    request: Any = None,
) -> SocialBroadcast:
    """Creates a durable SocialBroadcast record with idempotency and validation."""
    report_id = uuid.UUID(str(report["id"]))

    # 1. Check idempotency: if an idempotency_key was supplied, look up existing record
    if idempotency_key:
        existing = await session.scalar(
            select(SocialBroadcast).where(
                SocialBroadcast.report_id == report_id,
                SocialBroadcast.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing

    # 2. Check for active existing broadcast (already published, in-flight, or outcome uncertain)
    active = await session.scalar(
        select(SocialBroadcast)
        .where(
            SocialBroadcast.report_id == report_id,
            SocialBroadcast.status.in_(["queued", "processing", "published", "outcome_unknown"]),
        )
        .order_by(SocialBroadcast.created_at.desc())
        .limit(1)
    )
    if active:
        return active

    # 3. Build snapshot of the post text
    location_coords: list[float] | None = None
    loc = report.get("location")
    if isinstance(loc, dict) and loc.get("type") == "Point" and "coordinates" in loc:
        coords = loc["coordinates"]
        if isinstance(coords, list):
            location_coords = [float(c) for c in coords]

    evidence_urls: list[str] = [
        ev["url"] for ev in report.get("evidence", []) if isinstance(ev, dict) and ev.get("url")
    ]

    post_pkg = build_social_post_package(
        report_id=str(report["id"]),
        ticket_no=report["ticket_no"],
        title=report["title"],
        description=report["description"],
        category_slug=report.get("category_slug"),
        severity=report.get("severity"),
        address_hint=report.get("address_hint"),
        location_coords=location_coords,
        tone=tone,  # type: ignore[arg-type]
        evidence_urls=evidence_urls,
        base_web_url=settings.app_base_url,
    )
    post_text = post_pkg["x_post"]["text"]

    # 4. Determine initial status:
    # If mode is disabled, mark disabled immediately.
    # If mode is live but user-context credentials are missing, mark not_configured.
    if settings.social_broadcast_mode == "disabled":
        init_status = "disabled"
        err = "Civic bot social broadcasting is currently disabled by administrator configuration."
    elif settings.social_broadcast_mode == "live" and not (
        (
            settings.twitter_api_key
            and settings.twitter_api_secret
            and settings.twitter_access_token
            and settings.twitter_access_token_secret
        )
        or (settings.twitter_access_token and not settings.twitter_bearer_token)
    ):
        init_status = "not_configured"
        err = "X API user-context credentials are not configured in environment."
    elif settings.social_broadcast_mode == "simulated" and not settings.celery_enabled:
        init_status = "simulated"
        err = None
    else:
        init_status = "queued"
        err = None

    broadcast = SocialBroadcast(
        report_id=report_id,
        requested_by=requester_id,
        network=network,
        tone=tone,
        status=init_status,
        post_text=post_text,
        idempotency_key=idempotency_key,
        last_error=err,
        max_attempts=settings.social_broadcast_max_attempts,
    )
    session.add(broadcast)
    try:
        await session.flush()
        # 5. Audit log request
        await audit(
            session,
            action="report.social_broadcast_requested",
            entity_type="report",
            entity_id=report_id,
            actor_id=requester_id,
            request=request,
            after={
                "broadcast_id": str(broadcast.id),
                "network": network,
                "tone": tone,
                "severity": report.get("severity"),
                "ticket_no": report["ticket_no"],
                "status": init_status,
            },
        )
        await session.commit()
        await session.refresh(broadcast)
        return broadcast
    except IntegrityError:
        await session.rollback()
        # Concurrency race: another request inserted an active or identical idempotency record
        if idempotency_key:
            existing = await session.scalar(
                select(SocialBroadcast).where(
                    SocialBroadcast.report_id == report_id,
                    SocialBroadcast.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing

        active = await session.scalar(
            select(SocialBroadcast)
            .where(
                SocialBroadcast.report_id == report_id,
                SocialBroadcast.status.in_(
                    ["queued", "processing", "published", "outcome_unknown"]
                ),
            )
            .order_by(SocialBroadcast.created_at.desc())
            .limit(1)
        )
        if active:
            return active
        raise


async def execute_broadcast(
    session: AsyncSession,
    *,
    broadcast_id: uuid.UUID,
    settings: Settings,
    publisher: XPublisherProtocol | None = None,
) -> SocialBroadcast:
    """Executes the publication of a broadcast record with pre-flight re-validation."""
    # 1. Emergency kill-switch pre-claim check
    if settings.social_broadcast_mode == "disabled":
        broadcast = await session.get(SocialBroadcast, broadcast_id)
        if broadcast and broadcast.status in ("queued", "retry_wait", "processing"):
            broadcast.status = "disabled"
            broadcast.last_error = (
                "Civic bot social broadcasting is currently disabled by administrator "
                "configuration."
            )
            broadcast.updated_at = datetime.now(UTC)
            await audit(
                session,
                action="report.social_broadcast_disabled",
                entity_type="report",
                entity_id=broadcast.report_id,
                actor_id=broadcast.requested_by,
                after={
                    "broadcast_id": str(broadcast.id),
                    "status": "disabled",
                    "reason": "kill_switch_activated",
                },
            )
            await session.commit()
            return broadcast

    # 1b. Atomically claim the broadcast row from ("queued", "retry_wait") -> "processing"
    now = datetime.now(UTC)
    claim_stmt = (
        update(SocialBroadcast)
        .where(
            SocialBroadcast.id == broadcast_id,
            SocialBroadcast.status.in_(["queued", "retry_wait"]),
        )
        .values(
            status="processing",
            attempts=SocialBroadcast.attempts + 1,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    claim_res = await session.execute(claim_stmt)
    await session.commit()

    broadcast = await session.get(SocialBroadcast, broadcast_id)
    if not broadcast:
        raise ApiError("Broadcast record not found", 404, "broadcast_not_found")

    claimed_count = getattr(claim_res, "rowcount", 0)
    if claimed_count == 0:
        # Another worker or process already claimed this broadcast, or it reached terminal state
        logger.info(
            "broadcast %s already processing or in terminal state (%s); skipping execution",
            broadcast_id,
            broadcast.status,
            extra=log_extra(broadcast_id=str(broadcast_id), status=broadcast.status),
        )
        return broadcast

    # 2. Pre-flight re-validation: fetch live report record
    report = await session.get(Report, broadcast.report_id)
    if not report or report.deleted_at is not None:
        broadcast.status = "failed"
        broadcast.last_error = "Report no longer exists or has been deleted."
        broadcast.updated_at = datetime.now(UTC)
        await session.commit()
        return broadcast

    if report.visibility != "public":
        broadcast.status = "failed"
        broadcast.last_error = "Report visibility was changed from public; broadcast aborted."
        broadcast.updated_at = datetime.now(UTC)
        await session.commit()
        return broadcast

    if report.status == "draft":
        broadcast.status = "failed"
        broadcast.last_error = "Report is in draft status; broadcast aborted."
        broadcast.updated_at = datetime.now(UTC)
        await session.commit()
        return broadcast

    if (report.severity or "").lower() not in ("high", "critical"):
        broadcast.status = "failed"
        broadcast.last_error = "Report severity is ineligible for official bot escalation."
        broadcast.updated_at = datetime.now(UTC)
        await session.commit()
        return broadcast

    # 3. Emergency kill-switch pre-publish check immediately before provider call
    if settings.social_broadcast_mode == "disabled":
        broadcast.status = "disabled"
        broadcast.last_error = (
            "Civic bot social broadcasting was disabled before publication by kill-switch."
        )
        broadcast.updated_at = datetime.now(UTC)
        await audit(
            session,
            action="report.social_broadcast_disabled",
            entity_type="report",
            entity_id=broadcast.report_id,
            actor_id=broadcast.requested_by,
            after={
                "broadcast_id": str(broadcast.id),
                "status": "disabled",
                "reason": "kill_switch_activated_before_publish",
            },
        )
        await session.commit()
        return broadcast

    pub = publisher or get_social_publisher(settings)
    result = await pub.publish(
        broadcast.post_text,
        report_id=str(broadcast.report_id),
        idempotency_key=broadcast.idempotency_key,
    )

    # 4. Apply outcome state transition
    if result.ok:
        if settings.social_broadcast_mode == "simulated":
            broadcast.status = "simulated"
            broadcast.external_post_id = result.external_post_id
            broadcast.published_url = None
        else:
            broadcast.status = "published"
            broadcast.external_post_id = result.external_post_id
            broadcast.published_url = result.published_url
            broadcast.published_at = datetime.now(UTC)

        broadcast.last_error = None
        await audit(
            session,
            action=f"report.social_broadcast_{broadcast.status}",
            entity_type="report",
            entity_id=broadcast.report_id,
            actor_id=broadcast.requested_by,
            after={
                "broadcast_id": str(broadcast.id),
                "external_post_id": broadcast.external_post_id,
                "status": broadcast.status,
            },
        )
    else:
        broadcast.last_error = result.error
        if getattr(result, "outcome_unknown", False):
            # Ambiguous network timeout: persist explicit uncertain state, NEVER blindly retry
            broadcast.status = "outcome_unknown"
            logger.error(
                "social broadcast outcome unknown for report %s (broadcast %s): %s",
                broadcast.report_id,
                broadcast.id,
                result.error,
                extra=log_extra(
                    report_id=str(broadcast.report_id),
                    broadcast_id=str(broadcast.id),
                    error=result.error,
                ),
            )
            await audit(
                session,
                action="report.social_broadcast_outcome_unknown",
                entity_type="report",
                entity_id=broadcast.report_id,
                actor_id=broadcast.requested_by,
                after={
                    "broadcast_id": str(broadcast.id),
                    "attempts": broadcast.attempts,
                    "error": result.error,
                    "resolution_required": "operator_verification",
                },
            )
        elif result.retryable and broadcast.attempts < broadcast.max_attempts:
            broadcast.status = "retry_wait"
            await audit(
                session,
                action="report.social_broadcast_retry_scheduled",
                entity_type="report",
                entity_id=broadcast.report_id,
                actor_id=broadcast.requested_by,
                after={
                    "broadcast_id": str(broadcast.id),
                    "attempt": broadcast.attempts,
                    "error": result.error,
                },
            )
        else:
            broadcast.status = "failed"
            await audit(
                session,
                action="report.social_broadcast_failed",
                entity_type="report",
                entity_id=broadcast.report_id,
                actor_id=broadcast.requested_by,
                after={
                    "broadcast_id": str(broadcast.id),
                    "attempts": broadcast.attempts,
                    "error": result.error,
                },
            )

    broadcast.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(broadcast)
    return broadcast


async def recover_stuck_broadcasts(
    session: AsyncSession,
    settings: Settings,
    max_age_seconds: int = 600,
) -> list[uuid.UUID]:
    """Recovers broadcasts stranded in 'processing' or 'queued' due to worker crash/timeout.

    CRITICAL RELIABILITY GUARANTEES:
    - If social_broadcast_mode is 'disabled', recovery sweep is a NO-OP.
    - 'outcome_unknown' broadcasts are NEVER re-enqueued automatically.
    - Stranded 'processing' broadcasts in 'live' mode transition to 'outcome_unknown'
      to prevent blind duplicate publication if the crash occurred post-transmission.
    """
    if settings.social_broadcast_mode == "disabled":
        logger.info("recover_stuck_broadcasts: skipped because social_broadcast_mode is disabled")
        return []

    cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    retry_cutoff = datetime.now(UTC) - timedelta(seconds=60)
    stmt = (
        select(SocialBroadcast)
        .where(
            or_(
                and_(
                    SocialBroadcast.status == "processing",
                    SocialBroadcast.updated_at < cutoff,
                ),
                and_(
                    SocialBroadcast.status == "queued",
                    SocialBroadcast.created_at < cutoff,
                ),
                and_(
                    SocialBroadcast.status == "retry_wait",
                    SocialBroadcast.updated_at < retry_cutoff,
                ),
            )
        )
        .order_by(SocialBroadcast.updated_at.asc())
        .limit(50)
    )
    stuck_broadcasts = (await session.execute(stmt)).scalars().all()
    recovered_ids: list[uuid.UUID] = []

    for b in stuck_broadcasts:
        if b.attempts >= b.max_attempts:
            b.status = "failed"
            b.last_error = (
                f"Broadcast stuck past {max_age_seconds}s and reached maximum "
                f"attempts ({b.attempts}/{b.max_attempts})."
            )
        elif b.status == "processing" and settings.social_broadcast_mode == "live":
            # Worker crash while communicating with live X API: outcome is ambiguous!
            # Move to outcome_unknown rather than blind re-queue to prevent duplicate tweets.
            b.status = "outcome_unknown"
            b.last_error = (
                f"Stranded in processing state after worker crash/timeout ({max_age_seconds}s). "
                "Outcome is ambiguous; operator verification required."
            )
        else:
            b.status = "queued"
            b.last_error = f"Recovered from stranded state after {max_age_seconds}s timeout."
            if settings.celery_enabled:
                try:
                    from tk_api.worker import celery_app as worker_app

                    worker_app.send_task("tk_worker.social_broadcast", args=[str(b.id)])
                except Exception:
                    logger.warning(
                        "failed to re-enqueue recovered broadcast %s to celery",
                        b.id,
                        extra=log_extra(broadcast_id=str(b.id)),
                    )
        b.updated_at = datetime.now(UTC)
        recovered_ids.append(b.id)

    if recovered_ids:
        await session.commit()
        logger.info(
            "recovered %d stuck social broadcasts",
            len(recovered_ids),
            extra=log_extra(recovered_count=len(recovered_ids)),
        )

    return recovered_ids


async def reconcile_broadcast_outcome(
    session: AsyncSession,
    *,
    broadcast_id: uuid.UUID,
    outcome: Literal["published", "failed"],
    external_post_id: str | None = None,
    resolution_note: str | None = None,
    operator_id: uuid.UUID | None = None,
) -> SocialBroadcast:
    """Reconciles an uncertain broadcast ('outcome_unknown') following operator verification."""
    broadcast = await session.get(SocialBroadcast, broadcast_id)
    if not broadcast:
        raise ApiError("Broadcast record not found", 404, "broadcast_not_found")
    if broadcast.status != "outcome_unknown":
        raise ApiError(
            "Only broadcasts with 'outcome_unknown' status can be reconciled "
            f"(current: {broadcast.status})",
            400,
            "invalid_broadcast_status_for_reconciliation",
        )
    if outcome == "published":
        if not external_post_id:
            raise ApiError(
                "External post ID is required when reconciling as published",
                422,
                "missing_external_post_id",
            )
        broadcast.status = "published"
        broadcast.external_post_id = external_post_id
        broadcast.published_url = f"https://x.com/TheekKaro/status/{external_post_id}"
        broadcast.published_at = datetime.now(UTC)
        broadcast.last_error = None
    else:
        broadcast.status = "failed"
        broadcast.last_error = (
            f"Reconciled as failed by operator: {resolution_note or 'No post found on X'}"
        )

    broadcast.updated_at = datetime.now(UTC)
    await audit(
        session,
        action="report.social_broadcast_reconciled",
        entity_type="report",
        entity_id=broadcast.report_id,
        actor_id=operator_id or broadcast.requested_by,
        after={
            "broadcast_id": str(broadcast.id),
            "status": broadcast.status,
            "external_post_id": broadcast.external_post_id,
            "resolution_note": resolution_note,
        },
    )
    await session.commit()
    await session.refresh(broadcast)
    return broadcast


async def get_latest_broadcast_for_report(
    session: AsyncSession,
    report_id: uuid.UUID,
) -> SocialBroadcast | None:
    """Retrieves the latest social broadcast record for a report."""
    stmt = (
        select(SocialBroadcast)
        .where(SocialBroadcast.report_id == report_id)
        .order_by(SocialBroadcast.created_at.desc())
        .limit(1)
    )
    return await session.scalar(stmt)
