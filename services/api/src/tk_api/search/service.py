"""Unified multi-domain search service (API.md §10, PRD §8).

Provides a provider abstraction (PostgresSearchProvider) that queries across
reports, institutions, geography, and categories.
"""

from __future__ import annotations

import re
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Category, IssueType
from tk_api.geography.models import Geography
from tk_api.institutions.models import Institution
from tk_api.reports.models import Report
from tk_api.search.schemas import SearchDomain, SearchResponse, SearchResultItem


def _clean_query(q: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", q.strip().lower())
    return re.sub(r"\s+", " ", cleaned)


class SearchProvider(Protocol):
    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        domain: SearchDomain = "all",
        limit: int = 20,
    ) -> SearchResponse: ...


class PostgresSearchProvider:
    """PostgreSQL ILIKE / text search provider across multiple core domains."""

    async def search(
        self,
        session: AsyncSession,
        *,
        query: str,
        domain: SearchDomain = "all",
        limit: int = 20,
    ) -> SearchResponse:
        clean_q = _clean_query(query)
        if not clean_q:
            return SearchResponse(query=query, total=0, items=[])

        pattern = f"%{clean_q}%"
        items: list[SearchResultItem] = []
        per_domain_limit = max(5, limit // 2 if domain == "all" else limit)

        # 1. Reports domain
        if domain in ("all", "reports"):
            stmt_rep = (
                select(Report)
                .where(
                    Report.deleted_at.is_(None),
                    or_(
                        Report.title.ilike(pattern),
                        Report.description.ilike(pattern),
                        Report.ticket_no.ilike(pattern),
                    ),
                )
                .limit(per_domain_limit)
            )
            rep_rows = (await session.execute(stmt_rep)).scalars().all()
            for r in rep_rows:
                snippet = r.description[:150] + "..." if len(r.description) > 150 else r.description
                items.append(
                    SearchResultItem(
                        id=r.id,
                        domain="reports",
                        title=r.title,
                        subtitle=f"Ticket: {r.ticket_no} | Status: {r.status}",
                        snippet=snippet,
                        score=1.0,
                        meta={"ticket_no": r.ticket_no, "status": r.status, "severity": r.severity},
                    )
                )

        # 2. Institutions domain
        if domain in ("all", "institutions"):
            stmt_inst = (
                select(Institution)
                .where(
                    Institution.deleted_at.is_(None),
                    or_(
                        Institution.name.ilike(pattern),
                        Institution.normalized_name.ilike(pattern),
                        Institution.official_identifier.ilike(pattern),
                        Institution.address.ilike(pattern),
                    ),
                )
                .limit(per_domain_limit)
            )
            inst_rows = (await session.execute(stmt_inst)).scalars().all()
            for inst in inst_rows:
                ident = inst.official_identifier or "N/A"
                items.append(
                    SearchResultItem(
                        id=inst.id,
                        domain="institutions",
                        title=inst.name,
                        subtitle=inst.address,
                        snippet=f"ID: {ident} | Status: {inst.operational_status}",
                        score=1.0,
                        meta={"operational_status": inst.operational_status},
                    )
                )

        # 3. Geography domain
        if domain in ("all", "geography"):
            stmt_geo = (
                select(Geography)
                .where(
                    or_(
                        Geography.name.ilike(pattern),
                        Geography.normalized_name.ilike(pattern),
                    )
                )
                .limit(per_domain_limit)
            )
            geo_rows = (await session.execute(stmt_geo)).scalars().all()
            for geo in geo_rows:
                items.append(
                    SearchResultItem(
                        id=geo.id,
                        domain="geography",
                        title=geo.name,
                        subtitle=f"Country: {geo.country_code}",
                        score=1.0,
                        meta={"country_code": geo.country_code},
                    )
                )

        # 4. Categories domain
        if domain in ("all", "categories"):
            stmt_cat = (
                select(Category)
                .where(Category.is_active.is_(True), Category.slug.ilike(pattern))
                .limit(per_domain_limit)
            )
            cat_rows = (await session.execute(stmt_cat)).scalars().all()
            for cat in cat_rows:
                items.append(
                    SearchResultItem(
                        id=cat.id,
                        domain="categories",
                        title=cat.slug.replace("_", " ").title(),
                        subtitle=f"Slug: {cat.slug}",
                        score=1.0,
                        meta={"slug": cat.slug, "icon": cat.icon},
                    )
                )

            stmt_it = (
                select(IssueType)
                .where(
                    IssueType.is_active.is_(True),
                    or_(IssueType.name.ilike(pattern), IssueType.slug.ilike(pattern)),
                )
                .limit(per_domain_limit)
            )
            it_rows = (await session.execute(stmt_it)).scalars().all()
            for it in it_rows:
                items.append(
                    SearchResultItem(
                        id=it.id,
                        domain="categories",
                        title=it.name,
                        subtitle=f"Issue Type ({it.slug})",
                        snippet=it.description,
                        score=1.0,
                        meta={"slug": it.slug, "category_id": str(it.category_id)},
                    )
                )

        return SearchResponse(query=query, total=len(items), items=items[:limit])


default_search_provider = PostgresSearchProvider()


async def search(
    session: AsyncSession,
    *,
    query: str,
    domain: SearchDomain = "all",
    limit: int = 20,
    provider: SearchProvider | None = None,
) -> SearchResponse:
    p = provider or default_search_provider
    return await p.search(session, query=query, domain=domain, limit=limit)
