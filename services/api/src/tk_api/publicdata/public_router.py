"""Phase 15 public open-data API (`/api/public/v1`).

Versioned public access to public-safe data: dataset catalog + provenance,
geographies, categories, institutions, reports, resolutions, departments,
coverage, methodology, research queries and exports. Rate-limited per IP and
optionally per API key (`X-API-Key`). All responses are public-safe — no PII,
no private media, no internal notes. Corrections require login (they live
under `/api/v1/public-data`).
"""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from tk_api.api.deps import DbSession
from tk_api.civic.models import Category
from tk_api.core.errors import ApiError
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.publicdata import service as pd_service
from tk_api.publicdata.models import DataExportJob, PublicApiKey
from tk_api.publicdata.schemas import ExportRequest

public_router = APIRouter(prefix="/api/public/v1", tags=["public"])

_service = pd_service.PublicDataService()

_IP_LIMIT = 120
_IP_WINDOW = 60

PAGE = Annotated[int, Query(ge=1, le=100000)]
PAGE_SIZE = Annotated[int, Query(ge=1, le=100)]


class PublicApiError(ApiError):
    pass


def _parse_uuid(raw: str, *, kind: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise PublicApiError(f"invalid {kind}", 422, "invalid_id") from exc


async def _resolve_access(request: Request, session: DbSession) -> tuple[PublicApiKey | None, str]:
    """Resolve API key (when sent) and apply rate limits."""
    secret = request.headers.get("x-api-key")
    remote = client_ip(request)
    key: PublicApiKey | None = None
    if secret:
        key = await _service.resolve_api_key(session, secret)
        if key is None:
            raise PublicApiError("invalid api key", 401, "invalid_api_key")
    limit = key.quota_per_hour if key else _IP_LIMIT
    window = 3600 if key else _IP_WINDOW
    key_id = key.id if key else None
    bucket_key = f"pk:{key_id if key_id else 'ip:' + remote}:{request.url.path}"
    await rate_limit(
        request, bucket="public_api", key=bucket_key, limit=limit, window_seconds=window
    )
    return key, remote


@contextlib.asynccontextmanager
async def _track(
    request: Request, session: DbSession, key: PublicApiKey | None, remote: str
) -> AsyncIterator[None]:
    """Record one usage row per public request (aggregate-only reporting)."""
    start = time.monotonic()
    status = 200
    try:
        yield
    except PublicApiError as exc:
        status = exc.status
        raise
    except Exception:
        status = 500
        raise
    finally:
        try:
            await _service.record_usage(
                session,
                key=key,
                user=None,
                endpoint=request.url.path,
                method=request.method,
                status_code=status,
                latency_ms=int((time.monotonic() - start) * 1000),
                client_ip=remote,
            )
            await session.commit()
        except Exception:
            await session.rollback()


def _now() -> datetime:
    return datetime.now(UTC)


# -----------------------------------------------------------------------------
# Dataset catalog + provenance
# -----------------------------------------------------------------------------


@public_router.get("/datasets", summary="Public dataset catalog")
async def list_public_datasets(
    request: Request,
    session: DbSession,
    category: str | None = None,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        rows = await _service.list_public_datasets(session, category=category)
        return {"items": rows, "count": len(rows)}


@public_router.get("/datasets/{slug}", summary="Dataset detail with provenance")
async def public_dataset_detail(
    slug: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.get_public_dataset(session, slug, include_internal=True)


@public_router.get("/datasets/{slug}/versions", summary="Dataset version history")
async def public_dataset_versions(
    slug: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        detail = await _service.get_public_dataset(session, slug, include_internal=True)
        return {"items": detail["versions"], "count": len(detail["versions"])}


@public_router.get("/datasets/{slug}/lineage", summary="Dataset lineage")
async def public_dataset_lineage(
    slug: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        detail = await _service.get_public_dataset(session, slug, include_internal=True)
        return {"steps": detail["lineage"], "count": len(detail["lineage"])}


# -----------------------------------------------------------------------------
# Explorer data
# -----------------------------------------------------------------------------


@public_router.get("/geographies", summary="Geography registry (optionally drilled down)")
async def public_geographies(
    request: Request,
    session: DbSession,
    type_code: str | None = None,
    parent_id: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        parent = _parse_uuid(parent_id, kind="geography") if parent_id else None
        payload = await _service.public_geographies(
            session, type_code=type_code, parent_id=parent, q=q
        )
        return payload


@public_router.get("/categories", summary="Civic categories")
async def public_categories(
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        rows = (
            (
                await session.execute(
                    select(Category)
                    .where(Category.is_active.is_(True))
                    .order_by(Category.slug.asc())
                )
            )
            .scalars()
            .all()
        )
        return {
            "items": [
                {
                    "slug": c.slug,
                    "name_key": c.default_locale_keys.get("en", c.slug),
                    "icon": c.icon,
                    "is_active": c.is_active,
                }
                for c in rows
            ],
            "count": len(rows),
        }


@public_router.get("/institutions", summary="Public institutions")
async def public_institutions(
    request: Request,
    session: DbSession,
    geography_id: str | None = None,
    type_code: str | None = None,
    q: str | None = None,
    page: PAGE = 1,
    page_size: PAGE_SIZE = 50,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        geo = _parse_uuid(geography_id, kind="geography") if geography_id else None
        return await _service.public_institutions(
            session,
            page=page,
            page_size=page_size,
            geography_id=geo,
            type_code=type_code,
            q=q,
        )


@public_router.get("/reports", summary="Public civic reports")
async def public_reports(
    request: Request,
    session: DbSession,
    category_slug: str | None = None,
    status: str | None = None,
    geography_id: str | None = None,
    page: PAGE = 1,
    page_size: PAGE_SIZE = 50,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        geo = _parse_uuid(geography_id, kind="geography") if geography_id else None
        return await _service.public_reports(
            session,
            page=page,
            page_size=page_size,
            category_slug=category_slug,
            status=status,
            geography_id=geo,
        )


@public_router.get("/resolutions", summary="Public resolution outcomes")
async def public_resolutions(
    request: Request,
    session: DbSession,
    page: PAGE = 1,
    page_size: PAGE_SIZE = 50,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.public_resolutions(session, page=page, page_size=page_size)


@public_router.get("/departments", summary="Public department directory")
async def public_departments(
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.public_departments(session)


@public_router.get("/departments/{department_id}", summary="Public department profile")
async def public_department_profile(
    department_id: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.department_public_profile(
            session, _parse_uuid(department_id, kind="department")
        )


@public_router.get("/statistics", summary="Platform-wide public statistics")
async def public_statistics(
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        result = await _service.india_statistics(session)
        result["note"] = "Based on available platform data."
        return result


@public_router.get("/coverage", summary="Data coverage by geography level")
async def public_coverage(
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.coverage(session)


@public_router.get("/freshness", summary="Dataset and aggregate freshness")
async def public_freshness(
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return {"items": await _service.dataset_freshness(session)}


@public_router.get("/methodology", summary="Public data methodology + metric definitions")
async def public_methodology(
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return _service.methodology()


# -----------------------------------------------------------------------------
# Exports (public, anonymous; large exports run async)
# -----------------------------------------------------------------------------


@public_router.post("/exports", status_code=201, summary="Request a public export")
async def public_create_export(
    body: ExportRequest,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        job = await _service.create_export_job(
            session, user_id=None, kind=body.kind, fmt=body.format, filters=body.filters
        )
        if job["sync"]:
            row = await session.get(DataExportJob, job["id"])
            if row is None:
                raise PublicApiError("export job not found", 404, "export_job_not_found")
            settings = request.app.state.settings
            storage = request.app.state.storage
            done = await _service.run_export(session, row, settings=settings, storage=storage)
            return done
        from tk_api.worker.tasks import generate_export

        generate_export.delay(str(job["id"]))
        return job


@public_router.get("/exports/jobs/{job_id}", summary="Export job status (public)")
async def public_export_status(
    job_id: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        job = await session.get(DataExportJob, _parse_uuid(job_id, kind="job"))
        if job is None or job.user_id is not None:
            raise PublicApiError("export job not found", 404, "export_job_not_found")
        payload = _service._job_payload(job)
        if job.status == "ready" and job.file_key:
            payload["download_url"] = request.app.state.storage.download_url(
                request.app.state.settings.media_exports_bucket,
                job.file_key,
                expires_seconds=900,
            )
        return payload


@public_router.get("/exports/jobs/{job_id}/download", summary="Download a ready export")
async def public_export_download(
    job_id: str,
    request: Request,
    session: DbSession,
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        job = await session.get(DataExportJob, _parse_uuid(job_id, kind="job"))
        if job is None or job.user_id is not None:
            raise PublicApiError("export job not found", 404, "export_job_not_found")
        if job.status != "ready" or not job.file_key:
            raise PublicApiError("export not ready", 409, "export_not_ready")
        if job.file_url_expires_at and _now() > job.file_url_expires_at:
            job.status = "expired"
            raise PublicApiError("export link expired", 410, "export_link_expired")
        url = request.app.state.storage.download_url(
            request.app.state.settings.media_exports_bucket,
            job.file_key,
            expires_seconds=900,
        )
        return {"download_url": url, "expires_in_seconds": 900}


# -----------------------------------------------------------------------------
# Research (structured, validated — no free-form SQL anywhere)
# -----------------------------------------------------------------------------


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise PublicApiError("invalid date format (use ISO 8601)", 422, "invalid_date") from exc


@public_router.get("/research/query", summary="Structured research query")
async def public_research_query(
    request: Request,
    session: DbSession,
    geography_id: str | None = None,
    category_slug: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    date_preset: str = "30d",
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.research_query(
            session,
            geography_id=_parse_uuid(geography_id, kind="geography") if geography_id else None,
            category_slug=category_slug,
            status_filter=status,
            date_from=_parse_dt(date_from),
            date_to=_parse_dt(date_to),
            date_preset=date_preset,
        )


@public_router.get("/research/compare", summary="Cross-geography comparison")
async def public_research_compare(
    request: Request,
    session: DbSession,
    geography_ids: str = Query(min_length=1, description="Comma-separated geography UUIDs"),
    category_slug: str | None = None,
    status: str | None = None,
    date_preset: str = "all",
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        ids = [
            _parse_uuid(part.strip(), kind="geography")
            for part in geography_ids.split(",")
            if part.strip()
        ]
        return await _service.research_compare(
            session,
            ids,
            category_slug=category_slug,
            status_filter=status,
            date_preset=date_preset,
        )


@public_router.get("/research/trends", summary="Time-series trend explorer")
async def public_research_trends(
    request: Request,
    session: DbSession,
    geography_id: str | None = None,
    category_slug: str | None = None,
    metric: str = "reports",
    interval: str = "month",
    date_preset: str = "90d",
) -> dict[str, Any]:
    key, remote = await _resolve_access(request, session)
    async with _track(request, session, key, remote):
        return await _service.research_trends(
            session,
            geography_id=_parse_uuid(geography_id, kind="geography") if geography_id else None,
            category_slug=category_slug,
            metric=metric,
            interval=interval,
            date_preset=date_preset,
        )
