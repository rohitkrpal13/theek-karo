"""Unified Search API endpoint (API.md §10, PRD §8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from tk_api.api.deps import DbSession
from tk_api.core.rate_limit import client_ip, rate_limit
from tk_api.search import service as search_service
from tk_api.search.schemas import SearchDomain, SearchResponse

search_router = APIRouter(prefix="/api/v1/search", tags=["search"])


@search_router.get("", response_model=SearchResponse)
async def unified_search(
    request: Request,
    session: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=200, description="Search query")],
    domain: Annotated[
        SearchDomain,
        Query(description="Domain filter: all, reports, institutions, geography, categories"),
    ] = "all",
    limit: Annotated[int, Query(ge=1, le=100, description="Maximum results to return")] = 20,
) -> SearchResponse:
    """Unified multi-domain search across reports, institutions, geography, and categories."""
    await rate_limit(
        request, bucket="search", key=f"search:{client_ip(request)}", limit=60, window_seconds=60
    )
    return await search_service.search(
        session,
        query=q,
        domain=domain,
        limit=limit,
    )
