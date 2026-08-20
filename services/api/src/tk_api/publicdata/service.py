"""Phase 15 public data, open data, research and transparency service.

Everything public-safe lives here. The module never reaches for PII: report
rows exported through this layer use an allowlist, generalize coordinates to
~0.01 deg, and exclude reporter identity, addresses, private media and notes.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.analytics.catalog import GLOBAL_METRIC_REGISTRY
from tk_api.cases.models import CivicCase
from tk_api.civic.models import Category, IssueType
from tk_api.core.errors import ApiError
from tk_api.departments.models import Department, DepartmentUser
from tk_api.geography.models import Geography, GeographyType
from tk_api.institutions.models import Institution, InstitutionType
from tk_api.publicdata.models import (
    DataCorrectionRequest,
    DataExportJob,
    PublicApiKey,
    PublicApiUsage,
    PublicDataset,
    PublicDatasetLineage,
    PublicDatasetVersion,
    SavedResearchQuery,
)
from tk_api.reports.models import Report
from tk_api.resolution.models import ResolutionEvidence, ResolutionReview, ResolutionSubmission
from tk_api.users.models import User

_IST = ZoneInfo("Asia/Kolkata")

_STALE_DAYS = 90
_MAYBE_STALE_DAYS = 30
_RECENT_DAYS = 7

# Public-safe dataset exports must never include these report columns.
_REPORT_EXPORT_ALLOWLIST = (
    "id",
    "ticket_no",
    "title",
    "description",
    "category_slug",
    "issue_type_slug",
    "status",
    "severity",
    "visibility",
    "boundary_id",
    "institution_id",
    "created_at",
    "resolved_at",
    "resolution_verified_at",
    "trust_score",
)

_EXPORT_FORMATS = ("csv", "json")
_SYNC_EXPORT_MAX_ROWS = 5000


class PublicDataError(ApiError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _label_freshness(updated: datetime | None, frequency: str | None) -> str:
    """Map dataset age + update frequency to a public freshness label.

    Labels: fresh / recently_updated / may_be_outdated / stale / no_data.
    """
    if updated is None:
        return "no_data"
    age = _utcnow() - updated
    if age <= timedelta(days=_RECENT_DAYS):
        return "fresh"
    if age <= timedelta(days=_MAYBE_STALE_DAYS):
        return "recently_updated"
    if frequency in ("daily", "weekly", "monthly", "continuous") or age <= timedelta(
        days=_STALE_DAYS
    ):
        return "may_be_outdated"
    return "stale"


def _generalize_coords(lon: float | None, lat: float | None) -> tuple[float | None, float | None]:
    """Round coordinates to ~0.01 deg (~1 km) — public-safe generalization."""
    if lon is None or lat is None:
        return None, None
    return round(lon, 2), round(lat, 2)


class PublicDataService:
    """Thin aggregation service over the platform's own tables + analytics."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Any]] = {}
        self._cache_ttl = 120.0

    # ------------------------------------------------------------------
    # cache helpers
    # ------------------------------------------------------------------

    def _cached(self, key: str) -> Any | None:
        hit = self._cache.get(key)
        if hit is None:
            return None
        created, value = hit
        if time.monotonic() - created > self._cache_ttl:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.monotonic(), value)
        if len(self._cache) > 256:
            now = time.monotonic()
            self._cache = {k: v for k, v in self._cache.items() if now - v[0] <= self._cache_ttl}

    # ------------------------------------------------------------------
    # dataset catalog + provenance
    # ------------------------------------------------------------------

    async def list_public_datasets(
        self, session: AsyncSession, category: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(PublicDataset).where(PublicDataset.status == "active")
        if category:
            stmt = stmt.where(PublicDataset.category == category)
        rows = (
            (await session.execute(stmt.order_by(PublicDataset.created_at.asc()))).scalars().all()
        )
        out: list[dict[str, Any]] = []
        for d in rows:
            out.append(self._dataset_item(d, session, include_internal=False))
        return out

    @staticmethod
    def _dataset_item(
        dataset: PublicDataset, session: AsyncSession, *, include_internal: bool = True
    ) -> dict[str, Any]:
        freshness = _label_freshness(dataset.last_updated_at, dataset.update_frequency)
        item: dict[str, Any] = {
            "slug": dataset.slug,
            "name": dataset.name,
            "name_hi": dataset.name_hi,
            "description": dataset.description,
            "category": dataset.category,
            "publisher": dataset.publisher,
            "source": dataset.source,
            "license": dataset.license,
            "update_frequency": dataset.update_frequency,
            "derived": dataset.derived,
            "version": dataset.version,
            "record_count": dataset.record_count,
            "last_updated_at": dataset.last_updated_at,
            "freshness": freshness,
            "status": dataset.status,
        }
        if include_internal:
            item.update(
                {
                    "source_url": dataset.source_url,
                    "license_url": dataset.license_url,
                    "released_at": dataset.released_at,
                    "retrieved_at": dataset.retrieved_at,
                    "processing_date": dataset.processing_date,
                    "derived_from": dataset.derived_from,
                    "coverage": dataset.coverage,
                    "formats": dataset.formats,
                    "checksum_sha256": dataset.checksum_sha256,
                    "documentation_url": dataset.documentation_url,
                    "methodology_slug": dataset.methodology_slug,
                    "description_hi": dataset.description_hi,
                    "created_at": dataset.created_at,
                    "updated_at": dataset.updated_at,
                }
            )
        return item

    async def get_public_dataset(
        self, session: AsyncSession, slug: str, *, include_internal: bool = True
    ) -> dict[str, Any]:
        row = await session.scalar(select(PublicDataset).where(PublicDataset.slug == slug))
        if row is None:
            raise PublicDataError("dataset not found", 404, "dataset_not_found")
        item = self._dataset_item(row, session, include_internal=include_internal)
        versions = (
            (
                await session.execute(
                    select(PublicDatasetVersion)
                    .where(PublicDatasetVersion.dataset_id == row.id)
                    .order_by(PublicDatasetVersion.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        lineage = (
            (
                await session.execute(
                    select(PublicDatasetLineage)
                    .where(PublicDatasetLineage.dataset_id == row.id)
                    .order_by(PublicDatasetLineage.step_order.asc())
                )
            )
            .scalars()
            .all()
        )
        item["versions"] = [
            {
                "version": v.version,
                "released_at": v.released_at,
                "record_count": v.record_count,
                "checksum_sha256": v.checksum_sha256,
                "change_summary": v.change_summary,
            }
            for v in versions
        ]
        item["lineage"] = [
            {
                "step_order": s.step_order,
                "step_name": s.step_name,
                "input_source": s.input_source,
                "description": s.description,
            }
            for s in lineage
        ]
        return item

    async def create_public_dataset(
        self, session: AsyncSession, payload: dict[str, Any], actor_id: uuid.UUID
    ) -> dict[str, Any]:
        existing = await session.scalar(
            select(PublicDataset).where(PublicDataset.slug == payload["slug"])
        )
        if existing is not None:
            raise PublicDataError(
                f"dataset slug '{payload['slug']}' already exists", 409, "dataset_slug_conflict"
            )
        row = PublicDataset(**payload)
        session.add(row)
        await session.flush()
        session.add(
            PublicDatasetVersion(
                dataset_id=row.id,
                version=row.version,
                record_count=row.record_count,
                checksum_sha256=row.checksum_sha256,
                published_by=actor_id,
            )
        )
        await session.flush()
        return self._dataset_item(row, session)

    async def update_public_dataset(
        self,
        session: AsyncSession,
        slug: str,
        payload: dict[str, Any],
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        row = await session.scalar(select(PublicDataset).where(PublicDataset.slug == slug))
        if row is None:
            raise PublicDataError("dataset not found", 404, "dataset_not_found")
        for field, value in payload.items():
            setattr(row, field, value)
        row.updated_at = _utcnow()
        await session.flush()
        return self._dataset_item(row, session)

    async def add_dataset_version(
        self, session: AsyncSession, slug: str, payload: dict[str, Any], actor_id: uuid.UUID
    ) -> dict[str, Any]:
        row = await session.scalar(select(PublicDataset).where(PublicDataset.slug == slug))
        if row is None:
            raise PublicDataError("dataset not found", 404, "dataset_not_found")
        dup = await session.scalar(
            select(PublicDatasetVersion).where(
                PublicDatasetVersion.dataset_id == row.id,
                PublicDatasetVersion.version == payload["version"],
            )
        )
        if dup is not None:
            raise PublicDataError(
                f"version {payload['version']} already exists", 409, "dataset_version_conflict"
            )
        session.add(
            PublicDatasetVersion(
                dataset_id=row.id,
                version=payload["version"],
                record_count=payload.get("record_count"),
                checksum_sha256=payload.get("checksum_sha256"),
                change_summary=payload.get("change_summary"),
                published_by=actor_id,
            )
        )
        row.version = payload["version"]
        if payload.get("record_count") is not None:
            row.record_count = payload["record_count"]
        row.updated_at = _utcnow()
        await session.flush()
        return self._dataset_item(row, session)

    async def set_dataset_lineage(
        self, session: AsyncSession, slug: str, steps: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        row = await session.scalar(select(PublicDataset).where(PublicDataset.slug == slug))
        if row is None:
            raise PublicDataError("dataset not found", 404, "dataset_not_found")
        existing = (
            (
                await session.execute(
                    select(PublicDatasetLineage).where(PublicDatasetLineage.dataset_id == row.id)
                )
            )
            .scalars()
            .all()
        )
        for existing_step in existing:
            await session.delete(existing_step)
        await session.flush()
        for step in steps:
            session.add(
                PublicDatasetLineage(
                    dataset_id=row.id,
                    step_order=step["step_order"],
                    step_name=step["step_name"],
                    input_source=step.get("input_source"),
                    description=step.get("description"),
                )
            )
        await session.flush()
        return steps

    # ------------------------------------------------------------------
    # coverage + freshness + methodology
    # ------------------------------------------------------------------

    async def coverage(self, session: AsyncSession) -> dict[str, Any]:
        key = "coverage"
        cached = self._cached(key)
        if isinstance(cached, dict):
            return cached

        types = (
            (await session.execute(select(GeographyType).order_by(GeographyType.sort_order.asc())))
            .scalars()
            .all()
        )
        levels: list[dict[str, Any]] = []
        for gt in types:
            geo_ids = (
                await session.scalars(select(Geography.id).where(Geography.type_id == gt.id))
            ).all()
            if not geo_ids:
                continue
            with_institutions = (
                await session.scalar(
                    select(func.count(func.distinct(Institution.geography_id))).where(
                        Institution.geography_id.in_(geo_ids),
                        Institution.deleted_at.is_(None),
                    )
                )
            ) or 0
            with_reports = (
                await session.scalar(
                    select(func.count(func.distinct(Report.boundary_id))).where(
                        Report.boundary_id.in_(geo_ids),
                        Report.visibility == "public",
                        Report.deleted_at.is_(None),
                    )
                )
            ) or 0
            with_official_data = 0
            if not levels:
                official_geos = (
                    await session.scalar(
                        select(func.count(func.distinct(Institution.geography_id))).where(
                            Institution.geography_id.in_(geo_ids),
                            Institution.source_id.is_not(None),
                            Institution.deleted_at.is_(None),
                        )
                    )
                ) or 0
                with_official_data = official_geos
            total = len(geo_ids)
            levels.append(
                {
                    "level": gt.name_key,
                    "total": total,
                    "with_institutions": int(with_institutions),
                    "with_reports": int(with_reports),
                    "with_official_data": int(with_official_data),
                    "institution_coverage_pct": round(with_institutions / total * 100, 1)
                    if total
                    else 0.0,
                    "reporting_coverage_pct": round(with_reports / total * 100, 1)
                    if total
                    else 0.0,
                }
            )
        result = {
            "generated_at": _utcnow(),
            "levels": levels,
            "overall_note": (
                "Coverage reflects where the platform has evidence today. "
                "Areas without data are not assumed problem-free."
            ),
        }
        self._cache_set(key, result)
        return result

    async def dataset_freshness(self, session: AsyncSession) -> list[dict[str, Any]]:
        rows = (
            (
                await session.execute(
                    select(PublicDataset)
                    .where(PublicDataset.status == "active")
                    .order_by(PublicDataset.last_updated_at.desc().nulls_last())
                )
            )
            .scalars()
            .all()
        )
        items: list[dict[str, Any]] = []
        for d in rows:
            items.append(
                {
                    "scope": f"dataset:{d.slug}",
                    "label": _label_freshness(d.last_updated_at, d.update_frequency),
                    "last_activity_at": d.last_updated_at,
                    "detail": d.name,
                }
            )
        last_report = await session.scalar(
            select(func.max(Report.created_at)).where(
                Report.visibility == "public", Report.deleted_at.is_(None)
            )
        )
        last_case = await session.scalar(select(func.max(CivicCase.updated_at)))
        live = datetime.now(UTC) - (last_report or datetime.min.replace(tzinfo=UTC))
        items.append(
            {
                "scope": "aggregates:reports",
                "label": "fresh" if live <= timedelta(days=_RECENT_DAYS) else "recently_updated",
                "last_activity_at": last_report,
                "detail": "Public civic report aggregates",
            }
        )
        items.append(
            {
                "scope": "aggregates:cases",
                "label": _label_freshness(last_case, "continuous"),
                "last_activity_at": last_case,
                "detail": "Department case aggregates",
            }
        )
        return items

    def methodology(self) -> dict[str, Any]:
        sections = [
            {
                "slug": "what-is-a-report",
                "title": "What is a report?",
                "body": (
                    "A report is a civic observation submitted by a citizen through "
                    "the platform — for example 'street light not working on MG Road'. "
                    "Reports are the rawest layer of Theek Karo data and reflect what "
                    "people choose to report, where they are active and how easy the "
                    "platform is to use."
                ),
            },
            {
                "slug": "what-is-verified",
                "title": "What does verified mean?",
                "body": (
                    "A report is verified when independent ground evidence (photos, "
                    "documents or an official check) confirms it. Verification separates "
                    "observed claims from confirmed issues."
                ),
            },
            {
                "slug": "what-is-resolved",
                "title": "What does resolved mean?",
                "body": (
                    "A report or case is resolved when the responsible department "
                    "submits resolution evidence and an independent reviewer accepts "
                    "it (decision 'verified'). Resolution evidence is public whenever "
                    "it is marked public."
                ),
            },
            {
                "slug": "what-is-official-data",
                "title": "What is official data?",
                "body": (
                    "Official data is information imported from a government source "
                    "such as a state education department or census publication. Every "
                    "official dataset shows its source, retrieval date and license. "
                    "Theek Karo never fabricates official numbers."
                ),
            },
            {
                "slug": "what-is-a-discrepancy",
                "title": "What is a discrepancy?",
                "body": (
                    "A discrepancy is a difference between an official value and what "
                    "citizens observe (for example official records say 10 classrooms, "
                    "citizens report 8 usable ones). Both values are shown — official "
                    "data is never overwritten."
                ),
            },
            {
                "slug": "how-metrics-are-calculated",
                "title": "How are metrics calculated?",
                "body": (
                    "Every metric on this site links to a formal definition with its "
                    "numerator, denominator and period (see the metric tables below). "
                    "Definitions come from the platform's public metric registry, not "
                    "from ad-hoc formulas."
                ),
            },
            {
                "slug": "geographic-boundaries",
                "title": "How are geographic boundaries determined?",
                "body": (
                    "Boundaries come from a documented geographic registry (states, "
                    "districts, blocks, villages…). Only boundaries from that registry "
                    "are used; informal areas are matched where the registry allows."
                ),
            },
            {
                "slug": "stale-data",
                "title": "How is stale data handled?",
                "body": (
                    "Every dataset and dashboard shows its freshness (fresh, recently "
                    "updated, may be outdated, stale). Stale data is labelled, not "
                    "hidden. Platform aggregates are computed from the latest available "
                    "records at the moment of the query."
                ),
            },
            {
                "slug": "how-ai-works",
                "title": "How does AI work here?",
                "body": (
                    "AI on this platform explains data it receives from structured "
                    "tools. It does not invent statistics: every number in an AI answer "
                    "must come from a database query performed by a tool, and the "
                    "answer cites the dataset, metric, period and geography it used."
                ),
            },
            {
                "slug": "reporting-bias",
                "title": "Reporting volume is not problem severity",
                "body": (
                    "A high reporting area may simply have more active users, better "
                    "connectivity or higher awareness. Areas with few reports are shown "
                    "as 'limited reporting data', never as problem-free."
                ),
            },
            {
                "slug": "privacy",
                "title": "Privacy in public data",
                "body": (
                    "Public datasets never include phone numbers, emails, private "
                    "addresses, exact personal locations or private media. Locations are "
                    "generalized to about one kilometre, small cells are protected, and "
                    "user identity is never linked to exported rows."
                ),
            },
        ]
        metrics: list[dict[str, Any]] = []
        for m in GLOBAL_METRIC_REGISTRY.list_metrics(role="public"):
            metrics.append(
                {
                    "metric_id": m.metric_id,
                    "name": m.name,
                    "formula": getattr(m, "description", "") or m.metric_id,
                    "explanation": getattr(m, "explanation", "") or "",
                    "source": getattr(m, "source_label", "") or "",
                }
            )
        return {
            "generated_at": _utcnow(),
            "sections": sections,
            "metrics": metrics[:40],
        }

    # ------------------------------------------------------------------
    # research queries
    # ------------------------------------------------------------------

    async def _report_stmt(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> Select[Any]:
        stmt = select(Report).where(Report.visibility == "public", Report.deleted_at.is_(None))
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        if status_filter == "open":
            stmt = stmt.where(
                Report.status.in_(
                    (
                        "submitted",
                        "under_verification",
                        "verified",
                        "assigned",
                        "in_progress",
                        "reopened",
                        "needs_information",
                    )
                )
            )
        elif status_filter == "resolved":
            stmt = stmt.where(Report.status.in_(("resolved", "community_verified", "closed")))
        if date_from:
            stmt = stmt.where(Report.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Report.created_at <= date_to)
        return stmt

    async def research_query(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        date_preset: str = "30d",
    ) -> dict[str, Any]:
        from tk_api.analytics.service import resolve_date_bounds

        start, end, period_label = resolve_date_bounds(
            date_preset, date_from, date_to, "Asia/Kolkata"
        )
        cache_key = f"query:{geography_id}:{category_slug}:{status_filter}:{start}:{end}"
        cached = self._cached(cache_key)
        if isinstance(cached, dict):
            return cached

        stmt = await self._report_stmt(
            session,
            geography_id=geography_id,
            category_slug=category_slug,
            status_filter=status_filter,
            date_from=start,
            date_to=end,
        )
        rows = (await session.execute(stmt)).scalars().all()
        total = len(rows)

        verified = 0
        resolved = 0
        open_count = 0
        trend_buckets: dict[str, dict[str, int]] = {}
        top_inst: dict[uuid.UUID, int] = {}
        cat_counts: dict[str, int] = {}
        for r in rows:
            if r.status in (
                "verified",
                "assigned",
                "in_progress",
                "resolution_submitted",
                "resolution_review",
                "resolved",
                "community_verified",
                "closed",
            ):
                verified += 1
            if r.status in ("resolved", "community_verified", "closed"):
                resolved += 1
            if r.status in (
                "submitted",
                "under_verification",
                "verified",
                "assigned",
                "in_progress",
                "reopened",
            ):
                open_count += 1
            bucket = r.created_at.astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
            entry = trend_buckets.setdefault(bucket, {"total": 0, "verified": 0, "resolved": 0})
            entry["total"] += 1
            if r.status in ("resolved", "community_verified", "closed"):
                entry["resolved"] += 1
            if r.institution_id:
                top_inst[r.institution_id] = top_inst.get(r.institution_id, 0) + 1
            if r.category_id:
                cat_counts.setdefault(str(r.category_id), 0)

        category_slugs: dict[str, str] = {}
        if rows:
            cats = (
                (
                    await session.execute(
                        select(Category).where(Category.id.in_(list(cat_counts.keys())))
                    )
                )
                .scalars()
                .all()
            )
            for c in cats:
                category_slugs[str(c.id)] = c.slug

        cat_breakdown = sorted(
            (
                {
                    "category_slug": category_slugs.get(cid),
                    "count": count,
                }
                for cid, count in cat_counts.items()
            ),
            key=lambda x: x["count"] or 0,
            reverse=True,
        )[:10]

        inst_rows = []
        if top_inst:
            insts = (
                (
                    await session.execute(
                        select(Institution).where(Institution.id.in_(list(top_inst.keys())))
                    )
                )
                .scalars()
                .all()
            )
            inst_names = {str(i.id): i.name for i in insts}
            inst_rows = sorted(
                (
                    {
                        "institution_id": str(iid),
                        "name": inst_names.get(str(iid), "unknown"),
                        "report_count": count,
                    }
                    for iid, count in top_inst.items()
                ),
                key=lambda x: cast(int, x["report_count"]),
                reverse=True,
            )[:10]

        sorted_buckets = sorted(trend_buckets.items())
        trends = [
            {
                "timestamp": bucket,
                "total_count": v["total"],
                "verified_count": v["verified"],
                "resolved_count": v["resolved"],
            }
            for bucket, v in sorted_buckets
        ]
        if len(trends) > 14:
            trends = trends[-14:]

        result = {
            "count": total,
            "verified_count": verified,
            "resolved_count": resolved,
            "open_count": open_count,
            "period_label": period_label,
            "trends": trends,
            "categories": cat_breakdown,
            "top_institutions": inst_rows,
            "coverage": {
                "period": period_label,
                "verified_pct": round(verified / total * 100, 1) if total else 0.0,
                "resolved_pct": round(resolved / total * 100, 1) if total else 0.0,
            },
            "limitations": (
                [
                    "Reporting volume reflects platform activity as well as observed issues.",
                    "Areas with few reports are shown as limited reporting data.",
                ]
            ),
            "notices": [],
            "generated_at": _utcnow(),
        }
        self._cache_set(cache_key, result)
        return result

    async def research_compare(
        self,
        session: AsyncSession,
        geography_ids: list[uuid.UUID],
        *,
        category_slug: str | None = None,
        status_filter: str | None = None,
        date_preset: str = "all",
    ) -> dict[str, Any]:
        if not 2 <= len(geography_ids) <= 5:
            raise PublicDataError(
                "compare requires between 2 and 5 geographies", 422, "invalid_compare"
            )
        geos = (
            (await session.execute(select(Geography).where(Geography.id.in_(geography_ids))))
            .scalars()
            .all()
        )
        if len(geos) != len(set(geography_ids)):
            missing = set(geography_ids) - {g.id for g in geos}
            raise PublicDataError(f"geography not found: {missing}", 404, "geography_not_found")
        items: list[dict[str, Any]] = []
        warnings: list[str] = []
        for geo in geos:
            result = await self.research_query(
                session,
                geography_id=geo.id,
                category_slug=category_slug,
                status_filter=status_filter,
                date_preset=date_preset,
            )
            inst_count = (
                await session.scalar(
                    select(func.count(Institution.id)).where(
                        Institution.geography_id == geo.id, Institution.deleted_at.is_(None)
                    )
                )
            ) or 0
            last_report = await session.scalar(
                select(func.max(Report.created_at)).where(Report.boundary_id == geo.id)
            )
            per_1000 = round(result["count"] / inst_count * 1000, 1) if inst_count else None
            notes: list[str] = []
            if inst_count == 0:
                notes.append("No mapped institutions in this geography — counts may differ.")
            items.append(
                {
                    "geography_id": geo.id,
                    "name": geo.name,
                    "report_count": result["count"],
                    "verified_count": result["verified_count"],
                    "resolved_count": result["resolved_count"],
                    "institution_count": inst_count,
                    "reports_per_1000_institutions": per_1000,
                    "last_report_at": last_report,
                    "notes": notes,
                }
            )
        if len(items) >= 2:
            counts = [i["institution_count"] for i in items]
            if max(counts) > 0 and min(counts) != max(counts):
                warnings.append(
                    "Institution counts differ between geographies — compare per-1,000-"
                    "institution rates rather than absolute counts where possible."
                )
            last_dates = [i["last_report_at"] for i in items]
            if (
                last_dates
                and None not in last_dates
                and max(last_dates) - min(last_dates) > timedelta(days=_MAYBE_STALE_DAYS)
            ):
                warnings.append("Data freshness differs between the compared geographies.")
        return {
            "generated_at": _utcnow(),
            "items": items,
            "warnings": warnings,
            "methodology_note": (
                "Counts use public reports only. Population denominators are never "
                "invented; normalized rates use mapped institution counts when valid."
            ),
        }

    async def research_trends(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        metric: str = "reports",
        interval: str = "month",
        date_preset: str = "90d",
    ) -> dict[str, Any]:
        allowed_metric = metric if metric in ("reports", "verified", "resolved") else "reports"
        result = await self.research_query(
            session,
            geography_id=geography_id,
            category_slug=category_slug,
            date_preset=date_preset,
        )
        series: list[dict[str, Any]] = []
        for point in result["trends"]:
            value = point[
                {
                    "reports": "total_count",
                    "verified": "verified_count",
                    "resolved": "resolved_count",
                }[allowed_metric]
            ]
            series.append({"timestamp": point["timestamp"], "value": value})
        current_total = sum(p["value"] for p in series)
        prev_total = sum(p["value"] for p in series[:-1]) if len(series) > 1 else 0
        change_count = result["count"]
        change_pct: float | None = None
        if len(series) >= 2 and prev_total:
            change_pct = round((current_total - prev_total) / prev_total * 100, 1)
        return {
            "metric": allowed_metric,
            "geography_id": geography_id,
            "category_slug": category_slug,
            "period_label": result["period_label"],
            "series": series,
            "change_count": change_count,
            "change_pct": change_pct,
            "generated_at": _utcnow(),
        }

    # ------------------------------------------------------------------
    # exports
    # ------------------------------------------------------------------

    async def _citizen_rows(
        self,
        session: AsyncSession,
        filters: dict[str, Any],
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        stmt = select(Report).where(Report.visibility == "public", Report.deleted_at.is_(None))
        geo = filters.get("geography_id") or filters.get("boundary_id")
        if geo:
            stmt = stmt.where(Report.boundary_id == uuid.UUID(str(geo)))
        if filters.get("category_slug"):
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == filters["category_slug"]
            )
        if filters.get("status"):
            stmt = stmt.where(Report.status == filters["status"])
        if filters.get("institution_type_id"):
            stmt = stmt.join(Institution, Report.institution_id == Institution.id).where(
                Institution.institution_type_id == uuid.UUID(str(filters["institution_type_id"]))
            )
        if filters.get("date_from"):
            stmt = stmt.where(
                Report.created_at >= datetime.fromisoformat(str(filters["date_from"]))
            )
        if filters.get("date_to"):
            stmt = stmt.where(Report.created_at <= datetime.fromisoformat(str(filters["date_to"])))
        stmt = stmt.order_by(Report.created_at.desc())
        rows = (await session.execute(stmt)).scalars().all()
        if limit:
            rows = rows[:limit]

        cats: dict[uuid.UUID, str] = {}
        issue_slugs: dict[uuid.UUID, str] = {}
        cat_ids = {r.category_id for r in rows}
        issue_ids = {r.issue_type_id for r in rows if r.issue_type_id}
        if cat_ids:
            for c in (
                await session.execute(select(Category).where(Category.id.in_(cat_ids)))
            ).scalars():
                cats[c.id] = c.slug
        if issue_ids:
            for i in (
                await session.execute(select(IssueType).where(IssueType.id.in_(issue_ids)))
            ).scalars():
                issue_slugs[i.id] = i.slug

        out: list[dict[str, Any]] = []
        for r in rows:
            loc = r.location
            if isinstance(loc, str):
                with contextlib.suppress(Exception):
                    loc = json.loads(loc)
            coords = loc.get("coordinates") if isinstance(loc, dict) and loc else None
            lon, lat = _generalize_coords(
                coords[0] if coords and len(coords) >= 2 else None,
                coords[1] if coords and len(coords) >= 2 else None,
            )
            out.append(
                {
                    "id": str(r.id),
                    "ticket_no": r.ticket_no,
                    "title": r.title,
                    "description": r.description,
                    "category_slug": cats.get(r.category_id),
                    "issue_type_slug": (
                        issue_slugs.get(r.issue_type_id) if r.issue_type_id else None
                    ),
                    "status": r.status,
                    "severity": r.severity,
                    "boundary_id": str(r.boundary_id) if r.boundary_id else None,
                    "institution_id": str(r.institution_id) if r.institution_id else None,
                    "generalized_lat": lat,
                    "generalized_lon": lon,
                    "created_at": r.created_at.isoformat(),
                    "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                    "resolution_verified_at": (
                        r.resolution_verified_at.isoformat() if r.resolution_verified_at else None
                    ),
                    "trust_score": float(r.trust_score or 0),
                }
            )
        return out

    async def _institution_rows(
        self, session: AsyncSession, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        stmt = select(Institution).where(Institution.deleted_at.is_(None))
        if filters.get("geography_id"):
            stmt = stmt.where(Institution.geography_id == uuid.UUID(str(filters["geography_id"])))
        if filters.get("institution_type_id"):
            stmt = stmt.where(
                Institution.institution_type_id == uuid.UUID(str(filters["institution_type_id"]))
            )
        if filters.get("operational_status"):
            stmt = stmt.where(Institution.operational_status == filters["operational_status"])
        rows = (await session.execute(stmt.order_by(Institution.name.asc()))).scalars().all()

        types: dict[uuid.UUID, str] = {}
        type_ids = {r.institution_type_id for r in rows}
        if type_ids:
            for t in (
                await session.execute(
                    select(InstitutionType).where(InstitutionType.id.in_(type_ids))
                )
            ).scalars():
                types[t.id] = t.code
        out: list[dict[str, Any]] = []
        for r in rows:
            loc = r.meta or {}
            coords = loc.get("coordinates") or {}
            out.append(
                {
                    "id": str(r.id),
                    "name": r.name,
                    "type_code": types.get(r.institution_type_id),
                    "geography_id": str(r.geography_id) if r.geography_id else None,
                    "official_identifier": r.official_identifier,
                    "operational_status": r.operational_status,
                    "verification_state": r.verification_state,
                    "lat": coords.get("lat") or None,
                    "lon": coords.get("lon") or None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                }
            )
        return out

    async def _resolution_rows(
        self, session: AsyncSession, filters: dict[str, Any], *, limit: int = 2000
    ) -> list[dict[str, Any]]:
        stmt = select(ResolutionSubmission)
        if filters.get("department_id"):
            stmt = stmt.join(CivicCase, ResolutionSubmission.case_id == CivicCase.id).where(
                CivicCase.primary_department_id == uuid.UUID(str(filters["department_id"]))
            )
        if filters.get("ids"):
            stmt = stmt.where(
                ResolutionSubmission.id.in_([uuid.UUID(str(i)) for i in filters["ids"]])
            )
        if filters.get("status"):
            stmt = stmt.where(ResolutionSubmission.status == filters["status"])
        rows = (
            (
                await session.execute(
                    stmt.order_by(ResolutionSubmission.submitted_at.desc()).limit(limit)
                )
            )
            .scalars()
            .all()
        )
        case_ids = {s.case_id for s in rows if s.case_id}
        report_ids = {s.report_id for s in rows}
        cases: dict[uuid.UUID, Any] = {}
        reports: dict[uuid.UUID, str] = {}
        depts: dict[uuid.UUID, str] = {}
        if case_ids:
            for c in (
                await session.execute(select(CivicCase).where(CivicCase.id.in_(case_ids)))
            ).scalars():
                cases[c.id] = c
        if report_ids:
            for r in (
                await session.execute(select(Report).where(Report.id.in_(report_ids)))
            ).scalars():
                reports[r.id] = r.ticket_no
        dept_ids = {c.primary_department_id for c in cases.values() if c.primary_department_id}
        if dept_ids:
            for d in (
                await session.execute(select(Department).where(Department.id.in_(dept_ids)))
            ).scalars():
                depts[d.id] = d.name

        evidence_counts: dict[uuid.UUID, int] = {}
        if rows:
            sub_ids = [s.id for s in rows]
            ev = (
                await session.execute(
                    select(ResolutionEvidence.resolution_submission_id, func.count())
                    .where(ResolutionEvidence.resolution_submission_id.in_(sub_ids))
                    .group_by(ResolutionEvidence.resolution_submission_id)
                )
            ).all()
            for sub_id, count in ev:
                evidence_counts[sub_id] = count

        reviews: dict[uuid.UUID, Any] = {}
        if rows:
            rev = (
                (
                    await session.execute(
                        select(ResolutionReview)
                        .where(ResolutionReview.resolution_submission_id.in_([s.id for s in rows]))
                        .order_by(ResolutionReview.reviewed_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            for review in rev:
                reviews.setdefault(review.resolution_submission_id, review)

        out: list[dict[str, Any]] = []
        for s in rows:
            case = cases.get(s.case_id) if s.case_id else None
            latest_review = reviews.get(s.id)
            out.append(
                {
                    "case_no": case.case_no if case else None,
                    "report_ticket_no": reports.get(s.report_id),
                    "case_status": case.status if case else None,
                    "department_name": depts.get(case.primary_department_id)
                    if case and case.primary_department_id
                    else None,
                    "submitted_at": s.submitted_at.isoformat(),
                    "resolution_date": s.resolution_date.isoformat() if s.resolution_date else None,
                    "decision": latest_review.decision if latest_review else None,
                    "resolution_verified_at": (
                        case.resolution_verified_at.isoformat()
                        if case and case.resolution_verified_at
                        else None
                    ),
                    "evidence_count": evidence_counts.get(s.id, 0),
                    "public_evidence": True,
                }
            )
        return out

    async def _statistics_rows(
        self, session: AsyncSession, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        coverage = await self.coverage(session)
        rows: list[dict[str, Any]] = []
        for level in coverage["levels"]:
            rows.append(
                {
                    "level": level["level"],
                    "total": level["total"],
                    "with_institutions": level["with_institutions"],
                    "with_reports": level["with_reports"],
                    "institution_coverage_pct": level["institution_coverage_pct"],
                    "reporting_coverage_pct": level["reporting_coverage_pct"],
                }
            )
        return rows

    async def count_rows(self, session: AsyncSession, kind: str, filters: dict[str, Any]) -> int:
        if kind == "citizen_reports":
            return len(await self._citizen_rows(session, filters, limit=100000))
        if kind == "institutions":
            return len(await self._institution_rows(session, filters))
        if kind == "resolutions":
            return len(await self._resolution_rows(session, filters))
        if kind == "statistics":
            return len(await self._statistics_rows(session, filters))
        raise PublicDataError(f"unknown export kind {kind}", 422, "invalid_export_kind")

    async def _rows_for_kind(
        self, session: AsyncSession, kind: str, filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if kind == "citizen_reports":
            return await self._citizen_rows(session, filters)
        if kind == "institutions":
            return await self._institution_rows(session, filters)
        if kind == "resolutions":
            return await self._resolution_rows(session, filters)
        if kind == "statistics":
            return await self._statistics_rows(session, filters)
        raise PublicDataError(f"unknown export kind {kind}", 422, "invalid_export_kind")

    def _serialize(self, rows: list[dict[str, Any]], fmt: str) -> tuple[str, str]:
        if fmt == "json":
            return json.dumps(rows, ensure_ascii=False, default=str), "application/json"
        if not rows:
            return "", "text/csv"
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: v for k, v in row.items() if k in list(rows[0].keys())})
        return buffer.getvalue(), "text/csv"

    async def create_export_job(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID | None,
        kind: str,
        fmt: str,
        filters: dict[str, Any],
    ) -> dict[str, Any]:
        if fmt not in _EXPORT_FORMATS:
            raise PublicDataError("format must be csv or json", 422, "invalid_export_format")
        row_count = await self.count_rows(session, kind, filters)
        job = DataExportJob(
            user_id=user_id,
            kind=kind,
            format=fmt,
            filters=filters,
            row_count=row_count,
            status="queued",
        )
        session.add(job)
        await session.flush()
        payload = self._job_payload(job)
        payload["sync"] = row_count <= _SYNC_EXPORT_MAX_ROWS
        return payload

    @staticmethod
    def _job_payload(job: DataExportJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "kind": job.kind,
            "format": job.format,
            "filters": job.filters,
            "row_count": job.row_count,
            "status": job.status,
            "requested_at": job.requested_at,
            "completed_at": job.completed_at,
            "download_url": None,
            "expires_at": job.file_url_expires_at,
            "error": job.error,
        }

    async def get_export_job(self, session: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
        job = await session.get(DataExportJob, job_id)
        if job is None:
            raise PublicDataError("export job not found", 404, "export_job_not_found")
        payload = self._job_payload(job)
        return payload

    async def _finalize_job(
        self,
        session: AsyncSession,
        job: DataExportJob,
        *,
        settings: Any,
        storage: Any,
    ) -> dict[str, Any]:
        rows = await self._rows_for_kind(session, job.kind, job.filters or {})
        content, _mime = self._serialize(rows, job.format)
        bucket = getattr(settings, "media_exports_bucket", "tk-exports")
        key = f"exports/{job.kind}/{job.id}.{job.format}"
        storage.save_bytes(bucket, key, content.encode("utf-8"))
        job.status = "ready"
        job.completed_at = _utcnow()
        job.file_key = key
        job.row_count = len(rows)
        job.file_url_expires_at = _utcnow() + timedelta(hours=24)
        await session.flush()
        return self._job_payload(job)

    async def run_export(
        self, session: AsyncSession, job: DataExportJob, *, settings: Any, storage: Any
    ) -> dict[str, Any]:
        try:
            job.status = "generating"
            await session.flush()
            return await self._finalize_job(session, job, settings=settings, storage=storage)
        except PublicDataError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            job.status = "failed"
            job.error = str(exc)[:400]
            await session.flush()
            return self._job_payload(job)

    async def download_url_for_job(
        self, session: AsyncSession, job_id: uuid.UUID, *, storage: Any, settings: Any
    ) -> dict[str, Any]:
        job = await session.get(DataExportJob, job_id)
        if job is None:
            raise PublicDataError("export job not found", 404, "export_job_not_found")
        if job.status != "ready" or not job.file_key:
            raise PublicDataError("export not ready", 409, "export_not_ready")
        if job.file_url_expires_at and datetime.now(UTC) > job.file_url_expires_at:
            job.status = "expired"
            await session.flush()
            raise PublicDataError("export link expired", 410, "export_link_expired")
        bucket = getattr(settings, "media_exports_bucket", "tk-exports")
        url = storage.download_url(bucket, job.file_key, expires_seconds=900)
        return {"download_url": url, "expires_in_seconds": 900}

    # ------------------------------------------------------------------
    # corrections
    # ------------------------------------------------------------------

    async def create_correction(
        self, session: AsyncSession, user_id: uuid.UUID, payload: dict[str, Any]
    ) -> dict[str, Any]:
        existing = await session.scalar(
            select(DataCorrectionRequest).where(
                DataCorrectionRequest.user_id == user_id,
                DataCorrectionRequest.target_type == payload["target_type"],
                DataCorrectionRequest.target_id == payload["target_id"],
                DataCorrectionRequest.status == "pending",
            )
        )
        if existing is not None:
            raise PublicDataError(
                "you already have a pending correction for this target", 409, "duplicate_correction"
            )
        row = DataCorrectionRequest(user_id=user_id, **payload)
        session.add(row)
        await session.flush()
        return self._correction_payload(row)

    async def list_corrections(
        self, session: AsyncSession, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = select(DataCorrectionRequest).order_by(DataCorrectionRequest.created_at.desc())
        if status:
            stmt = stmt.where(DataCorrectionRequest.status == status)
        rows = (await session.execute(stmt)).scalars().all()
        return [self._correction_payload(r) for r in rows]

    async def list_my_corrections(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = (
            (
                await session.execute(
                    select(DataCorrectionRequest)
                    .where(DataCorrectionRequest.user_id == user_id)
                    .order_by(DataCorrectionRequest.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [self._correction_payload(r) for r in rows]

    @staticmethod
    def _correction_payload(row: DataCorrectionRequest) -> dict[str, Any]:
        return {
            "id": row.id,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "target_name": row.target_name,
            "field": row.field,
            "current_value": row.current_value,
            "suggested_value": row.suggested_value,
            "reason": row.reason,
            "evidence": row.evidence,
            "status": row.status,
            "decision_note": row.decision_note,
            "created_at": row.created_at,
            "decided_at": row.decided_at,
        }

    async def review_correction(
        self,
        session: AsyncSession,
        correction_id: uuid.UUID,
        *,
        decision: str,
        note: str | None,
        actor_id: uuid.UUID,
    ) -> dict[str, Any]:
        row = await session.get(DataCorrectionRequest, correction_id)
        if row is None:
            raise PublicDataError("correction request not found", 404, "correction_not_found")
        if row.status != "pending":
            raise PublicDataError("correction already decided", 409, "correction_decided")
        row.status = decision
        row.decided_by = actor_id
        row.decided_at = _utcnow()
        row.decision_note = note
        row.updated_at = _utcnow()
        await session.flush()
        return self._correction_payload(row)

    # ------------------------------------------------------------------
    # saved research queries
    # ------------------------------------------------------------------

    async def save_query(
        self, session: AsyncSession, user_id: uuid.UUID, name: str, filters: dict[str, Any]
    ) -> dict[str, Any]:
        row = SavedResearchQuery(user_id=user_id, name=name, filters=filters)
        session.add(row)
        await session.flush()
        return self._saved_payload(row)

    async def list_saved_queries(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = (
            (
                await session.execute(
                    select(SavedResearchQuery)
                    .where(SavedResearchQuery.user_id == user_id)
                    .order_by(SavedResearchQuery.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [self._saved_payload(r) for r in rows]

    async def delete_saved_query(
        self, session: AsyncSession, query_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        row = await session.get(SavedResearchQuery, query_id)
        if row is None or row.user_id != user_id:
            raise PublicDataError("saved query not found", 404, "saved_query_not_found")
        await session.delete(row)
        await session.flush()

    @staticmethod
    def _saved_payload(row: SavedResearchQuery) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "filters": row.filters,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------
    # API keys + usage
    # ------------------------------------------------------------------

    async def create_api_key(
        self, session: AsyncSession, user_id: uuid.UUID, name: str, quota_per_hour: int
    ) -> dict[str, Any]:
        import hashlib
        import secrets

        secret = "tk_" + secrets.token_urlsafe(32)
        prefix = secret[:8]
        key_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        row = PublicApiKey(
            user_id=user_id,
            name=name,
            key_prefix=prefix,
            key_hash=key_hash,
            quota_per_hour=quota_per_hour,
        )
        session.add(row)
        await session.flush()
        payload = self._api_key_payload(row)
        payload["key"] = secret
        return payload

    async def list_api_keys(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        rows = (
            (
                await session.execute(
                    select(PublicApiKey)
                    .where(PublicApiKey.user_id == user_id)
                    .order_by(PublicApiKey.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
        return [self._api_key_payload(r) for r in rows]

    async def revoke_api_key(
        self, session: AsyncSession, key_id: uuid.UUID, user_id: uuid.UUID
    ) -> dict[str, Any]:
        row = await session.get(PublicApiKey, key_id)
        if row is None or row.user_id != user_id:
            raise PublicDataError("api key not found", 404, "api_key_not_found")
        row.status = "revoked"
        row.revoked_at = _utcnow()
        await session.flush()
        return self._api_key_payload(row)

    @staticmethod
    def _api_key_payload(row: PublicApiKey) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "key_prefix": row.key_prefix,
            "status": row.status,
            "quota_per_hour": row.quota_per_hour,
            "created_at": row.created_at,
            "last_used_at": row.last_used_at,
        }

    async def resolve_api_key(self, session: AsyncSession, secret: str) -> PublicApiKey | None:
        import hashlib

        key_hash = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        row = await session.scalar(select(PublicApiKey).where(PublicApiKey.key_hash == key_hash))
        if row is None or row.status != "active":
            return None
        row.last_used_at = _utcnow()
        await session.flush()
        return row

    async def record_usage(
        self,
        session: AsyncSession,
        *,
        key: PublicApiKey | None,
        user: User | None,
        endpoint: str,
        method: str,
        status_code: int,
        latency_ms: int,
        client_ip: str | None,
    ) -> None:
        session.add(
            PublicApiUsage(
                key_id=key.id if key else None,
                user_id=user.id if user else None,
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                latency_ms=latency_ms,
                client_ip=client_ip,
            )
        )
        await session.flush()

    async def usage_summary(self, session: AsyncSession, *, days: int = 7) -> dict[str, Any]:
        since = _utcnow() - timedelta(days=days)
        total = (
            await session.scalar(
                select(func.count(PublicApiUsage.id)).where(PublicApiUsage.created_at >= since)
            )
        ) or 0
        rows = (
            await session.execute(
                select(
                    PublicApiUsage.endpoint,
                    func.count(PublicApiUsage.id),
                    func.sum(func.case((PublicApiUsage.status_code >= 400, 1), else_=0)),
                    func.percentile_cont(0.95).within_group(PublicApiUsage.latency_ms),
                )
                .where(PublicApiUsage.created_at >= since)
                .group_by(PublicApiUsage.endpoint)
                .order_by(func.count(PublicApiUsage.id).desc())
            )
        ).all()
        buckets = [
            {
                "endpoint": endpoint,
                "requests": int(count),
                "errors": int(errors or 0),
                "latency_ms_p95": int(p95 or 0),
            }
            for endpoint, count, errors, p95 in rows
        ]
        return {"generated_at": _utcnow(), "total_requests": int(total), "buckets": buckets}

    # ------------------------------------------------------------------
    # public queries (reports, institutions, resolutions, departments)
    # ------------------------------------------------------------------

    async def public_reports(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 50,
        category_slug: str | None = None,
        status: str | None = None,
        geography_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        stmt = select(Report).where(Report.visibility == "public", Report.deleted_at.is_(None))
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        if status:
            stmt = stmt.where(Report.status == status)
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        total = (await session.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
        rows = (
            (
                await session.execute(
                    stmt.order_by(Report.created_at.desc())
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            )
            .scalars()
            .all()
        )
        cat_ids = {r.category_id for r in rows}
        cats: dict[uuid.UUID, str] = {}
        if cat_ids:
            for c in (
                await session.execute(select(Category).where(Category.id.in_(cat_ids)))
            ).scalars():
                cats[c.id] = c.slug
        items = [
            {
                "id": str(r.id),
                "ticket_no": r.ticket_no,
                "title": r.title,
                "category_slug": cats.get(r.category_id),
                "status": r.status,
                "severity": r.severity,
                "boundary_id": str(r.boundary_id) if r.boundary_id else None,
                "institution_id": str(r.institution_id) if r.institution_id else None,
                "lat": None,
                "lon": None,
                "created_at": r.created_at,
                "resolved_at": r.resolved_at,
                "resolution_verified_at": r.resolution_verified_at,
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def public_institutions(
        self,
        session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 50,
        geography_id: uuid.UUID | None = None,
        type_code: str | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(Institution).where(Institution.deleted_at.is_(None))
        if geography_id:
            stmt = stmt.where(Institution.geography_id == geography_id)
        if type_code:
            stmt = stmt.join(
                InstitutionType, Institution.institution_type_id == InstitutionType.id
            ).where(InstitutionType.code == type_code)
        if q:
            stmt = stmt.where(Institution.normalized_name.ilike(f"%{q}%"))
        total = (await session.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
        rows = (
            (
                await session.execute(
                    stmt.order_by(Institution.name.asc())
                    .limit(page_size)
                    .offset((page - 1) * page_size)
                )
            )
            .scalars()
            .all()
        )
        types = {
            t.id: t.code
            for t in (
                await session.execute(
                    select(InstitutionType).where(
                        InstitutionType.id.in_({r.institution_type_id for r in rows})
                    )
                )
            ).scalars()
        }
        items = [
            {
                "id": str(r.id),
                "name": r.name,
                "type_code": types.get(r.institution_type_id),
                "geography_id": str(r.geography_id) if r.geography_id else None,
                "official_identifier": r.official_identifier,
                "operational_status": r.operational_status,
                "verification_state": r.verification_state,
                "lat": None,
                "lon": None,
            }
            for r in rows
        ]
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    async def public_resolutions(
        self, session: AsyncSession, *, page: int = 1, page_size: int = 50
    ) -> dict[str, Any]:
        stmt = select(ResolutionSubmission).order_by(ResolutionSubmission.submitted_at.desc())
        total = (await session.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
        rows = (
            (await session.execute(stmt.limit(page_size).offset((page - 1) * page_size)))
            .scalars()
            .all()
        )
        out = await self._resolution_rows(session, {"ids": [s.id for s in rows]}, limit=page_size)
        return {"items": out, "total": total, "page": page, "page_size": page_size}

    async def public_geographies(
        self,
        session: AsyncSession,
        *,
        type_code: str | None = None,
        parent_id: uuid.UUID | None = None,
        q: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(Geography)
        if type_code:
            stmt = stmt.join(GeographyType, Geography.type_id == GeographyType.id).where(
                GeographyType.code == type_code
            )
        if parent_id:
            stmt = stmt.where(Geography.parent_id == parent_id)
        if q:
            stmt = stmt.where(Geography.name.ilike(f"%{q.strip()}%"))
        rows = (await session.execute(stmt.order_by(Geography.name.asc()))).scalars().all()
        type_codes = {
            t.id: t.code for t in (await session.execute(select(GeographyType))).scalars()
        }
        items = [
            {
                "id": str(g.id),
                "type_code": type_codes.get(g.type_id),
                "name": g.name,
                "parent_id": str(g.parent_id) if g.parent_id else None,
                "child_count": 0,
                "has_boundary": False,
            }
            for g in rows
        ]
        return {"items": items, "total": len(items)}

    async def public_departments(self, session: AsyncSession) -> dict[str, Any]:
        rows = (
            (
                await session.execute(
                    select(Department)
                    .where(Department.status == "active")
                    .order_by(Department.name)
                )
            )
            .scalars()
            .all()
        )
        items: list[dict[str, Any]] = []
        for d in rows:
            assigned = (
                await session.scalar(
                    select(func.count(CivicCase.id)).where(CivicCase.primary_department_id == d.id)
                )
            ) or 0
            members = (
                await session.scalar(
                    select(func.count(DepartmentUser.id)).where(
                        DepartmentUser.department_id == d.id,
                        DepartmentUser.is_active.is_(True),
                    )
                )
            ) or 0
            items.append(
                {
                    "id": str(d.id),
                    "slug": d.slug,
                    "name": d.name,
                    "type_name": None,
                    "status": d.status,
                    "member_count": members,
                    "case_assigned_count": assigned,
                }
            )
        return {"items": items, "total": len(items)}

    async def department_public_profile(
        self, session: AsyncSession, department_id: uuid.UUID
    ) -> dict[str, Any]:
        dept = await session.get(Department, department_id)
        if dept is None or dept.status == "archived":
            raise PublicDataError("department not found", 404, "department_not_found")
        assigned = (
            await session.scalar(
                select(func.count(CivicCase.id)).where(CivicCase.primary_department_id == dept.id)
            )
        ) or 0
        acknowledged = (
            await session.scalar(
                select(func.count(CivicCase.id)).where(
                    CivicCase.primary_department_id == dept.id,
                    CivicCase.status.in_(
                        (
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
                        )
                    ),
                )
            )
        ) or 0
        resolved = (
            await session.scalar(
                select(func.count(CivicCase.id)).where(
                    CivicCase.primary_department_id == dept.id,
                    CivicCase.status.in_(("resolved", "closed", "partially_resolved")),
                )
            )
        ) or 0
        verified_resolutions = (
            await session.scalar(
                select(func.count(CivicCase.id)).where(
                    CivicCase.primary_department_id == dept.id,
                    CivicCase.resolution_verified_at.is_not(None),
                )
            )
        ) or 0

        sla_compliant = 0
        sla_total = 0
        from tk_api.cases.models import SlaInstance

        sla_rows = (
            await session.execute(
                select(SlaInstance.status)
                .join(CivicCase, SlaInstance.case_id == CivicCase.id)
                .where(CivicCase.primary_department_id == dept.id)
            )
        ).all()
        for (status,) in sla_rows:
            sla_total += 1
            if status in ("closed", "exempt"):
                sla_compliant += 1
        sla_rate = round(sla_compliant / sla_total * 100, 1) if sla_total else None

        response_times: list[float] = []
        resolution_times: list[float] = []
        from tk_api.cases.models import CaseResponse, CaseStatusHistory

        case_ids = (
            await session.scalars(
                select(CivicCase.id).where(CivicCase.primary_department_id == dept.id)
            )
        ).all()
        if case_ids:
            resp = (
                await session.execute(
                    select(CaseResponse.case_id, func.min(CaseResponse.created_at))
                    .where(
                        CaseResponse.case_id.in_(case_ids),
                        CaseResponse.visibility == "public",
                    )
                    .group_by(CaseResponse.case_id)
                )
            ).all()
            created = {
                c.id: c.created_at
                for c in (
                    await session.execute(
                        select(CivicCase.id, CivicCase.created_at).where(CivicCase.id.in_(case_ids))
                    )
                ).all()
            }
            for cid, first_resp in resp:
                created_at = created.get(cid)
                if created_at:
                    response_times.append((first_resp - created_at).total_seconds() / 3600)
            history = (
                await session.execute(
                    select(CaseStatusHistory.case_id, func.min(CaseStatusHistory.created_at))
                    .where(
                        CaseStatusHistory.case_id.in_(case_ids),
                        CaseStatusHistory.to_status.in_(("resolved", "closed")),
                    )
                    .group_by(CaseStatusHistory.case_id)
                )
            ).all()
            for cid, resolved_at in history:
                created_at = created.get(cid)
                if created_at:
                    resolution_times.append((resolved_at - created_at).total_seconds() / 3600)

        def _median(values: list[float]) -> float | None:
            if not values:
                return None
            ordered = sorted(values)
            mid = len(ordered) // 2
            if len(ordered) % 2:
                return round(ordered[mid], 1)
            return round((ordered[mid - 1] + ordered[mid]) / 2, 1)

        item = {
            "id": str(dept.id),
            "slug": dept.slug,
            "name": dept.name,
            "type_name": None,
            "status": dept.status,
            "member_count": 0,
            "case_assigned_count": assigned,
        }
        metrics = {
            "case_assigned_count": int(assigned),
            "acknowledged_count": int(acknowledged),
            "resolved_count": int(resolved),
            "verified_resolution_count": int(verified_resolutions),
            "response_rate_pct": round(acknowledged / assigned * 100, 1) if assigned else None,
            "median_response_hours": _median(response_times),
            "median_resolution_hours": _median(resolution_times),
            "sla_compliance_pct": sla_rate,
        }
        limitations: list[str] = []
        if not assigned:
            limitations.append("No comparable case history for this department yet.")
        if sla_rate is None:
            limitations.append("SLA history insufficient for compliance measurement.")
        return {
            "department": item,
            "metrics": metrics,
            "methodology_note": (
                "System-level transparency only: no individual employee "
                "performance or departmental rankings are published."
            ),
            "limitations": limitations,
            "generated_at": _utcnow(),
        }

    async def india_statistics(self, session: AsyncSession) -> dict[str, Any]:
        cache_key = "india_stats"
        cached = self._cached(cache_key)
        if isinstance(cached, dict):
            return cached
        states = (
            await session.scalar(
                select(func.count(Geography.id))
                .join(GeographyType, Geography.type_id == GeographyType.id)
                .where(GeographyType.code == "state")
            )
        ) or 0
        districts = (
            await session.scalar(
                select(func.count(Geography.id))
                .join(GeographyType, Geography.type_id == GeographyType.id)
                .where(GeographyType.code == "district")
            )
        ) or 0
        institutions = (
            await session.scalar(
                select(func.count(Institution.id)).where(Institution.deleted_at.is_(None))
            )
        ) or 0
        reports = (
            await session.scalar(
                select(func.count(Report.id)).where(
                    Report.visibility == "public", Report.deleted_at.is_(None)
                )
            )
        ) or 0
        verified = (
            await session.scalar(
                select(func.count(Report.id)).where(
                    Report.visibility == "public",
                    Report.deleted_at.is_(None),
                    Report.status.in_(
                        (
                            "verified",
                            "assigned",
                            "in_progress",
                            "resolution_submitted",
                            "resolution_review",
                            "resolved",
                            "community_verified",
                            "closed",
                        )
                    ),
                )
            )
        ) or 0
        open_cases = (
            await session.scalar(
                select(func.count(CivicCase.id)).where(
                    CivicCase.status.in_(
                        (
                            "submitted",
                            "under_review",
                            "needs_information",
                            "verified",
                            "assigned",
                            "acknowledged",
                            "action_planned",
                            "in_progress",
                            "waiting_for_information",
                        )
                    )
                )
            )
        ) or 0
        verified_resolutions = (
            await session.scalar(
                select(func.count(CivicCase.id)).where(
                    CivicCase.resolution_verified_at.is_not(None)
                )
            )
        ) or 0
        datasets = (
            await session.scalar(
                select(func.count(PublicDataset.id)).where(PublicDataset.status == "active")
            )
        ) or 0
        result = {
            "generated_at": _utcnow(),
            "stats": {
                "states_covered": int(states),
                "districts_covered": int(districts),
                "institutions_mapped": int(institutions),
                "public_reports": int(reports),
                "verified_reports": int(verified),
                "open_cases": int(open_cases),
                "verified_resolutions": int(verified_resolutions),
                "public_datasets": int(datasets),
            },
        }
        self._cache_set(cache_key, result)
        return result
