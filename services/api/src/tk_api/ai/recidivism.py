"""Phase 9 — Recidivism Analytics.

Detects recurring civic issues: reports at the same location or institution
that reappear after resolution. Recidivism signals indicate systemic problems
that need department attention, not just individual case fixes.

Every finding is a review trigger — never an automatic action.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.civic.models import Category
from tk_api.reports.models import Report


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RECIDIVISM_WINDOW_DAYS = 180  # look back 6 months
RECIDIVISM_MIN_REPEATS = 2   # at least 2 resolved + 1 new = recidivism
RECIDIVISM_RADIUS_M = 200    # same institution or within 200m


def _extract_coords(loc: Any) -> tuple[float, float] | None:
    """Extract (lon, lat) from a GeoJSON location dict."""
    if isinstance(loc, dict):
        coords = loc.get("coordinates")
        if coords and len(coords) >= 2:
            try:
                return float(coords[0]), float(coords[1])
            except (ValueError, TypeError):
                return None
    return None


async def detect_recidivism(
    session: AsyncSession,
    *,
    geography_id: uuid.UUID | None = None,
    category_slug: str | None = None,
    institution_id: uuid.UUID | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Detect recurring civic issues in the platform.

    Returns a list of recidivism signals: locations/categories where issues
    keep recurring despite previous resolutions.
    """
    from datetime import timedelta

    now = datetime.now(UTC)
    cutoff = now - timedelta(days=RECIDIVISM_WINDOW_DAYS)

    # Base query: resolved/closed reports in the window
    base_stmt = (
        select(
            Report.institution_id,
            Report.category_id,
            Report.ticket_no,
            Report.title,
            Report.status,
            Report.severity,
            Report.created_at,
            Report.location,
        )
        .where(
            Report.deleted_at.is_(None),
            Report.created_at >= cutoff,
        )
    )

    if geography_id:
        base_stmt = base_stmt.where(Report.geography_id == geography_id)
    if category_slug:
        cat = await session.scalar(select(Category).where(Category.slug == category_slug))
        if cat:
            base_stmt = base_stmt.where(Report.category_id == cat.id)
    if institution_id:
        base_stmt = base_stmt.where(Report.institution_id == institution_id)

    reports = (await session.execute(base_stmt.order_by(Report.created_at.desc()))).all()

    # Group by institution + category
    groups: dict[str, list[Any]] = {}
    for row in reports:
        inst_id = str(row.institution_id) if row.institution_id else "none"
        cat_id = str(row.category_id) if row.category_id else "none"
        key = f"{inst_id}:{cat_id}"
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    # Detect recidivism: at least 2 resolved + 1 new/open
    signals = []
    for key, group in groups.items():
        resolved = [r for r in group if r.status in ("resolved", "closed")]
        open_reports = [r for r in group if r.status not in ("resolved", "closed", "rejected", "draft")]

        if len(resolved) >= RECIDIVISM_MIN_REPEATS and len(open_reports) >= 1:
            # Get institution name
            inst_name = None
            if group[0].institution_id:
                from tk_api.institutions.models import Institution
                inst = await session.get(Institution, group[0].institution_id)
                inst_name = inst.name if inst else None

            cat_name = None
            if group[0].category_id:
                cat = await session.get(Category, group[0].category_id)
                cat_name = cat.name_key if cat else None

            # Calculate severity trend
            severities = [r.severity for r in group if r.severity]
            high_count = sum(1 for s in severities if s in ("high", "critical"))

            signals.append({
                "institution_id": str(group[0].institution_id) if group[0].institution_id else None,
                "institution_name": inst_name,
                "category_id": str(group[0].category_id) if group[0].category_id else None,
                "category_name": cat_name,
                "resolved_count": len(resolved),
                "open_count": len(open_reports),
                "total_count": len(group),
                "high_severity_count": high_count,
                "first_report": group[-1].created_at.isoformat() if group[-1].created_at else None,
                "latest_report": group[0].created_at.isoformat() if group[0].created_at else None,
                "sample_tickets": [r.ticket_no for r in group[:5]],
                "recidivism_score": min(1.0, (len(resolved) * 0.3 + high_count * 0.2)),
                "recommendation": (
                    "Systemic issue detected — department investigation recommended"
                    if high_count >= 2
                    else "Monitor for further recurrence"
                ),
            })

    # Sort by recidivism score descending
    signals.sort(key=lambda s: s["recidivism_score"], reverse=True)

    return {
        "signals": signals[:limit],
        "total_signals": len(signals),
        "window_days": RECIDIVISM_WINDOW_DAYS,
        "min_repeats": RECIDIVISM_MIN_REPEATS,
        "note": (
            "Recidivism signals are review triggers. "
            "They indicate systemic patterns that need department attention. "
            "No automatic actions are taken."
        ),
    }


async def get_recidivism_summary(
    session: AsyncSession,
    *,
    geography_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Get a high-level summary of recidivism across the platform."""
    result = await detect_recidivism(
        session, geography_id=geography_id, limit=100
    )

    signals = result["signals"]
    total_institutions = len(set(
        s["institution_id"] for s in signals if s.get("institution_id")
    ))
    total_categories = len(set(
        s["category_id"] for s in signals if s.get("category_id")
    ))

    high_priority = sum(
        1 for s in signals if s["recidivism_score"] >= 0.7
    )

    return {
        "total_recurring_patterns": len(signals),
        "institutions_affected": total_institutions,
        "categories_affected": total_categories,
        "high_priority_patterns": high_priority,
        "top_signals": signals[:5],
        "methodology": (
            f"Detected over {RECIDIVISM_WINDOW_DAYS}-day window with "
            f"minimum {RECIDIVISM_MIN_REPEATS} resolved + 1 open report "
            f"at the same institution+category."
        ),
    }
