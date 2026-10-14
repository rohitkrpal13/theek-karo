import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { civicApi, reportsApi } from "@/lib/api"
import ReportsFeedPage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "en" }),
  useSearchParams: () => new URLSearchParams(),
}))

describe("ReportsFeedPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(civicApi, "listCategories").mockResolvedValue({ items: [] })
  })

  it("shows a retryable error instead of an empty feed when loading fails", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined)
    const listReports = vi
      .spyOn(reportsApi, "list")
      .mockRejectedValueOnce(new Error("Network unavailable"))
      .mockResolvedValueOnce({ items: [], next_cursor: null })

    render(<ReportsFeedPage />)

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn't load reports. Check your connection and try again.",
    )
    expect(
      screen.queryByText("No reports found matching your criteria."),
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole("button", { name: "Try again" }))

    await waitFor(() => {
      expect(listReports).toHaveBeenCalledTimes(2)
    })
    expect(
      await screen.findByText("No reports found matching your criteria."),
    ).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })
})
