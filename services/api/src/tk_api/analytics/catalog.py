"""Centralized Metric Catalog & Registry (Phase 12, PRD §26, ADR-050).

Every analytical metric in Theek Karo is registered here with its formal formula,
dimensions, data sources, allowed roles, refresh frequency, and privacy thresholds.
Backend owns metric definitions to prevent disparate frontend calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricDefinition:
    metric_id: str
    name: str
    description: str
    formula: str
    dimensions: list[str]
    allowed_roles: list[str] = field(
        default_factory=lambda: ["public", "citizen", "moderator", "admin"]
    )
    data_sources: list[str] = field(default_factory=lambda: ["reports"])
    refresh_frequency: str = "realtime"  # realtime | near_realtime | batch
    privacy_threshold: int = 0  # Small-cell protection threshold
    unit: str = "count"  # count | percentage | hours | currency_inr | currency_usd
    is_public: bool = True
    version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "description": self.description,
            "formula": self.formula,
            "dimensions": self.dimensions,
            "allowed_roles": self.allowed_roles,
            "data_sources": self.data_sources,
            "refresh_frequency": self.refresh_frequency,
            "privacy_threshold": self.privacy_threshold,
            "unit": self.unit,
            "is_public": self.is_public,
            "version": self.version,
        }


class MetricRegistry:
    """Registry containing authoritative definitions of all platform metrics."""

    def __init__(self) -> None:
        self._metrics: dict[str, MetricDefinition] = {}
        self._register_default_metrics()

    def _register_default_metrics(self) -> None:
        self.register(
            MetricDefinition(
                metric_id="report_count",
                name="Total Reported Issues",
                description="Total civic observation reports submitted across all statuses.",
                formula="COUNT(reports.id)",
                dimensions=["geography", "category", "issue_type", "severity", "status", "time"],
                unit="count",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="verified_report_count",
                name="Verified Reports",
                description="Reports achieving community or authority verification thresholds.",
                formula=(
                    "COUNT(reports.id) WHERE status IN ('verified', 'assigned', 'in_progress', "
                    "'resolution_submitted', 'resolution_review', 'resolved', "
                    "'community_verified', 'closed')"
                ),
                dimensions=["geography", "category", "issue_type", "time"],
                unit="count",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="open_report_count",
                name="Open Reports",
                description="Active reports awaiting investigation, assignment, or action.",
                formula=(
                    "COUNT(reports.id) WHERE status IN ('submitted', 'under_verification', "
                    "'verified', 'assigned', 'in_progress', 'reopened')"
                ),
                dimensions=["geography", "category", "severity", "time"],
                unit="count",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="resolved_report_count",
                name="Resolved Reports",
                description="Reports where corrective resolution action has been completed.",
                formula=(
                    "COUNT(reports.id) WHERE status IN ('resolved', 'community_verified', 'closed')"
                ),
                dimensions=["geography", "category", "institution", "time"],
                unit="count",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="verified_resolution_count",
                name="Verified Resolutions",
                description="Resolutions confirmed by independent community observation.",
                formula="COUNT(reports.id) WHERE status IN ('community_verified', 'closed')",
                dimensions=["geography", "category", "institution", "time"],
                unit="count",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="resolution_rate",
                name="Resolution Rate",
                description="Proportion of eligible civic reports that have been resolved.",
                formula="COUNT(resolved_reports) / NULLIF(COUNT(eligible_reports), 0)",
                dimensions=["geography", "category", "institution", "time"],
                unit="percentage",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="verification_rate",
                name="Verification Rate",
                description="Proportion of submitted reports that have passed verification.",
                formula="COUNT(verified_reports) / NULLIF(COUNT(submitted_reports), 0)",
                dimensions=["geography", "category", "time"],
                unit="percentage",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="median_resolution_hours",
                name="Median Resolution Time",
                description="Median duration in hours from report submission to resolution.",
                formula="MEDIAN(reports.resolved_at - reports.created_at)",
                dimensions=["geography", "category", "severity"],
                unit="hours",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="median_verification_hours",
                name="Median Verification Time",
                description="Median duration in hours from report submission to verification.",
                formula="MEDIAN(reports.verified_at - reports.created_at)",
                dimensions=["geography", "category"],
                unit="hours",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="institution_coverage_pct",
                name="Institution Mapped Coverage",
                description="Percentage of public institutions with mapped digital twin profiles.",
                formula="COUNT(mapped_institutions) / NULLIF(COUNT(all_institutions), 0)",
                dimensions=["geography", "institution_type"],
                data_sources=["institutions", "geography"],
                unit="percentage",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="official_data_coverage_pct",
                name="Official Data Coverage",
                description="Percentage of institutions with registered official datasets.",
                formula="COUNT(institutions_with_official_data) / NULLIF(COUNT(institutions), 0)",
                dimensions=["geography", "institution_type"],
                data_sources=["institutions", "gov_datasets"],
                unit="percentage",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="discrepancy_rate",
                name="Discrepancy Rate",
                description="Percentage of institutions with flagged data discrepancies.",
                formula=(
                    "COUNT(institutions_with_discrepancies) / "
                    "NULLIF(COUNT(institutions_with_data), 0)"
                ),
                dimensions=["geography", "category"],
                data_sources=["institution_discrepancies"],
                unit="percentage",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="backlog_aging_buckets",
                name="Backlog Aging Buckets",
                description="Distribution of open reports by aging interval.",
                formula=(
                    "CASE WHEN age <= 7 THEN '0-7d' WHEN age <= 30 THEN '8-30d' "
                    "WHEN age <= 90 THEN '31-90d' ELSE '90+d' END"
                ),
                dimensions=["geography", "category", "severity"],
                unit="count",
            )
        )
        self.register(
            MetricDefinition(
                metric_id="ai_cost_usd",
                name="AI Infrastructure Cost",
                description="Total estimated USD expenditure on LLM inferences.",
                formula="SUM(ai_runs.cost_usd)",
                dimensions=["model", "provider", "task", "time"],
                allowed_roles=["admin"],
                data_sources=["ai_runs"],
                unit="currency_usd",
                is_public=False,
            )
        )
        self.register(
            MetricDefinition(
                metric_id="ai_token_volume",
                name="AI Token Volume",
                description="Total prompt and completion tokens processed.",
                formula="SUM(ai_runs.tokens_in + ai_runs.tokens_out)",
                dimensions=["model", "provider", "task", "time"],
                allowed_roles=["admin"],
                data_sources=["ai_runs"],
                unit="count",
                is_public=False,
            )
        )
        self.register(
            MetricDefinition(
                metric_id="ai_feedback_positivity_pct",
                name="AI Feedback Positivity Rate",
                description="Proportion of positive feedback ratings received from users.",
                formula="COUNT(positive_feedback) / NULLIF(COUNT(all_feedback), 0)",
                dimensions=["task", "model", "time"],
                allowed_roles=["admin"],
                data_sources=["ai_feedback"],
                unit="percentage",
                is_public=False,
            )
        )

    def register(self, definition: MetricDefinition) -> None:
        self._metrics[definition.metric_id] = definition

    def get_metric(self, metric_id: str) -> MetricDefinition | None:
        return self._metrics.get(metric_id)

    def list_metrics(self, role: str = "public") -> list[MetricDefinition]:
        if role == "admin":
            return list(self._metrics.values())
        return [m for m in self._metrics.values() if role in m.allowed_roles and m.is_public]


GLOBAL_METRIC_REGISTRY = MetricRegistry()
