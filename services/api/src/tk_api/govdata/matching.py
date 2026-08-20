"""Multi-signal Entity Matching & Resolution for Government Data Ingestion."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.institutions.models import Institution


def normalize_text(text: str) -> str:
    """Normalize names for comparison: lowercase, remove punctuation, collapse whitespace."""
    if not text:
        return ""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())


def calculate_name_similarity(name_a: str, name_b: str) -> float:
    """Compute token-based Jaccard and containment similarity between two institution names."""
    norm_a = normalize_text(name_a)
    norm_b = normalize_text(name_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())

    intersection = tokens_a.intersection(tokens_b)
    union = tokens_a.union(tokens_b)
    if not union:
        return 0.0

    jaccard = len(intersection) / len(union)

    # Substring containment bonus (e.g. "Govt High School" in "Govt High School Jaipur")
    containment = len(intersection) / min(len(tokens_a), len(tokens_b))
    return round(0.6 * jaccard + 0.4 * containment, 3)


async def match_institution_candidate(
    session: AsyncSession,
    *,
    name: str,
    official_identifier: str | None = None,
    institution_type_id: uuid.UUID | None = None,
    geography_id: uuid.UUID | None = None,
) -> tuple[Institution | None, float, str, dict[str, Any]]:
    """Resolve an incoming external record against existing institutions via multi-signal matching.

    Returns:
        (matched_institution, confidence_score, match_status, signals_dict)
        match_status in ('MATCHED', 'POSSIBLE_MATCH', 'CONFLICT', 'UNMATCHED')
    """
    signals: dict[str, Any] = {
        "identifier_exact": False,
        "name_similarity": 0.0,
        "geography_match": False,
        "type_match": False,
    }

    # Signal 1: Exact Unique Official Identifier
    if official_identifier:
        stmt = select(Institution).where(
            Institution.deleted_at.is_(None),
            (Institution.official_identifier == official_identifier)
            | (Institution.source_identifier == official_identifier),
        )
        res = await session.execute(stmt)
        candidates = res.scalars().all()
        if len(candidates) == 1:
            signals["identifier_exact"] = True
            signals["name_similarity"] = calculate_name_similarity(name, candidates[0].name)
            return candidates[0], 0.95, "MATCHED", signals
        elif len(candidates) > 1:
            signals["identifier_exact"] = True
            signals["conflict_count"] = len(candidates)
            return candidates[0], 0.60, "CONFLICT", signals

    # Signal 2: Query potential matches by institution_type / geography
    base_query = select(Institution).where(Institution.deleted_at.is_(None))
    if institution_type_id:
        base_query = base_query.where(Institution.institution_type_id == institution_type_id)
    if geography_id:
        base_query = base_query.where(Institution.geography_id == geography_id)

    res = await session.execute(base_query.limit(200))
    pool = res.scalars().all()

    if not pool:
        # Fallback to broader search without geography filter
        broader_query = select(Institution).where(Institution.deleted_at.is_(None))
        if institution_type_id:
            broader_query = broader_query.where(
                Institution.institution_type_id == institution_type_id
            )
        res_broad = await session.execute(broader_query.limit(200))
        pool = res_broad.scalars().all()

    scored: list[tuple[Institution, float, dict[str, Any]]] = []

    for inst in pool:
        sim = calculate_name_similarity(name, inst.name)
        geo_match = geography_id is not None and inst.geography_id == geography_id
        type_match = (
            institution_type_id is not None and inst.institution_type_id == institution_type_id
        )

        score = sim * 0.7
        if geo_match:
            score += 0.2
        if type_match:
            score += 0.1

        score = min(1.0, round(score, 3))
        if score >= 0.50:
            item_signals = {
                "identifier_exact": False,
                "name_similarity": sim,
                "geography_match": geo_match,
                "type_match": type_match,
            }
            scored.append((inst, score, item_signals))

    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        return None, 0.0, "UNMATCHED", signals

    top_inst, top_score, top_signals = scored[0]

    # Check for tie/conflict
    if len(scored) > 1 and abs(top_score - scored[1][1]) < 0.05 and top_score >= 0.75:
        top_signals["conflict_count"] = len(scored)
        return top_inst, 0.60, "CONFLICT", top_signals

    if top_score >= 0.85:
        return top_inst, top_score, "MATCHED", top_signals
    elif top_score >= 0.50:
        return top_inst, top_score, "POSSIBLE_MATCH", top_signals
    else:
        return None, top_score, "UNMATCHED", top_signals
