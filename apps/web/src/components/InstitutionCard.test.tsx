import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { InstitutionCard } from "./InstitutionCard"
import type { Institution } from "@/lib/types"

describe("InstitutionCard", () => {
  const mockInstitution: Institution = {
    id: "inst-123",
    type_id: "type-school",
    official_id: "SCH-PATNA-001",
    name: "Patna Central Model School",
    slug: "patna-central-model-school",
    description: "Senior secondary government school in Patna district.",
    geography_id: "geo-patna",
    operational_status: "operational",
    verification_state: "official",
    confidence_score: 0.95,
    source_id: "src-gov",
    is_active: true,
    created_at: "2026-08-16T10:00:00Z",
    updated_at: "2026-08-16T10:00:00Z",
  }

  it("renders institution name, official ID, and operational status", () => {
    render(
      <InstitutionCard
        institution={mockInstitution}
        typeName="Government School"
        geographyName="Patna, Bihar"
      />,
    )

    expect(screen.getByText("Patna Central Model School")).toBeInTheDocument()
    expect(screen.getByText("Government School")).toBeInTheDocument()
    expect(screen.getByText("operational")).toBeInTheDocument()
    expect(screen.getByText(/SCH-PATNA-001/)).toBeInTheDocument()
    expect(screen.getByText("Patna, Bihar")).toBeInTheDocument()
  })

  it("renders link to digital twin detail page", () => {
    render(
      <InstitutionCard
        institution={mockInstitution}
        typeName="School"
        geographyName="Bihar"
      />,
    )

    const link = screen.getByRole("link", { name: "View Digital Twin" })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute("href", "/en/institutions/inst-123")
  })
})
