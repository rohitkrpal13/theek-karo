import { render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { IntelligenceHub } from "@/components/intelligence/IntelligenceHub"
import { Providers } from "@/components/Providers"
import { intelligenceApi } from "@/lib/api/intelligence"

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    overview: vi.fn(),
    listSignals: vi.fn(),
    getSignal: vi.fn(),
    createSignal: vi.fn(),
    reviewSignal: vi.fn(),
    trends: vi.fn(),
    anomalies: vi.fn(),
    clusters: vi.fn(),
    recurring: vi.fn(),
    resolution: vi.fn(),
    improvements: vi.fn(),
    freshness: vi.fn(),
    dataGaps: vi.fn(),
    map: vi.fn(),
    listForecasts: vi.fn(),
    runForecast: vi.fn(),
    listModelVersions: vi.fn(),
    listReports: vi.fn(),
    createReport: vi.fn(),
    getReport: vi.fn(),
  },
}))

const mockOverview = {
  generated_at: "2026-08-18T10:00:00Z",
  geography_name: null,
  sections: [
    {
      key: "trends",
      title: "Trend comparison",
      data: {
        direction: "increasing",
        change_pct: 12.5,
        series: [
          { timestamp: "2026-08-11", value: 4 },
          { timestamp: "2026-08-18", value: 7 },
        ],
      },
      limitations: ["Comparable-window ratio; no causation."],
    },
    {
      key: "anomalies",
      title: "Detected anomalies",
      data: {
        anomalies: [{ metric: "reports", observed_value: 9, deviation_pct: 33, status: "NEW" }],
      },
      limitations: ["Deviation triggers require human review."],
    },
    {
      key: "clusters",
      title: "Issue clusters",
      data: { clusters: [{ cluster_key: "water-gaya", label: "Water in Gaya", report_count: 3 }] },
      limitations: ["Clusters never merge or delete reports."],
    },
    {
      key: "recurring_issues",
      title: "Recurring issues",
      data: { items: [{ geography_name: "Gaya", distinct_months: 3, total_reports: 6 }] },
      limitations: ["Distinct-month recurrence is a review trigger."],
    },
    {
      key: "data_freshness",
      title: "Data freshness",
      data: { items: [{ label: "UDISE+", last_updated_at: "2026-08-01T00:00:00Z" }] },
      limitations: ["Last-import based; sources may publish elsewhere."],
    },
  ],
  methodology_note: "Deterministic engines over stored data.",
}

function renderHub() {
  return render(
    <Providers locale="en">
      <IntelligenceHub />
    </Providers>,
  )
}

beforeEach(() => {
  vi.restoreAllMocks()
})

describe("IntelligenceHub", () => {
  it("renders the overview tab with trend and anomaly sections", async () => {
    vi.mocked(intelligenceApi.overview).mockResolvedValue(mockOverview as never)

    renderHub()

    expect(screen.getByRole("heading", { name: "Civic Intelligence" })).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText("Trend comparison")).toBeInTheDocument()
    })
    expect(screen.getByText("Increasing")).toBeInTheDocument()
    expect(screen.getByText("Detected anomalies")).toBeInTheDocument()
  })

  it("shows the signals tab and renders a signal", async () => {
    vi.mocked(intelligenceApi.listSignals).mockResolvedValue({
      items: [
        {
          id: "sig-1",
          signal_type: "anomaly",
          title: "Water complaints spike",
          description: null,
          severity: "HIGH",
          confidence: "MEDIUM",
          status: "NEW",
          evidence_count: 2,
          source_count: 1,
          created_at: "2026-08-18T10:00:00Z",
          review_history: [],
        },
      ],
      count: 1,
      generated_at: "2026-08-18T10:00:00Z",
      note: "review triggers",
    } as never)

    renderHub()

    await waitFor(() => {
      expect(screen.getByRole("tab", { name: "Signals" })).toBeInTheDocument()
    })
    screen.getByRole("tab", { name: "Signals" }).click()

    await waitFor(() => {
      expect(screen.getByText("Water complaints spike")).toBeInTheDocument()
    })
    expect(screen.getByText(/2 evidence/)).toBeInTheDocument()
    expect(screen.getByText(/1 sources/)).toBeInTheDocument()
  })

  it("shows an error state when the API fails", async () => {
    vi.mocked(intelligenceApi.overview).mockRejectedValue(new Error("boom") as never)

    renderHub()

    await waitFor(() => {
      expect(screen.getByText("Could not load intelligence data.")).toBeInTheDocument()
    })
  })
})
