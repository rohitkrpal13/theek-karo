import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { SubmitWizard } from "./SubmitWizard"
import { civicApi, institutionsApi, reportsApi } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import type { Category } from "@/lib/types"

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: null })),
}))

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
    vi.mocked(useAuth).mockReturnValue({ user: null } as ReturnType<typeof useAuth>)
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
    fireEvent.click(nextButton)
    expect(screen.getByText("Incident Location")).toBeInTheDocument()
    expect(nextButton).toBeDisabled()
    fireEvent.change(screen.getByLabelText("Latitude (WGS84)"), {
      target: { value: "91" },
    })
    fireEvent.change(screen.getByLabelText("Longitude (WGS84)"), {
      target: { value: "0" },
    })
    expect(nextButton).toBeDisabled()
    expect(
      screen.getByText("Enter a latitude from -90 to 90 and a longitude from -180 to 180."),
    ).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText("Latitude (WGS84)"), {
      target: { value: "0" },
    })
    fireEvent.change(screen.getByLabelText("Longitude (WGS84)"), {
      target: { value: "0" },
    })
    expect(nextButton).not.toBeDisabled()
    fireEvent.click(nextButton)

    // Equator and prime meridian are valid coordinates.
    expect(
      screen.getByText("Linked Public Institution (Optional)"),
    ).toBeInTheDocument()
  })

  it("explains that guests can submit reports but need an account to attach evidence", async () => {
    render(<SubmitWizard initialCategory="road" initialLat={26.9} initialLon={75.7} />)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled()
    })
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.change(screen.getByLabelText(/Issue Title/i), {
      target: { value: "Road damage at Main Street" },
    })
    fireEvent.change(screen.getByLabelText(/Detailed Description/i), {
      target: { value: "A large pothole is affecting traffic." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    expect(
      screen.getByText("Sign in to attach evidence. You can still submit a report without files."),
    ).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Log in" })).toHaveAttribute(
      "href",
      "/en/auth/login",
    )
    expect(screen.getByText("Upload from Gallery").closest("button")).toBeDisabled()
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

    render(<SubmitWizard initialCategory="road" initialLat={26.9124} initialLon={75.7873} />)

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

  it("uploads selected evidence with the submitted report", async () => {
    vi.mocked(useAuth).mockReturnValue({ user: { id: "user-1" } } as ReturnType<typeof useAuth>)
    vi.spyOn(reportsApi, "requestUploadSlot").mockResolvedValueOnce({
      media_id: "media-1",
      upload_method: "api",
      presigned_url: null,
      expires_in: 900,
    })
    vi.spyOn(reportsApi, "uploadEvidenceBytes")
      .mockRejectedValueOnce(new Error("Network interrupted"))
      .mockResolvedValueOnce()
    vi.spyOn(reportsApi, "completeUpload").mockResolvedValueOnce({
      id: "evidence-1",
      report_id: "rep-123",
      kind: "image",
      created_at: "2026-08-16T12:00:00Z",
    })
    const submitReport = vi.spyOn(reportsApi, "submit").mockResolvedValueOnce({
      id: "rep-123",
      ticket_no: "TK-20260816-000001",
      category_id: "cat-2",
      campaign_id: null,
      institution_id: null,
      issue_type_id: null,
      reporter_id: "user-1",
      title: "Road damage at Main Street",
      description: "A large pothole is affecting traffic.",
      severity: "medium",
      visibility: "public",
      source: "citizen",
      location: { type: "Point", coordinates: [0, 0] },
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

    const { container } = render(
      <SubmitWizard initialCategory="road" initialLat={0} initialLon={0} />,
    )
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled()
    })
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.change(screen.getByLabelText(/Issue Title/i), {
      target: { value: "Road damage at Main Street" },
    })
    fireEvent.change(screen.getByLabelText(/Detailed Description/i), {
      target: { value: "A large pothole is affecting traffic." },
    })
    fireEvent.click(screen.getByRole("button", { name: "Next" }))

    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]')
    expect(fileInput).not.toBeNull()
    const evidenceFile = new File(["image-bytes"], "pothole.png", { type: "image/png" })
    Object.defineProperty(evidenceFile, "arrayBuffer", {
      value: async () => new TextEncoder().encode("image-bytes").buffer,
    })
    fireEvent.change(fileInput!, {
      target: {
        files: [evidenceFile],
      },
    })
    fireEvent.click(screen.getByRole("button", { name: "Next" }))
    fireEvent.click(screen.getByRole("button", { name: "Submit report" }))

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Report TK-20260816-000001 was registered")
    })
    fireEvent.click(screen.getByRole("button", { name: "Retry evidence upload" }))

    await waitFor(() => {
      expect(reportsApi.requestUploadSlot).toHaveBeenCalledWith("rep-123", {
        mime_type: "image/png",
        size_bytes: 11,
        kind: "image",
      })
      expect(reportsApi.requestUploadSlot).toHaveBeenCalledTimes(1)
      expect(reportsApi.uploadEvidenceBytes).toHaveBeenCalledWith(
        "media-1",
        expect.any(File),
        null,
      )
      expect(reportsApi.uploadEvidenceBytes).toHaveBeenCalledTimes(2)
      expect(submitReport).toHaveBeenCalledTimes(1)
      expect(reportsApi.completeUpload).toHaveBeenCalledWith(
        "rep-123",
        expect.objectContaining({ media_id: "media-1", checksum_sha256: expect.any(String) }),
      )
      expect(screen.getByText("Report submitted!")).toBeInTheDocument()
    })
  })
})
