"""Media endpoints (API.md §7, SECURITY.md §6).

Upload flow differs per storage mode but the API contract is stable:

1. ``POST /media/uploads`` → idempotent; returns ``presigned_url`` (minio) or
   ``upload_method: "api"`` (memory/local, dev).
2. Client PUTs bytes (minio: directly to storage; dev: ``PUT /media/uploads/{id}/object``).
3. ``POST /media/uploads/{id}/complete`` → scan gate, thumbnails, status
   ``available`` (or ``failed``). Replays return the stored final state.

``GET /media/{id}`` returns metadata + a (presigned or API) download URL to the
owner. Thumbnails are deliberately low-res and public.

Hardening (Step 6): per-user rate limits on request/complete, JSON parse guards
(malformed bodies → 422, never 500), Content-Length pre-checks so dev-mode PUT
rejects oversized payloads before buffering, and nosniff + server-generated safe
filenames on every object/thumbnail response. Object keys are always generated
server-side ("media/YYYY/MM/<uuid>") — no client filename is ever stored or
reflected.
"""

from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from tk_api.api.deps import DbSession, get_optional_user, require_active
from tk_api.core.errors import ApiError
from tk_api.core.idempotency import IDEMPOTENCY_TTL_SECONDS, IdempotencyRecord
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.media import service as media_service

media_router = APIRouter(prefix="/api/v1/media", tags=["media"])

UploaderUser = Annotated[Any, Depends(require_active())]
OptionalViewer = Annotated[Any, Depends(get_optional_user)]

_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


async def _read_json(request: Request) -> dict[str, Any]:
    """Parse a small JSON body; malformed input → 422 (never a 500)."""
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > 8192:
                raise ApiError("request body too large", 413, "payload_too_large")
        except ValueError:
            pass
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise ApiError("request body is not valid JSON", 422, "invalid_payload") from exc
    if not isinstance(body, dict):
        raise ApiError("request body must be a JSON object", 422, "invalid_payload")
    return body


