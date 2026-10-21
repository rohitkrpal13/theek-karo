import { render, screen, waitFor, fireEvent } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { SocialAmplifyModal } from "./SocialAmplifyModal"
import { reportsApi } from "@/lib/api/reports"

vi.mock("@/lib/api/reports", () => ({
  reportsApi: {
    getSocialPost: vi.fn(),
    broadcastSocialPost: vi.fn(),
    getSocialBroadcastStatus: vi.fn(),
  },
}))

describe("SocialAmplifyModal component", () => {
  const mockPostResponse = {
    report_id: "rep-123",
    ticket_no: "TK-2026-BLR-001",
    tone: "urgent" as const,
    x_post: {
      text: "🚨 URGENT CIVIC ALERT: Massive crater pothole at CMH Road, Bengaluru. Severe hazard! Pls intervene @BBMPCOMM @blrcitytraffic #TK-2026-BLR-001 https://theekkaro.in/reports/rep-123 #TheekKaro",
      intent_url: "https://x.com/intent/tweet?text=mock",
      handles: ["@BBMPCOMM", "@blrcitytraffic"],
      char_count: 220,
      fits_single_tweet: true,
    },
    instagram_post: {
      caption: "⚠️ CIVIC OBSERVATION — ACTION REQUIRED ⚠️\nLocation: CMH Road\nTicket: #TK-2026-BLR-001",
      handles: ["@bbmp.bangalore", "@bangaloretrafficpolice"],
      hashtags: ["#TheekKaro", "#BengaluruCivic", "#BBMP"],
    },
    authorities: [
      {
        name: "BBMP",
        x_handle: "@BBMPCOMM",
        instagram_handle: "@bbmp.bangalore",
        jurisdiction: "Municipal Corporation",
        is_primary: true,
        verification_status: "unverified" as const,
      },
    ],
    hashtags: ["#TheekKaro", "#BengaluruCivic", "#BBMP"],
    report_url: "https://theekkaro.in/reports/rep-123",
    story_card: {
      ticket_no: "TK-2026-BLR-001",
      title: "Massive crater pothole",
      category: "Roads",
      severity: "High",
      address: "CMH Road, Bengaluru",
      city: "Bengaluru",
      primary_authority_name: "BBMP",
      primary_authority_handle: "@BBMPCOMM",
      report_url: "https://theekkaro.in/reports/rep-123",
      primary_image_url: null,
      trust_tier: "COMMUNITY_VERIFIED",
    },
    official_broadcast_eligible: true,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(reportsApi.getSocialPost).mockResolvedValue(mockPostResponse)
    vi.mocked(reportsApi.getSocialBroadcastStatus).mockResolvedValue(null)
  })


  it("renders social post modal with 1-click X tweet intent and authority tags", async () => {
    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    expect(screen.getByText("Amplify & Tag Authorities")).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText(/Massive crater pothole at CMH Road/)).toBeInTheDocument()
    })

    expect(screen.getByText("Post on 𝕏 (1-Click)")).toBeInTheDocument()
    expect(screen.getByText("@BBMPCOMM")).toBeInTheDocument()
  })

  it("switches to Instagram tab and shows caption and story options", async () => {
    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("Post on 𝕏 (1-Click)")).toBeInTheDocument()
    })

    const igTab = screen.getByRole("button", { name: /Instagram Story & Post/ })
    fireEvent.click(igTab)

    expect(screen.getByText("Instagram Caption & Hashtags:")).toBeInTheDocument()
    expect(screen.getByText("Download Story Image (9:16)")).toBeInTheDocument()
  })

  it("changes tone and requests updated post payload", async () => {
    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("Post on 𝕏 (1-Click)")).toBeInTheDocument()
    })

    const nudgeBtn = screen.getByRole("button", { name: /Civic Nudge/ })
    fireEvent.click(nudgeBtn)

    expect(reportsApi.getSocialPost).toHaveBeenCalledWith("rep-123", "nudge")
  })

  it("renders accessible modal dialog with aria-labelledby and handles Escape key", async () => {
    const handleClose = vi.fn()
    render(<SocialAmplifyModal reportId="rep-123" isOpen={true} onClose={handleClose} />)

    const dialog = screen.getByRole("dialog")
    expect(dialog).toBeInTheDocument()
    expect(dialog).toHaveAttribute("aria-modal", "true")
    expect(dialog).toHaveAttribute("aria-labelledby", "social-amplify-title")

    fireEvent.keyDown(window, { key: "Escape" })
    expect(handleClose).toHaveBeenCalledTimes(1)
  })

  it("renders WhatsApp mobilization tab with formatted group text", async () => {
    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("Post on 𝕏 (1-Click)")).toBeInTheDocument()
    })

    const waTab = screen.getByRole("button", { name: /WhatsApp & Groups/ })
    fireEvent.click(waTab)

    expect(screen.getByText("Mobilize Local RWA & Resident Groups")).toBeInTheDocument()
    expect(screen.getByText("Share to WhatsApp")).toBeInTheDocument()
    expect(screen.getByText("Copy Report Link")).toBeInTheDocument()
  })

  it("triggers official bot escalation and renders simulated sandbox outcome", async () => {
    vi.mocked(reportsApi.broadcastSocialPost).mockResolvedValue({
      id: "b-sim-123",
      status: "simulated",
      report_id: "rep-123",
      ticket_no: "TK-2026-BLR-001",
      message: "Broadcast intent recorded for report #TK-2026-BLR-001 (simulated: sandbox mode).",
      published_url: null,
    })

    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("Escalate Bot")).toBeInTheDocument()
    })

    const escalateBtn = screen.getByRole("button", { name: "Escalate Bot" })
    fireEvent.click(escalateBtn)

    await waitFor(() => {
      expect(screen.getByText("Sandbox Simulated")).toBeInTheDocument()
    })

    expect(screen.getByText(/Broadcast intent recorded for report #TK-2026-BLR-001/)).toBeInTheDocument()
  })

  it("renders confirmed published 𝕏 link when broadcast is published", async () => {
    vi.mocked(reportsApi.getSocialBroadcastStatus).mockResolvedValue({
      id: "b-pub-456",
      status: "published",
      report_id: "rep-123",
      ticket_no: "TK-2026-BLR-001",
      message: "Official civic bot broadcast published for report #TK-2026-BLR-001.",
      published_url: "https://x.com/TheekKaro/status/1840001112223334445",
      external_post_id: "1840001112223334445",
    })

    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("✓ Published")).toBeInTheDocument()
    })

    const link = screen.getByRole("link", { name: /View Confirmed Post on 𝕏/ })
    expect(link).toHaveAttribute("href", "https://x.com/TheekKaro/status/1840001112223334445")
  })

  it("displays queued status and prevents duplicate escalation requests while pending", async () => {
    vi.mocked(reportsApi.getSocialBroadcastStatus).mockResolvedValue({
      id: "b-queue-789",
      status: "queued",
      report_id: "rep-123",
      ticket_no: "TK-2026-BLR-001",
      message: "Broadcast task queued for report #TK-2026-BLR-001.",
      published_url: null,
    })

    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("Queued")).toBeInTheDocument()
    })

    // Escalate button is replaced by status indicator, preventing duplicate request
    expect(screen.queryByRole("button", { name: "Escalate Bot" })).not.toBeInTheDocument()
  })

  it("displays failure state and allows retry", async () => {
    vi.mocked(reportsApi.getSocialBroadcastStatus).mockResolvedValue({
      id: "b-fail-101",
      status: "failed",
      report_id: "rep-123",
      ticket_no: "TK-2026-BLR-001",
      message: "Broadcast failed: Provider error",
      published_url: null,
    })

    render(<SocialAmplifyModal reportId="rep-123" embedded={true} />)

    await waitFor(() => {
      expect(screen.getByText("Retry Escalation")).toBeInTheDocument()
    })

    expect(screen.getByText("Broadcast failed: Provider error")).toBeInTheDocument()
  })
})
