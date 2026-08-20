"""Media service (API.md §7, DATABASE.md §3.4).

Flow: 1) ``request_upload`` returns the storage endpoint ready to receive bytes
(minio: presigned PUT URL; memory/local: API dev route). 2) Client uploads.
3) ``complete`` verifies size + checksum (when provided), runs the scan gate
(magic bytes / ClamAV-slot), records width/height, generates a thumbnail, and
flips status ``uploading`` → ``available`` (or ``failed``).

Any media whose scan is not ``clean`` stays failed and can never be served.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from tk_api.core.audit import audit
from tk_api.core.config import Settings
from tk_api.core.errors import ApiError
from tk_api.media.models import MediaObject
from tk_api.media.scan import ALLOWED_MIME, make_thumbnail, probe_image, scan_bytes
from tk_api.media.storage import StorageAdapter

THUMBNAIL_SUFFIX = ".thumb.jpg"


class MediaError(ApiError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _object_key(now: datetime) -> str:
    return f"media/{now.year:04d}/{now.month:02d}/{uuid.uuid4().hex}"


async def _get_media(session: AsyncSession, media_id: uuid.UUID) -> MediaObject:
    media = await session.get(MediaObject, media_id)
    if media is None or media.status == "deleted":
        raise MediaError("media not found", 404, "media_not_found")
    return media


def _media_out(media: MediaObject, download_url: str | None = None) -> dict[str, Any]:
    return {
        "id": str(media.id),
        "bucket": media.bucket,
        "object_key": media.object_key,
        "mime_type": media.mime_type,
        "size_bytes": media.size_bytes,
        "width": media.width,
        "height": media.height,
        "scan_status": media.scan_status,
        "status": media.status,
        "checksum_sha256": media.checksum_sha256,
        "uploaded_by": str(media.uploaded_by),
        "created_at": media.created_at,
        "updated_at": media.updated_at,
        "download_url": download_url,
    }


async def request_upload(
    session: AsyncSession,
    *,
    settings: Settings,
    storage: StorageAdapter,
    mime_type: str,
    size_bytes: int,
    uploaded_by: uuid.UUID,
    request: Request,
) -> dict[str, Any]:
    if mime_type not in ALLOWED_MIME or mime_type not in settings.media_allowed_mime:
        raise MediaError(f"unsupported media type: {mime_type}", 422, "unsupported_mime")
    max_bytes = settings.media_max_size_mb * 1024 * 1024
    if size_bytes <= 0 or size_bytes > max_bytes:
        raise MediaError("media size out of range", 422, "invalid_size")

    key = _object_key(_utcnow())
    media = MediaObject(
        bucket=settings.media_minio_bucket,
        object_key=key,
        checksum_sha256="",  # filled at complete
        mime_type=mime_type,
        size_bytes=size_bytes,
        scan_status="pending",
        status="uploading",
        uploaded_by=uploaded_by,
    )
    session.add(media)
    await session.flush()
    await audit(
        session,
        action="media.upload_request",
        entity_type="media_object",
        entity_id=media.id,
        actor_id=uploaded_by,
        after={"mime_type": mime_type, "size_bytes": size_bytes},
        request=request,
    )
    await session.commit()

    presigned = storage.request_upload(key, size_bytes)
    return {
        "media_id": str(media.id),
        "object_key": key,
        "upload_method": "presigned" if presigned is not None else "api",
        "presigned_url": presigned,
        "expires_in": 900,
    }


async def complete_upload(
    session: AsyncSession,
    *,
    media_id: uuid.UUID,
    settings: Settings,
    storage: StorageAdapter,
    checksum_sha256: str | None,
    actor: Any,
    request: Request,
) -> dict[str, Any]:
    media = await _get_media(session, media_id)
    if media.status != "uploading":
        # idempotent replay: a completed upload returns its final state
        return _media_out(media, download_url=storage.download_url(media.bucket, media.object_key))
    if media.uploaded_by != actor.id and not actor.has_role("admin"):
        raise MediaError("not the upload owner", 403, "forbidden")

    try:
        actual_size = storage.stat(media.bucket, media.object_key)
    except FileNotFoundError:
        await _fail(session, media, "object missing in storage")
        raise MediaError("uploaded object not found in storage", 409, "upload_missing") from None

    if actual_size != media.size_bytes:
        await _fail(
            session, media, f"size mismatch: declared {media.size_bytes}, actual {actual_size}"
        )
        raise MediaError(
            f"declared size {media.size_bytes} != actual {actual_size}", 409, "size_mismatch"
        )

    data = storage.read_prefix(media.bucket, media.object_key, actual_size)
    digest = hashlib.sha256(data).hexdigest()
    if checksum_sha256 and digest != checksum_sha256.lower():
        await _fail(session, media, "checksum mismatch")
        raise MediaError("checksum mismatch", 409, "checksum_mismatch")

    if settings.celery_enabled:
        # the scan gate moved to the worker (Phase 8): mark pending and enqueue
        media.status = "pending_scan"
        media.checksum_sha256 = digest
        media.updated_at = _utcnow()
        await session.commit()
        from tk_api.worker import celery_app as worker_app

        worker_app.send_task("tk_worker.process_media", args=[str(media.id)])
        return _media_out(media)

    return await finalize_scan(  # inline fallback (tests / single-process dev)
        session,
        media=media,
        data=data,
        settings=settings,
        storage=storage,
        actor=actor,
        request=request,
    )


async def finalize_scan(
    session: AsyncSession,
    *,
    media: MediaObject,
    data: bytes,
    settings: Settings,
    storage: StorageAdapter,
    actor: Any | None = None,
    request: Request | None = None,
) -> dict[str, Any]:
    """Scan gate + dimensions + thumbnail; the worker calls this for
    ``pending_scan`` rows (ADR-005 at-least-once: idempotent per status)."""
    result = scan_bytes(data, media.mime_type, settings.media_max_size_mb * 1024 * 1024)
    if not result.clean:
        await _fail(session, media, result.detail, request=request)
        raise MediaError(f"media failed the scan gate: {result.detail}", 422, "scan_failed")

    media.scan_status = "clean"
    media.status = "available"
    width, height = probe_image(data)
    media.width = width
    media.height = height
    media.updated_at = _utcnow()

    thumbnail = make_thumbnail(data)
    if thumbnail is not None:
        storage.save_bytes(media.bucket, media.object_key + THUMBNAIL_SUFFIX, thumbnail)

    if actor is not None:
        await audit(
            session,
            action="media.upload_complete",
            entity_type="media_object",
            entity_id=media.id,
            actor_id=actor.id,
            after={
                "status": media.status,
                "scan_status": media.scan_status,
                "size_bytes": media.size_bytes,
            },
            request=request,
        )
    await session.commit()
    return _media_out(media, download_url=storage.download_url(media.bucket, media.object_key))


async def process_media_task(
    session: AsyncSession,
    *,
    media_id: uuid.UUID,
    settings: Settings,
    storage: StorageAdapter,
) -> str:
    """Worker body for ``tk_worker.process_media``."""
    media = await _get_media(session, media_id)
    if media.status == "available":
        return media.status  # already finalized (replay under at-least-once)
    data = storage.read_prefix(media.bucket, media.object_key, media.size_bytes)
    try:
        await finalize_scan(session, media=media, data=data, settings=settings, storage=storage)
        return "available"
    except MediaError:
        return "failed"


STUCK_SCAN_THRESHOLD_MINUTES = 10


async def recover_stuck_media(
    session: AsyncSession,
    *,
    settings: Settings,
    storage: StorageAdapter,
) -> list[uuid.UUID]:
    """Re-drive media stuck in ``pending_scan`` (worker died before scanning).

    Beat sweep (Step 11): rows that entered ``pending_scan`` more than
    ``STUCK_SCAN_THRESHOLD_MINUTES`` ago are re-enqueued (celery) or finalized
    inline (single-process dev / tests). Idempotent: ``process_media_task``
    returns immediately for rows already ``available``.
    """
    cutoff = _utcnow() - timedelta(minutes=STUCK_SCAN_THRESHOLD_MINUTES)
    stuck = list(
        (
            await session.execute(
                select(MediaObject).where(
                    MediaObject.status == "pending_scan",
                    MediaObject.updated_at < cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    recovered: list[uuid.UUID] = []
    for media in stuck:
        if settings.celery_enabled:
            from tk_api.worker import celery_app as worker_app

            worker_app.send_task("tk_worker.process_media", args=[str(media.id)])
        else:
            await process_media_task(session, media_id=media.id, settings=settings, storage=storage)
        recovered.append(media.id)
    if stuck:
        await session.commit()
    return recovered


async def _fail(
    session: AsyncSession,
    media: MediaObject,
    detail: str,
    *,
    request: Request | None = None,
) -> None:
    media.status = "failed"
    media.scan_status = "error"
    media.updated_at = _utcnow()
    if request is not None:
        from tk_api.core.audit import audit

        await audit(
            session,
            action="media.upload_failed",
            entity_type="media_object",
            entity_id=media.id,
            actor_id=media.uploaded_by,
            after={"status": "failed", "reason": detail},
            request=request,
        )
    await session.commit()


async def get_media(
    session: AsyncSession,
    *,
    media_id: uuid.UUID,
    storage: StorageAdapter,
    viewer: Any | None,
) -> dict[str, Any]:
    media = await _get_media(session, media_id)
    owner = viewer is not None and (media.uploaded_by == viewer.id or viewer.has_role("admin"))
    if not owner:
        raise MediaError("not the upload owner", 403, "forbidden")
    if media.status == "failed":
        raise MediaError("media failed processing", 409, "media_failed")
    url = storage.download_url(media.bucket, media.object_key)
    return _media_out(media, download_url=url)


async def save_dev_object(
    session: AsyncSession,
    *,
    media_id: uuid.UUID,
    data: bytes,
    actor: Any,
    storage: StorageAdapter,
) -> None:
    """Dev-mode direct upload (memory/local storage): store the bytes as-is;
    the scan gate runs at ``complete``."""
    media = await _get_media(session, media_id)
    if media.status != "uploading":
        raise MediaError("upload already completed", 409, "upload_completed")
    if media.uploaded_by != actor.id and not actor.has_role("admin"):
        raise MediaError("not the upload owner", 403, "forbidden")
    if len(data) != media.size_bytes:
        raise MediaError("size mismatch with upload request", 409, "size_mismatch")
    storage.save_bytes(media.bucket, media.object_key, data)


async def read_thumbnail(
    session: AsyncSession,
    *,
    media_id: uuid.UUID,
    storage: StorageAdapter,
    viewer: Any | None = None,
) -> bytes:
    """Low-res thumbnail bytes. Visibility-gated (Step 7): thumbnails of
    public-report evidence are world-readable (public feeds), but evidence
    attached to private reports requires the reporter or staff — a thumbnail
    can still reveal private content."""
    media = await _get_media(session, media_id)
    if media.status != "available":
        raise MediaError("thumbnail not available", 404, "media_not_found")
    if not await _viewer_can_read_media(session, media, viewer):
        raise MediaError("thumbnail not found", 404, "media_not_found")
    thumb_key = media.object_key + THUMBNAIL_SUFFIX
    try:
        size = storage.stat(media.bucket, thumb_key)
    except FileNotFoundError:
        raise MediaError("thumbnail not found", 404, "media_not_found") from None
    return storage.read_prefix(media.bucket, thumb_key, size)


async def read_media_bytes(
    session: AsyncSession,
    *,
    media_id: uuid.UUID,
    storage: StorageAdapter,
    viewer: Any | None = None,
) -> tuple[bytes, str]:
    """Stream full object bytes behind the same visibility gate (API-proxied
    download; used for evidence ``url`` links in all storage modes)."""
    media = await _get_media(session, media_id)
    if media.status != "available":
        raise MediaError("media not available", 404, "media_not_found")
    if not await _viewer_can_read_media(session, media, viewer):
        raise MediaError("media not found", 404, "media_not_found")
    return storage.read_prefix(media.bucket, media.object_key, media.size_bytes), media.mime_type


async def read_object(
    session: AsyncSession,
    *,
    bucket: str,
    object_key: str,
    storage: StorageAdapter,
    viewer: Any | None = None,
) -> tuple[bytes, str]:
    """Read a stored object via API routes (memory/local storage modes).

    Visibility-gated (IDOR hardening, Phase 16): the object must belong to a
    public report, or the viewer must be the uploader / staff when the report
    is private (or the media is not linked to any report).
    """
    media = await session.scalar(
        select(MediaObject).where(
            MediaObject.bucket == bucket, MediaObject.object_key == object_key
        )
    )
    if media is None or media.status != "available":
        raise MediaError("object not found", 404, "media_not_found")
    if not await _viewer_can_read_media(session, media, viewer):
        raise MediaError("object not found", 404, "media_not_found")
    return storage.read_prefix(bucket, object_key, media.size_bytes), media.mime_type


async def _viewer_can_read_media(
    session: AsyncSession, media: MediaObject, viewer: Any | None
) -> bool:
    """True when the viewer may read a media object in dev mode. Mirrors the
    report visibility gate (reports/service.can_view_report) without importing
    it, to avoid a service cycle."""
    if viewer is not None and (str(media.uploaded_by) == str(viewer.id)):
        return True
    if viewer is not None and viewer.has_role("admin"):
        return True
    from tk_api.reports.models import Report, ReportEvidence

    link = await session.scalar(
        select(ReportEvidence.report_id).where(ReportEvidence.media_object_id == media.id)
    )
    if link is None:
        # unattached media: owner/admin only (checked above)
        return False
    report = await session.get(Report, link)
    if report is None:
        return False
    if report.visibility == "public":
        return True
    if viewer is None:
        return False
    if any(role in {"super_admin", "admin", "moderator"} for role in viewer.role_codes()):
        return True
    return str(report.reporter_id) == str(viewer.id)
