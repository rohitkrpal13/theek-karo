import { render, screen, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { DiscrepancyCard } from "./DiscrepancyCard"
import type { ResourceComparisonItem } from "@/lib/types"

describe("DiscrepancyCard component", () => {
  const mockItemDiscrepancy: ResourceComparisonItem = {
    resource_key: "sanctioned_teachers",
    label: "Sanctioned Teachers",
    official_value: 16,
    official_source: "UDISE+ 2026",
    official_updated_at: "Published 30 days ago",
    citizen_reports_count: 3,
    citizen_observation_summary: "3 citizen reports indicate severe teacher shortage in Class 9 and 10",
    discrepancy_state: "POSSIBLE_DISCREPANCY",
    ai_analysis_note: "Possible discrepancy between published staff figures and recent community reports.",
  }

  const mockItemConsistent: ResourceComparisonItem = {
    resource_key: "drinking_water_available",
    label: "Drinking Water",
    official_value: true,
    official_source: "UDISE+ 2026",
    official_updated_at: "Published 30 days ago",
    citizen_reports_count: 0,
    citizen_observation_summary: "No conflicting observations reported",
    discrepancy_state: "NO_DISCREPANCY_DETECTED",
    ai_analysis_note: "Official data aligns with community observations.",
  }

  it("renders discrepancy item with neutral non-accusatory badge and details", () => {
    render(<DiscrepancyCard item={mockItemDiscrepancy} />)

    expect(screen.getByText("Sanctioned Teachers")).toBeInTheDocument()
    expect(screen.getByText("Possible Discrepancy")).toBeInTheDocument()
    expect(screen.getByText("16")).toBeInTheDocument()
    expect(
      screen.getByText("3 citizen reports indicate severe teacher shortage in Class 9 and 10")
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        "Possible discrepancy between published staff figures and recent community reports."
      )
    ).toBeInTheDocument()
  })

  it("renders consistent item with Data Consistent badge", () => {
    render(<DiscrepancyCard item={mockItemConsistent} />)

    expect(screen.getByText("Drinking Water")).toBeInTheDocument()
    expect(screen.getByText("Data Consistent")).toBeInTheDocument()
    expect(screen.getByText("Available / Functional")).toBeInTheDocument()
  })

  it("triggers onVerify callback when Verify On-Ground is clicked", () => {
    const handleVerify = vi.fn()
    render(<DiscrepancyCard item={mockItemDiscrepancy} onVerify={handleVerify} />)

    const btn = screen.getByRole("button", { name: /Verify On-Ground/i })
    fireEvent.click(btn)
    expect(handleVerify).toHaveBeenCalledTimes(1)
  })
})
