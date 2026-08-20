import { render, screen, fireEvent } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { KpiCard } from "./KpiCard"
import { TrendChart } from "./TrendChart"
import { CategoryBreakdownChart } from "./CategoryBreakdownChart"
import { ResolutionMatrix } from "./ResolutionMatrix"
import { DataQualityScorecard } from "./DataQualityScorecard"
import { AiOpsDashboard } from "./AiOpsDashboard"
import type {
  AiOpsAnalyticsResponse,
  CategoryAnalyticsItem,
  DataQualityScorecardResponse,
  KpiItem,
  ResolutionAnalyticsResponse,
  TimeSeriesPoint,
} from "@/lib/types"

describe("Phase 12 Analytics Components", () => {
  it("renders KpiCard with formatted value and toggles definition", () => {
    const kpi: KpiItem = {
      metric_id: "resolution_rate",
      name: "Resolution Rate",
      value: 78.5,
      unit: "percentage",
      period_label: "Last 30 days",
      definition: "Proportion of closed or resolved reports.",
      source: "Civic Authority",
      denominator_label: "78.5% resolved",
    }

    render(<KpiCard kpi={kpi} />)
    expect(screen.getByText("Resolution Rate")).toBeDefined()
    expect(screen.getByText("78.5%")).toBeDefined()
    expect(screen.getByText("Civic Authority")).toBeDefined()

    // Toggle definition
    const btn = screen.getByLabelText("Definition for Resolution Rate")
    fireEvent.click(btn)
    expect(screen.getByText("Proportion of closed or resolved reports.")).toBeDefined()
  })

  it("renders TrendChart and toggles accessible table view", () => {
    const series: TimeSeriesPoint[] = [
      {
        timestamp: "2026-08-10",
        total_count: 14,
        verified_count: 10,
        resolved_count: 8,
        critical_count: 2,
      },
      {
        timestamp: "2026-08-11",
        total_count: 20,
        verified_count: 15,
        resolved_count: 12,
        critical_count: 3,
      },
    ]

    render(<TrendChart series={series} interval="day" />)
    expect(screen.getByText("Report Volume Trends")).toBeDefined()

    // Toggle table
    const tableBtn = screen.getByText("Accessible Table")
    fireEvent.click(tableBtn)
    expect(screen.getByText("2026-08-10")).toBeDefined()
    expect(screen.getByText("2026-08-11")).toBeDefined()
  })

  it("renders CategoryBreakdownChart and expands issue types", () => {
    const categories: CategoryAnalyticsItem[] = [
      {
        category_slug: "education",
        category_name: "Education",
        report_count: 25,
        verified_count: 20,
        resolved_count: 15,
        open_count: 10,
        pct_of_total: 62.5,
        top_issue_types: [
          { slug: "school_toilets", name: "School Toilets", count: 15, pct: 60.0 },
        ],
      },
    ]

    render(<CategoryBreakdownChart categories={categories} totalReports={40} />)
    expect(screen.getByText("Education")).toBeDefined()
    expect(screen.getByText("25")).toBeDefined()

    // Expand issue types
    const expandBtn = screen.getByText("Education")
    fireEvent.click(expandBtn)
    expect(screen.getByText("School Toilets")).toBeDefined()
    expect(screen.getByText("15 (60%)")).toBeDefined()
  })

  it("renders ResolutionMatrix with median duration and verified fixes", () => {
    const resolution: ResolutionAnalyticsResponse = {
      total_resolved: 45,
      resolution_rate: 75.0,
      verified_resolution_count: 32,
      community_confirmed_count: 32,
      closed_count: 13,
      reopened_count: 3,
      median_resolution_hours: 48.0,
      p90_resolution_hours: 120.0,
      resolution_by_category: {},
    }

    render(<ResolutionMatrix resolution={resolution} />)
    expect(screen.getByText("75.0%")).toBeDefined()
    expect(screen.getByText("2.0d")).toBeDefined()
    expect(screen.getByText("32")).toBeDefined()
    expect(screen.getByText("3")).toBeDefined()
  })

  it("renders DataQualityScorecard with health telemetry", () => {
    const scorecard: DataQualityScorecardResponse = {
      total_sources: 12,
      healthy_sources_count: 10,
      stale_sources_count: 2,
      failed_sources_count: 0,
      total_records_ingested: 14500,
      pending_entity_matches_count: 4,
      institutions_with_official_data_pct: 85.0,
      sources_breakdown: [
        {
          id: "src-1",
          name: "PMGSY Roads",
          publisher: "MoRD",
          status: "HEALTHY",
          retrieval_date: "2026-08-01",
          confidence_base: 0.95,
        },
      ],
    }

    render(<DataQualityScorecard scorecard={scorecard} />)
    expect(screen.getByText("10")).toBeDefined()
    expect(screen.getByText("14,500")).toBeDefined()
    expect(screen.getByText("PMGSY Roads")).toBeDefined()
  })

  it("renders AiOpsDashboard with token volume and estimated USD costs", () => {
    const aiOps: AiOpsAnalyticsResponse = {
      total_requests: 1240,
      total_tokens: 350000,
      estimated_cost_usd: 1.452,
      avg_latency_ms: 320,
      p95_latency_ms: 680,
      feedback_positivity_pct: 94.5,
      task_breakdown: { chat_assistant: 800, classification: 440 },
      model_breakdown: { "deepseek-chat": 1240 },
    }

    render(<AiOpsDashboard aiOps={aiOps} />)
    expect(screen.getByText("1,240")).toBeDefined()
    expect(screen.getByText("350,000")).toBeDefined()
    expect(screen.getByText("$1.4520")).toBeDefined()
    expect(screen.getByText("320ms")).toBeDefined()
    expect(screen.getByText("deepseek-chat")).toBeDefined()
  })
})
