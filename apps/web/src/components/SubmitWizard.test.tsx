import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { SubmitWizard } from "./SubmitWizard"
import { civicApi, institutionsApi, reportsApi } from "@/lib/api"
import type { Category } from "@/lib/types"

describe("SubmitWizard component", () => {
  const mockCategories: Category[] = [
    {
      id: "cat-1",
      slug: "school",
      icon: "school",
      form_schema: {
        type: "object",
        required: ["classrooms"],
        properties: { classrooms: { type: "integer" } },
      },
      verification_policy: {},
      attachment_rules: {},
      default_locale_keys: {},
      form_schema_version: 1,
      is_active: true,
    },
    {
      id: "cat-2",
      slug: "road",
      icon: "road",
      form_schema: { type: "object", properties: {} },
      verification_policy: {},
      attachment_rules: {},
      default_locale_keys: {},
      form_schema_version: 1,
      is_active: true,
    },
  ]

  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(civicApi, "listCategories").mockResolvedValue({
      items: mockCategories,
    })
    vi.spyOn(civicApi, "listIssueTypes").mockResolvedValue([])
    vi.spyOn(institutionsApi, "list").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      limit: 30,
      pages: 0,
    })
  })

  it("renders category selection step and advances when category chosen", async () => {
    render(<SubmitWizard />)

    await waitFor(() => {
      expect(screen.getByText("school")).toBeInTheDocument()
      expect(screen.getByText("road")).toBeInTheDocument()
    })

    const roadButton = screen.getByRole("button", { name: /road/i })
    fireEvent.click(roadButton)

    const nextButton = screen.getByRole("button", { name: "Next" })
    expect(nextButton).not.toBeDisabled()
    fireEvent.click(nextButton)

    // Now on step 1 (Location)
    expect(screen.getByText("Incident Location")).toBeInTheDocument()
  })

  it("completes submission flow successfully", async () => {
    vi.spyOn(reportsApi, "submit").mockResolvedValueOnce({
      id: "rep-123",
      ticket_no: "TK-20260816-000001",
      category_id: "cat-2",
      campaign_id: null,
      institution_id: null,
      issue_type_id: null,
      reporter_id: "user-1",
      title: "Major pothole near Gandhi Chowk",
      description: "Severe road damage creating safety hazards for vehicles.",
      severity: "high",
      visibility: "public",
      source: "citizen",
      location: { type: "Point", coordinates: [75.7873, 26.9124] },
      location_accuracy_m: 15,
      status: "submitted",
      info_class: "CITIZEN_REPORT",
      trust_score: 0,
      duplicate_of: null,
      merged_by_ai: false,
      fields: {},
      resolved_at: null,
      created_at: "2026-08-16T12:00:00Z",
      updated_at: "2026-08-16T12:00:00Z",
    })

    render(<SubmitWizard initialCategory="road" />)

    // Wait for category to be selected automatically
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled()
    })

    // Advance through steps
    // Step 0 -> Step 1 (Location)
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(screen.getByText("Incident Location")).toBeInTheDocument()

    // Step 1 -> Step 2 (Institution)
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(
      screen.getByText("Linked Public Institution (Optional)"),
    ).toBeInTheDocument()

    // Step 2 -> Step 3 (Details)
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(
      screen.getByText("Issue Details & Category Schema"),
    ).toBeInTheDocument()

    // Fill Title and Description
    const titleInput = screen.getByLabelText(/Issue Title/i)
    const descInput = screen.getByLabelText(/Detailed Description/i)

    fireEvent.change(titleInput, {
      target: { value: "Major pothole near Gandhi Chowk" },
    })
    fireEvent.change(descInput, {
      target: {
        value: "Severe road damage creating safety hazards for vehicles.",
      },
    })

    // Step 3 -> Step 4 (Evidence)
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(
      screen.getByRole("heading", { name: "Evidence" }),
    ).toBeInTheDocument()

    // Step 4 -> Step 5 (Review)
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    expect(screen.getByText("Review Your Civic Report")).toBeInTheDocument()

    // Submit
    const submitBtn = screen.getByRole("button", { name: "Submit report" })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText("Report submitted!")).toBeInTheDocument()
      expect(screen.getByText("TK-20260816-000001")).toBeInTheDocument()
    })
  })
})
