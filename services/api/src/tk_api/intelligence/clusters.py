"""Issue clustering + recurrence engines (Phase 20, docs/INTELLIGENCE-METHODOLOGY.md).

Clustering groups *related* public reports into issue clusters using a
deterministic, documented key: (geography or institution) + category within a
sliding observation window, plus a normalized near-duplicate text signal.
Individual reports are never deleted or merged by the engine — a cluster is a
read-only summary view (the platform decision on duplicates stays human,
reusing the existing duplicate/report-moderation machinery).

Recurrence looks at the same institution/category appearing across distinct
calendar months, so "water issue reported in May, June, July, August" is
surfaced as a recurring-issue pattern.
"""

from __future__ import annotations

import difflib
import itertools
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Category, IssueType
from tk_api.geography.models import Geography
from tk_api.institutions.models import Institution
from tk_api.intelligence.models import IssueCluster
from tk_api.intelligence.schemas import (
    ClusterItem,
    ClusterResponse,
    RecurringIssueItem,
    RecurringIssueResponse,
)
from tk_api.reports.models import Report

DEFAULT_CLUSTER_WINDOW_DAYS = 30
MIN_CLUSTER_REPORTS = 3
MIN_DISTINCT_MONTHS = 3
RECURRENCE_WINDOW_MONTHS = 6

RESOLVED_STATUSES = ("resolved", "community_verified", "closed")
OPEN_STATUSES = (
    "submitted",
    "under_verification",
    "verified",
    "assigned",
    "in_progress",
    "reopened",
    "needs_information",
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    stop = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "on",
        "at",
        "to",
        "is",
        "are",
        "was",
        "were",
        "been",
        "for",
        "with",
        "from",
        "by",
        "this",
        "that",
        "report",
    }
    return {w for w in words if len(w) > 2 and w not in stop}


