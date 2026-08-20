"""Intelligence report generator (Phase 20, spec §12, docs/INTELLIGENCE-METHODOLOGY.md).

A compiled report = trend summary + anomaly events + clusters + resilience
gaps + data freshness, serialized to JSON (``format=json``) or CSV
(``format=csv`` in a single-sheet table layout) and stored on the media
export bucket. The generator runs in the worker; the API only creates
``pending`` rows and serves the finished file.

Every report pins methodology + dataset versions so the "how was this
computed" question always has a stored answer; failures are persisted on the
row (``status=failed`` + ``error``) so they are visible in the UI.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tk_api.intelligence.anomalies import AnomalyEngine
from tk_api.intelligence.clusters import ClusterEngine, RecurringIssueEngine
from tk_api.intelligence.freshness import DataFreshnessEngine
from tk_api.intelligence.models import IntelligenceReport
from tk_api.intelligence.trends import TrendEngine


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _rowify(section: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten one dashboard section into CSV rows (one section per row)."""
    out: list[dict[str, Any]] = []
    for item in section.get("items", []):
        row: dict[str, Any] = {"section": section.get("section", "")}
        if isinstance(item, dict):
            for k, v in item.items():
                row[k] = v
        else:
            row["value"] = item
        out.append(row)
    return out


def _to_csv(sections: list[dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    cols: list[str] = []
    for section in sections:
        for row in _rowify(section):
            for k in row:
                if k not in cols:
                    cols.append(k)
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    for section in sections:
        writer.writerows(_rowify(section))
    return buf.getvalue().encode("utf-8")


def _to_json(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, default=str, indent=2).encode("utf-8")


class IntelligenceReportGenerator:
    """Composes the standard report sections from the Phase 20 engines."""

    def __init__(
        self,
        *,
        trend_engine: TrendEngine | None = None,
        anomaly_engine: AnomalyEngine | None = None,
        cluster_engine: ClusterEngine | None = None,
        recurring_engine: RecurringIssueEngine | None = None,
        freshness_engine: DataFreshnessEngine | None = None,
    ) -> None:
        self._trends = trend_engine or TrendEngine()
        self._anomalies = anomaly_engine or AnomalyEngine()
        self._clusters = cluster_engine or ClusterEngine()
        self._recurring = recurring_engine or RecurringIssueEngine()
        self._freshness = freshness_engine or DataFreshnessEngine()

    async def sections(
        self, session: AsyncSession, *, geography_id: uuid.UUID | None = None
    ) -> list[dict[str, Any]]:
        trend = await self._trends.summarize(session, geography_id=geography_id)
        anomaly_items = await self._anomalies.detect_all(session, geography_id=geography_id)
        cluster_resp = await self._clusters.summarize(session, geography_id=geography_id)
        recurring_resp = await self._recurring.summarize(session, geography_id=geography_id)
        freshness = await self._freshness.scan(session)
        gaps = await self._freshness.gap_analysis(session)
        return [
            {
                "section": "trends",
                "generated_at": trend.generated_at.isoformat() if trend.generated_at else None,
                "items": [t.model_dump(mode="json") for t in trend.items],
                "note": trend.methodology_note,
            },
            {
                "section": "anomalies",
                "generated_at": _utcnow().isoformat(),
                "items": [a.model_dump(mode="json") for a in anomaly_items],
                "note": (
                    "An anomaly is 'something unusual was detected' — never an "
                    "accusation; it is a trigger for human review."
                ),
            },
            {
                "section": "clusters",
                "generated_at": cluster_resp.generated_at.isoformat(),
                "items": [c.model_dump(mode="json") for c in cluster_resp.clusters],
                "note": cluster_resp.note,
            },
            {
                "section": "recurring_issues",
                "generated_at": recurring_resp.generated_at.isoformat(),
                "items": [i.model_dump(mode="json") for i in recurring_resp.items],
                "note": recurring_resp.note,
            },
            {
                "section": "data_freshness",
                "generated_at": freshness.generated_at.isoformat(),
                "items": [i.model_dump(mode="json") for i in freshness.items],
            },
            {
                "section": "data_coverage_gaps",
                "generated_at": gaps.generated_at.isoformat(),
                "items": [i.model_dump(mode="json") for i in gaps.items],
                "note": gaps.interpretation_note,
            },
        ]

    async def generate(
        self,
        session: AsyncSession,
        report: IntelligenceReport,
        save_callback: Any = None,
    ) -> IntelligenceReport:
        """Run the engines and persist the finished artifact."""
        try:
            sections = await self.sections(session, geography_id=report.geography_id)
            report.status = "generating"
            report.methodology = {
                "trends": "comparable-period ratio vs previous period",
                "anomalies": "IQR over rolling baseline (1.5x multiplier)",
                "clusters": "geo/institution + category bucketing over fixed window",
                "recurring": "distinct-month recurrence at same institution",
                "forecasting": "piecewise-exponential drift-EMA",
                "freshness": "staleness vs expected frequency",
            }
            report.dataset_versions = {"core": "phase20-migrations-0033"}
            payload = {
                "report_id": str(report.id),
                "title": report.title,
                "scope": report.scope,
                "generated_at": _utcnow().isoformat(),
                "sections": sections,
            }
            blob = _to_csv(sections) if report.format == "csv" else _to_json(payload)
            report.content = payload
            if save_callback is not None:
                key = f"intelligence/{report.id}.{report.format}"
                save_callback(key, blob)
                report.file_key = key
            report.status = "ready"
            report.generated_at = _utcnow()
            await session.flush()
            return report
        except Exception as exc:
            report.status = "failed"
            report.error = f"{type(exc).__name__}: {exc}"
            await session.flush()
            return report
