import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { fireEvent, render, screen } from "@testing-library/react"
import { RealtimeAlertBanner } from "@/components/RealtimeAlertBanner"

const { publicAlertsMock } = vi.hoisted(() => ({
  publicAlertsMock: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "en" }),
}))

vi.mock("@/hooks/useRealtimeEvents", () => ({
  useRealtimeEvents: () => undefined,
}))

vi.mock("@/lib/api/realtime", () => ({
  realtimeApi: { publicAlerts: publicAlertsMock },
}))

describe("RealtimeAlertBanner", () => {
  beforeEach(() => {
    publicAlertsMock.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it("shows a retry after a load failure and recovers", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    publicAlertsMock
      .mockRejectedValueOnce(new Error("network unavailable"))
      .mockResolvedValueOnce({
        items: [
          {
            id: "alert-1",
            title: "Water interruption",
            summary: "Service is temporarily unavailable.",
            severity: "warning",
            status: "published",
            verified: true,
            expires_at: null,
            created_at: "2026-10-14T12:00:00Z",
          },
        ],
      })

    render(<RealtimeAlertBanner />)

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Civic alerts couldn't be loaded.",
    )
    fireEvent.click(screen.getByRole("button", { name: "Try again" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Water interruption")
    expect(publicAlertsMock).toHaveBeenCalledTimes(2)
  })

  it("renders only verified published alerts that have not expired", async () => {
    publicAlertsMock.mockResolvedValueOnce({
      items: [
        {
          id: "valid",
          title: "Valid alert",
          summary: "Current public notice.",
          severity: "info",
          status: "published",
          verified: true,
          expires_at: null,
          created_at: "2026-10-14T12:00:00Z",
        },
        {
          id: "unverified",
          title: "Unverified alert",
          summary: "This should not appear.",
          severity: "warning",
          status: "published",
          verified: false,
          expires_at: null,
          created_at: "2026-10-14T12:00:00Z",
        },
        {
          id: "expired",
          title: "Expired alert",
          summary: "This should not appear either.",
          severity: "critical",
          status: "published",
          verified: true,
          expires_at: "2000-01-01T00:00:00Z",
          created_at: "2000-01-01T00:00:00Z",
        },
      ],
    })

    render(<RealtimeAlertBanner />)

    expect(await screen.findByRole("alert")).toHaveTextContent("Valid alert")
    expect(screen.queryByText("Unverified alert")).not.toBeInTheDocument()
    expect(screen.queryByText("Expired alert")).not.toBeInTheDocument()
  })
})