def _parse_id(raw: str, *, kind: str, error_kind: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ApiError(f"invalid {kind} id", 422, error_kind) from exc


def _safe_download_headers(mime_type: str, filename_stem: str) -> dict[str, str]:
    """nosniff + a server-generated, extension-limited Content-Disposition."""
    extension = _EXTENSION.get(mime_type, ".bin")
    return {
        "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'inline; filename="{filename_stem}{extension}"',
    }


@media_router.post("/uploads", status_code=201, summary="Request an upload (idempotent)")
async def request_upload(
    request: Request,
    user: UploaderUser,
    session: DbSession,
) -> Any:
    body = await _read_json(request)
    mime_type = body.get("mime_type")
    size_bytes = body.get("size_bytes")
    if not isinstance(mime_type, str) or not isinstance(size_bytes, int):
        raise ApiError("mime_type (str) and size_bytes (int) are required", 422, "invalid_payload")

    idem = request.headers.get("idempotency-key")
    key = None
    if idem is not None:
        try:
            key_id = uuid.UUID(idem)
        except ValueError as exc:
            raise ApiError(
                "Idempotency-Key must be a UUID", 422, "invalid_idempotency_key"
            ) from exc
        key = f"media:{user.id}:{key_id}"
        store = request.app.state.idempotency_store
        cached = await store.get(key)
        if cached is not None:
            return JSONResponse(status_code=200, content=cached.payload)

    await rate_limit(
        request, bucket="media", key=f"request:{user.id}", limit=30, window_seconds=3600
    )
    result = await media_service.request_upload(
        session,
        settings=request.app.state.settings,
        storage=request.app.state.storage,
        mime_type=mime_type,
        size_bytes=size_bytes,
        uploaded_by=user.id,
        request=request,
    )
    if key is not None:
        await request.app.state.idempotency_store.put(
            key, IdempotencyRecord(201, result), IDEMPOTENCY_TTL_SECONDS
        )
    return result


@media_router.put("/uploads/{media_id}/object", summary="Dev-mode upload route")
async def put_object(
    media_id: str,
    request: Request,
    user: UploaderUser,
    session: DbSession,
) -> Response:
    """Direct-upload route for memory/local storage; production uses presigned PUT."""
    parsed = _parse_id(media_id, kind="media", error_kind="invalid_media_id")
    await rate_limit(
        request, bucket="media", key=f"write:{client_ip(request)}", limit=60, window_seconds=60
    )
    # Reject oversized payloads before buffering them (dev mode only; minio
    # presigned PUTs are bounded by the same declared-size check at complete).
    max_bytes = request.app.state.settings.media_max_size_mb * 1024 * 1024
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > max_bytes:
                raise ApiError("payload exceeds the media size limit", 413, "payload_too_large")
        except ValueError:
            pass
    body = await request.body()
    await media_service.save_dev_object(
        session,
        media_id=parsed,
        data=body,
        actor=user,
        storage=request.app.state.storage,
    )
    return Response(status_code=204)


@media_router.post("/uploads/{media_id}/complete", summary="Verify + scan + activate")
async def complete_upload(
    media_id: str,
    request: Request,
    user: UploaderUser,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(media_id, kind="media", error_kind="invalid_media_id")
    await rate_limit(
        request, bucket="media", key=f"complete:{user.id}", limit=60, window_seconds=3600
    )
    checksum = None
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await _read_json(request)
        checksum = body.get("checksum_sha256")
    return await media_service.complete_upload(
        session,
        media_id=parsed,
        settings=request.app.state.settings,
        storage=request.app.state.storage,
        checksum_sha256=checksum,
        actor=user,
        request=request,
    )


@media_router.get("/{media_id}", summary="Media metadata + download URL (owner)")
async def get_media(
    media_id: str,
    request: Request,
    user: OptionalViewer,
    session: DbSession,
) -> dict[str, Any]:
    parsed = _parse_id(media_id, kind="media", error_kind="invalid_media_id")
    return await media_service.get_media(
        session,
        media_id=parsed,
        storage=request.app.state.storage,
        viewer=user,
    )


@media_router.get("/{media_id}/download", summary="Stream object bytes (visibility-gated)")
async def download_media(
    media_id: str,
    request: Request,
    viewer: OptionalViewer,
    session: DbSession,
) -> Response:
    """API-proxied download used by evidence ``url`` links. Applies the same
    visibility gate as the object route: public-report evidence is readable by
    anyone; private-report evidence requires the reporter or staff."""
    await rate_limit(
        request, bucket="media_read", key=f"dl:{client_ip(request)}", limit=60, window_seconds=60
    )
    parsed = _parse_id(media_id, kind="media", error_kind="invalid_media_id")
    data, mime_type = await media_service.read_media_bytes(
        session,
        media_id=parsed,
        storage=request.app.state.storage,
        viewer=viewer,
    )
    return Response(
        content=data,
        media_type=mime_type,
        headers=_safe_download_headers(mime_type, f"media-{parsed}"),
    )


@media_router.get("/{media_id}/thumbnail", summary="Low-res thumbnail (visibility-gated)")
async def get_thumbnail(
    media_id: str,
    request: Request,
    viewer: OptionalViewer,
    session: DbSession,
) -> Response:
    parsed = _parse_id(media_id, kind="media", error_kind="invalid_media_id")
    data = await media_service.read_thumbnail(
        session, media_id=parsed, storage=request.app.state.storage, viewer=viewer
    )
    return Response(
        content=data,
        media_type="image/jpeg",
        headers=_safe_download_headers("image/jpeg", f"thumb-{parsed}"),
    )


@media_router.get("/object/{bucket}/{object_key:path}")
async def read_object(
    bucket: str,
    object_key: str,
    request: Request,
    viewer: OptionalViewer,
    session: DbSession,
) -> Response:
    """Dev-mode read route (memory/local storage); production uses presigned
    URLs. Visibility-gated like the report detail endpoint: public-report
    objects are world-readable, private-report objects require the reporter or
    staff."""
    data, mime_type = await media_service.read_object(
        session,
        bucket=bucket,
        object_key=object_key,
        storage=request.app.state.storage,
        viewer=viewer,
    )
    return Response(
        content=data,
        media_type=mime_type,
        headers=_safe_download_headers(mime_type, f"media-{uuid.uuid4().hex[:12]}"),
    )


# ---------------------------------------------------------------------------
# Phase 5 — Evidence Chain Endpoints
# ---------------------------------------------------------------------------


@media_router.get(
    "/reports/{report_id}/evidence-chain",
    summary="Get evidence chain for a report",
)
async def get_evidence_chain(
    report_id: str,
    session: DbSession,
    user: UploaderUser,
) -> Any:
    """Return the evidence chain for a report (tamper-evident SHA-256 chain)."""
    from sqlalchemy import select

    from tk_api.media.models import EvidenceChain

    rid = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    stmt = (
        select(EvidenceChain)
        .where(EvidenceChain.report_id == rid)
        .order_by(EvidenceChain.created_at.desc())
        .limit(1)
    )
    chain = (await session.execute(stmt)).scalar_one_or_none()
    if chain is None:
        return {"report_id": report_id, "chain": None, "message": "No evidence chain found"}
    return {
        "report_id": report_id,
        "chain": {
            "id": str(chain.id),
            "chain_hash": chain.chain_hash,
            "evidence_count": chain.evidence_count,
            "created_at": chain.created_at.isoformat() if chain.created_at else None,
            "updated_at": chain.updated_at.isoformat() if chain.updated_at else None,
        },
    }


@media_router.get(
    "/reports/{report_id}/media",
    summary="List all media for a report with evidence pairing",
)
async def get_report_media(
    report_id: str,
    session: DbSession,
    user: UploaderUser,
) -> Any:
    """List all media items for a report with before/after pairing info."""
    from sqlalchemy import select

    from tk_api.media.models import MediaObject, ReportMedia

    rid = _parse_id(report_id, kind="report", error_kind="invalid_report_id")
    stmt = (
        select(ReportMedia, MediaObject)
        .join(MediaObject, ReportMedia.media_object_id == MediaObject.id)
        .where(ReportMedia.report_id == rid)
        .order_by(ReportMedia.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    media_items = []
    for rm, mo in rows:
        media_items.append(
            {
                "id": str(mo.id),
                "report_media_kind": rm.kind,
                "pair_group": rm.pair_group,
                "pair_role": rm.pair_role,
                "captured_at": rm.captured_at.isoformat() if rm.captured_at else None,
                "mime_type": mo.mime_type,
                "size_bytes": mo.size_bytes,
                "duration_seconds": mo.duration_seconds,
                "scan_status": mo.scan_status,
                "status": mo.status,
            }
        )

    return {
        "report_id": report_id,
        "media": media_items,
        "count": len(media_items),
    }
