import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { CivicAssistantChat } from "./CivicAssistantChat"
import { aiApi } from "@/lib/api/ai"

vi.mock("@/lib/api/ai", () => ({
  aiApi: {
    chat: vi.fn(),
    submitFeedback: vi.fn(),
  },
}))

describe("CivicAssistantChat", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.HTMLElement.prototype.scrollIntoView = vi.fn()
  })

  it("renders assistant header, greeting, and suggested queries", () => {
    render(<CivicAssistantChat />)

    expect(screen.getByText("Civic Intelligence Assistant")).toBeInTheDocument()
    expect(screen.getByText(/Evidence Grounded/i)).toBeInTheDocument()
    expect(screen.getByText(/I am the Theek Karo Evidence-Grounded/i)).toBeInTheDocument()
    expect(screen.getByText("Show unresolved school infrastructure issues in Patna")).toBeInTheDocument()
  })

  it("sends message, displays answer with citations and confidence label", async () => {
    vi.mocked(aiApi.chat).mockResolvedValueOnce({
      answer: "Patna schools show 3 unresolved drinking water reports.",
      conversation_id: "conv-123",
      citations: [
        {
          source_id: "src-1",
          dataset_name: "UDISE+ Portal 2026",
          publication_date: "2026-01-01",
          snippet: "Official records show drinking water functional.",
          url: "https://udiseplus.gov.in",
        },
      ],
      related_entities: [
        {
          id: "inst-99",
          kind: "institution",
          title: "Govt High School Patna",
        },
      ],
      suggested_followups: ["Which ward in Patna is affected?"],
      confidence_label: "high",
      model_id: "deepseek-chat",
      latency_ms: 320,
    })

    render(<CivicAssistantChat />)

    const input = screen.getByLabelText("Civic research question")
    fireEvent.change(input, { target: { value: "Water issues in Patna schools" } })

    const submitBtn = screen.getByRole("button", { name: /Ask Assistant/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(aiApi.chat).toHaveBeenCalledWith(
        expect.objectContaining({
          message: "Water issues in Patna schools",
          language: "en",
        })
      )
    })

    await waitFor(() => {
      expect(screen.getByText("Patna schools show 3 unresolved drinking water reports.")).toBeInTheDocument()
      expect(screen.getByText("UDISE+ Portal 2026")).toBeInTheDocument()
      expect(screen.getByText("Govt High School Patna")).toBeInTheDocument()
      expect(screen.getByText("high confidence")).toBeInTheDocument()
    })
  })

  it("opens provenance modal when citation badge is clicked", async () => {
    vi.mocked(aiApi.chat).mockResolvedValueOnce({
      answer: "Verified with official data.",
      conversation_id: "conv-123",
      citations: [
        {
          source_id: "src-1",
          dataset_name: "UDISE+ Portal 2026",
          publication_date: "2026-01-01",
          snippet: "Ground truth verbatim excerpt.",
          url: "https://udiseplus.gov.in",
        },
      ],
      related_entities: [],
      suggested_followups: [],
      confidence_label: "high",
      model_id: "stub-civic-v1",
      latency_ms: 150,
    })

    render(<CivicAssistantChat />)

    const input = screen.getByLabelText("Civic research question")
    fireEvent.change(input, { target: { value: "Check citations" } })
    fireEvent.click(screen.getByRole("button", { name: /Ask Assistant/i }))

    await waitFor(() => {
      expect(screen.getByText("UDISE+ Portal 2026")).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText("UDISE+ Portal 2026"))

    expect(screen.getByText("Official Source Provenance")).toBeInTheDocument()
    expect(screen.getByText("Ground truth verbatim excerpt.")).toBeInTheDocument()

    const closeBtn = screen.getByRole("button", { name: "Close" })
    fireEvent.click(closeBtn)

    await waitFor(() => {
      expect(screen.queryByText("Official Source Provenance")).not.toBeInTheDocument()
    })
  })
})