def text_similarity(a: str, b: str) -> float:
    """Deterministic normalized similarity in [0, 1] from token overlap + ratio."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()
    jaccard = len(ta & tb) / len(ta | tb)
    ratio = difflib.SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()
    return round(max(jaccard, ratio), 3)


class ClusterEngine:
    """Deterministic issue-cluster and duplicate-candidate grouping."""

    async def compute_clusters(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
        window_days: int = DEFAULT_CLUSTER_WINDOW_DAYS,
        min_reports: int = MIN_CLUSTER_REPORTS,
    ) -> list[dict[str, Any]]:
        """Group public reports into issue clusters and return cluster dicts."""
        now = _utcnow()
        since = now - timedelta(days=window_days)
        stmt = select(Report).where(
            Report.visibility == "public",
            Report.deleted_at.is_(None),
            Report.created_at >= since,
        )
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        if category_slug:
            stmt = stmt.join(Category, Report.category_id == Category.id).where(
                Category.slug == category_slug
            )
        reports = (await session.execute(stmt)).scalars().all()

        cats: dict[uuid.UUID, str] = {}
        if reports:
            cat_ids = {r.category_id for r in reports}
            rows = await session.execute(select(Category).where(Category.id.in_(cat_ids)))
            cats = {c.id: c.slug for c in rows.scalars()}

        clusters: list[dict[str, Any]] = []
        members: dict[str, list[Any]] = {}

        for r in reports:
            geo_key = r.boundary_id or "none"
            inst_key = r.institution_id or "none"
            cat_slug = cats.get(r.category_id) or "unknown"
            near_dup_key = None
            # Deterministic near-duplicate matching inside the same (geo,
            # institution, category) group: fold highly overlapping titles
            # together before bucketing by location/category.
            if r.institution_id:
                candidates = [
                    c
                    for c in clusters
                    if c.get("institution_id") == r.institution_id
                    and c.get("category_slug") == cat_slug
                ]
            else:
                candidates = [
                    c
                    for c in clusters
                    if c.get("geography_id") == r.boundary_id
                    and c.get("category_slug") == cat_slug
                    and c.get("institution_id") is None
                ]
            for existing in candidates:
                sample_no = existing["report_ids"][0]
                sample = next((x for x in reports if str(x.id) == str(sample_no)), None)
                if sample and text_similarity(r.title, sample.title) >= 0.75:
                    near_dup_key = existing["cluster_key"]
                    break

            key = near_dup_key or (f"{geo_key}:{inst_key}:{cat_slug}:{r.issue_type_id or 'any'}")
            if key not in members:
                members[key] = []
            members[key].append(r)

        for key, group in members.items():
            if len(group) < min_reports:
                continue
            first = min(g.created_at for g in group if g.created_at) if group else None
            last = max(g.created_at for g in group if g.created_at) if group else None
            label_parts = [cats.get(group[0].category_id) or "issue"]
            if group[0].institution_id:
                label_parts.append("at linked institution")
            elif group[0].boundary_id:
                label_parts.append("in linked geography")
            clusters.append(
                {
                    "cluster_key": key,
                    "label": " / ".join(label_parts),
                    "category_slug": cats.get(group[0].category_id),
                    "geography_id": group[0].boundary_id,
                    "institution_id": group[0].institution_id,
                    "report_ids": [str(g.id) for g in group],
                    "report_count": len(group),
                    "evidence_count": sum(
                        1 for g in group if g.trust_score and float(g.trust_score) >= 0.3
                    ),
                    "first_seen": first,
                    "last_seen": last,
                    "status": "open",
                    "near_duplicate_group": any(
                        text_similarity(a.title, b.title) >= 0.75
                        for a, b in itertools.pairwise(group)
                    ),
                }
            )
        clusters.sort(key=lambda c: c["report_count"], reverse=True)
        return clusters

    async def save_clusters(
        self, session: AsyncSession, clusters: list[dict[str, Any]]
    ) -> list[IssueCluster]:
        """Upsert issue clusters (append-only detail; existing clusters merge)."""
        saved: list[IssueCluster] = []
        for data in clusters:
            existing = await session.scalar(
                select(IssueCluster).where(IssueCluster.cluster_key == data["cluster_key"])
            )
            now = _utcnow()
            if existing is not None:
                existing.report_ids = data["report_ids"]
                existing.report_count = data["report_count"]
                existing.evidence_count = data["evidence_count"]
                existing.last_seen = data["last_seen"]
                existing.updated_at = now
                saved.append(existing)
            else:
                row = IssueCluster(
                    cluster_key=data["cluster_key"],
                    label=data["label"],
                    category_slug=data["category_slug"],
                    geography_id=data["geography_id"],
                    institution_id=data["institution_id"],
                    report_ids=data["report_ids"],
                    report_count=data["report_count"],
                    evidence_count=data["evidence_count"],
                    first_seen=data["first_seen"],
                    last_seen=data["last_seen"],
                    status="open",
                )
                session.add(row)
                saved.append(row)
        if saved:
            await session.flush()
        return saved

    async def list_clusters(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ClusterItem]:
        stmt = select(IssueCluster).order_by(IssueCluster.report_count.desc()).limit(limit)
        if geography_id:
            stmt = stmt.where(IssueCluster.geography_id == geography_id)
        if status:
            stmt = stmt.where(IssueCluster.status == status)
        rows = (await session.execute(stmt)).scalars().all()
        inst_names: dict[uuid.UUID, str] = {}
        geo_names: dict[uuid.UUID, str] = {}
        if rows:
            inst_ids = {c.institution_id for c in rows if c.institution_id}
            geo_ids = {c.geography_id for c in rows if c.geography_id}
            if inst_ids:
                for inst in (
                    await session.execute(select(Institution).where(Institution.id.in_(inst_ids)))
                ).scalars():
                    inst_names[inst.id] = inst.name
            if geo_ids:
                for geo in (
                    await session.execute(select(Geography).where(Geography.id.in_(geo_ids)))
                ).scalars():
                    geo_names[geo.id] = geo.name
        return [
            ClusterItem(
                cluster_key=c.cluster_key,
                label=c.label,
                category_slug=c.category_slug,
                geography_id=c.geography_id,
                geography_name=geo_names.get(c.geography_id) if c.geography_id else None,
                institution_id=c.institution_id,
                institution_name=(inst_names.get(c.institution_id) if c.institution_id else None),
                report_count=c.report_count,
                evidence_count=c.evidence_count,
                first_seen=c.first_seen,
                last_seen=c.last_seen,
                report_ids=[uuid.UUID(str(x)) for x in c.report_ids],
                status=c.status,
            )
            for c in rows
        ]

    async def summarize(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        category_slug: str | None = None,
    ) -> ClusterResponse:
        clusters = await self.compute_clusters(
            session, geography_id=geography_id, category_slug=category_slug
        )
        await self.save_clusters(session, clusters)
        items = await self.list_clusters(session, geography_id=geography_id, limit=50)
        return ClusterResponse(
            clusters=items,
            observation_window_days=DEFAULT_CLUSTER_WINDOW_DAYS,
            generated_at=_utcnow(),
            note=(
                "Clusters group related public reports for review. They never delete "
                "or merge individual reports; duplication decisions stay human."
            ),
        )


class RecurringIssueEngine:
    """Detect issues that repeatedly appear at the same institution/geography."""

    async def detect(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
        window_months: int = RECURRENCE_WINDOW_MONTHS,
        min_distinct_months: int = MIN_DISTINCT_MONTHS,
    ) -> list[RecurringIssueItem]:
        now = _utcnow()
        since = now - timedelta(days=window_months * 30)
        stmt = select(Report).where(
            Report.visibility == "public",
            Report.deleted_at.is_(None),
            Report.created_at >= since,
            Report.duplicate_of.is_(None),
        )
        if geography_id:
            stmt = stmt.where(Report.boundary_id == geography_id)
        reports = (await session.execute(stmt)).scalars().all()

        from zoneinfo import ZoneInfo

        groups: dict[tuple[Any, ...], dict[str, Any]] = {}
        for r in reports:
            key_month = (r.created_at or now).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m")
            if r.institution_id:
                gkey = ("inst", str(r.institution_id), r.category_id, r.issue_type_id)
            else:
                gkey = ("geo", str(r.boundary_id), r.category_id, r.issue_type_id)
            entry = groups.setdefault(
                gkey,
                {
                    "institution_id": r.institution_id,
                    "geography_id": r.boundary_id,
                    "category_id": r.category_id,
                    "issue_type_id": r.issue_type_id,
                    "months": set(),
                    "total": 0,
                    "open": 0,
                    "first_seen": None,
                    "last_seen": None,
                },
            )
            entry["months"].add(key_month)
            entry["total"] += 1
            if r.status in OPEN_STATUSES:
                entry["open"] += 1
            entry["first_seen"] = min(entry["first_seen"] or r.created_at, r.created_at or now)
            entry["last_seen"] = max(entry["last_seen"] or r.created_at, r.created_at or now)

        cat_names: dict[uuid.UUID, str] = {}
        issue_names: dict[uuid.UUID, str] = {}
        inst_names: dict[uuid.UUID, str] = {}
        geo_names: dict[uuid.UUID, str] = {}
        cat_ids = {e["category_id"] for e in groups.values()}
        issue_ids = {e["issue_type_id"] for e in groups.values() if e["issue_type_id"]}
        inst_ids = {e["institution_id"] for e in groups.values() if e["institution_id"]}
        geo_ids = {e["geography_id"] for e in groups.values() if e["geography_id"]}
        if cat_ids:
            for c in (
                await session.execute(select(Category).where(Category.id.in_(cat_ids)))
            ).scalars():
                cat_names[c.id] = c.slug
        if issue_ids:
            for i in (
                await session.execute(select(IssueType).where(IssueType.id.in_(issue_ids)))
            ).scalars():
                issue_names[i.id] = i.slug
        if inst_ids:
            for inst in (
                await session.execute(select(Institution).where(Institution.id.in_(inst_ids)))
            ).scalars():
                inst_names[inst.id] = inst.name
        if geo_ids:
            for geo in (
                await session.execute(select(Geography).where(Geography.id.in_(geo_ids)))
            ).scalars():
                geo_names[geo.id] = geo.name

        items: list[RecurringIssueItem] = []
        for entry in groups.values():
            if len(entry["months"]) < min_distinct_months:
                continue
            items.append(
                RecurringIssueItem(
                    institution_id=entry["institution_id"],
                    institution_name=(
                        inst_names.get(entry["institution_id"]) if entry["institution_id"] else None
                    ),
                    geography_id=entry["geography_id"],
                    geography_name=(
                        geo_names.get(entry["geography_id"]) if entry["geography_id"] else None
                    ),
                    category_slug=cat_names.get(entry["category_id"]),
                    issue_type_slug=issue_names.get(entry["issue_type_id"]),
                    distinct_months=len(entry["months"]),
                    total_reports=entry["total"],
                    first_seen=entry["first_seen"],
                    last_seen=entry["last_seen"],
                    open_reports=entry["open"],
                )
            )
        items.sort(key=lambda x: (x.distinct_months, x.total_reports), reverse=True)
        return items

    async def summarize(
        self,
        session: AsyncSession,
        *,
        geography_id: uuid.UUID | None = None,
    ) -> RecurringIssueResponse:
        items = await self.detect(session, geography_id=geography_id)
        return RecurringIssueResponse(
            items=items,
            window_months=RECURRENCE_WINDOW_MONTHS,
            min_distinct_months=MIN_DISTINCT_MONTHS,
            generated_at=_utcnow(),
            note=(
                "A recurring-issue pattern means the same category appeared at the "
                "same institution/geography in several distinct months. It does not "
                "by itself prove an unresolved problem — it is a review trigger."
            ),
        )
