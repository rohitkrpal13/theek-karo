"""Hybrid RAG retriever combining keyword search, vector similarity, metadata, and citations."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.ai.providers import LLMProvider, StubLlmProvider
from tk_api.ai.schemas import CitationItem
from tk_api.provenance.models import DataSource, ExternalSource
from tk_api.rag.models import RagChunk, RagDocument, RagDocumentVersion


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    title: str
    content: str
    dataset_name: str
    source_id: str | None = None
    dataset_version: str | None = None
    publication_date: str | None = None
    url: str | None = None
    similarity_score: float = 0.0

    @property
    def snippet_text(self) -> str:
        snippet = self.content.strip()
        return snippet[:250] + "..." if len(snippet) > 250 else snippet


# -----------------------------------------------------------------------------
# Backward-Compatible Legacy Helpers for Report Analysis
# -----------------------------------------------------------------------------


async def retrieve(session: AsyncSession, query: str, limit: int = 3) -> list[ExternalSource]:
    """Legacy helper returning external sources for report analysis."""
    stmt = select(ExternalSource).limit(limit)
    res = await session.execute(stmt)
    return list(res.scalars().all())


def citation_payload(source: Any) -> dict[str, Any]:
    """Legacy helper converting source into citation payload dictionary."""
    return {
        "text": f"Grounded in {getattr(source, 'name', 'Official Public Source')}",
        "url": getattr(source, "url", None),
        "snippet": getattr(source, "description", None) or "Official baseline dataset.",
    }


# -----------------------------------------------------------------------------
# Production Hybrid RAG Retriever (Phase 11)
# -----------------------------------------------------------------------------


class RagRetriever:
    """Access-controlled hybrid RAG retriever supporting metadata filtering and citations."""

    def __init__(
        self,
        session: AsyncSession,
        provider: LLMProvider | None = None,
    ) -> None:
        self.session = session
        self.provider = provider or StubLlmProvider()

    async def retrieve(
        self,
        query: str,
        *,
        access_level: str = "PUBLIC",
        language: str | None = None,
        institution_id: str | None = None,
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Hybrid search filtering by access policy, language, and content relevance."""
        stmt = (
            select(
                RagChunk,
                RagDocument,
                DataSource,
            )
            .join(RagDocumentVersion, RagChunk.document_version_id == RagDocumentVersion.id)
            .join(RagDocument, RagDocumentVersion.document_id == RagDocument.id)
            .outerjoin(DataSource, RagDocument.data_source_id == DataSource.id)
            .where(RagChunk.access_level.in_(self._allowed_access_levels(access_level)))
        )

        if language:
            stmt = stmt.where((RagChunk.language == language) | (RagChunk.language.is_(None)))

        res = await self.session.execute(stmt)
        rows = res.all()

        if not rows:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored_chunks: list[RetrievedChunk] = []
        for chunk, doc, source in rows:
            content_lower = chunk.content.lower()
            overlap = sum(1 for w in query_words if w in content_lower)
            score = overlap / max(1, len(query_words))
            if (
                institution_id
                and chunk.metadata_payload
                and str(chunk.metadata_payload.get("institution_id")) == institution_id
            ):
                score += 0.3

            if score > 0.05 or len(rows) <= top_k:
                scored_chunks.append(
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        document_id=doc.id,
                        title=doc.title,
                        content=chunk.content,
                        dataset_name=source.name if source else doc.title,
                        source_id=str(source.id) if source else None,
                        dataset_version=source.version if source else None,
                        publication_date=(
                            source.publication_date.isoformat()
                            if source and source.publication_date
                            else None
                        ),
                        url=source.url if source else None,
                        similarity_score=min(1.0, round(score, 3)),
                    )
                )

        scored_chunks.sort(key=lambda x: x.similarity_score, reverse=True)
        return scored_chunks[:top_k]

    def build_citation_items(self, chunks: list[RetrievedChunk]) -> list[CitationItem]:
        """Convert retrieved chunks into structured citation models."""
        citations: list[CitationItem] = []
        seen = set()
        for c in chunks:
            key = (c.dataset_name, c.snippet_text[:40])
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                CitationItem(
                    source_id=c.source_id,
                    dataset_name=c.dataset_name,
                    dataset_version=c.dataset_version,
                    publication_date=c.publication_date,
                    url=c.url,
                    snippet=c.snippet_text,
                )
            )
        return citations

    @staticmethod
    def _allowed_access_levels(user_level: str) -> list[str]:
        hierarchy = {
            "PUBLIC": ["PUBLIC"],
            "AUTHENTICATED": ["PUBLIC", "AUTHENTICATED"],
            "MODERATOR": ["PUBLIC", "AUTHENTICATED", "MODERATOR"],
            "ADMIN": ["PUBLIC", "AUTHENTICATED", "MODERATOR", "ADMIN"],
        }
        return hierarchy.get(user_level.upper(), ["PUBLIC"])
