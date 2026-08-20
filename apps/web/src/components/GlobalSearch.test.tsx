import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { describe, expect, it, vi, beforeEach } from "vitest"
import { GlobalSearch } from "./GlobalSearch"
import { searchApi } from "@/lib/api/search"

describe("GlobalSearch component", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it("renders search input with accessibility attributes", () => {
    render(<GlobalSearch />)
    const input = screen.getByRole("combobox")
    expect(input).toBeInTheDocument()
    expect(input).toHaveAttribute("placeholder", "Search institutions, locations, reports, categories…")
  })

  it("updates query and executes debounced search", async () => {
    const mockResults = {
      query: "hospital",
      domain: "all",
      total: 1,
      items: [
        {
          domain: "institution" as const,
          id: "inst-hosp-1",
          title: "District Civil Hospital",
          subtitle: "Patna",
          snippet: "Emergency healthcare facility",
          url: "/institutions/inst-hosp-1",
          relevance_score: 0.9,
          metadata: {},
        },
      ],
    }

    vi.spyOn(searchApi, "search").mockResolvedValueOnce(mockResults)

    render(<GlobalSearch isExpanded />)
    const input = screen.getByRole("combobox")

    fireEvent.change(input, { target: { value: "hospital" } })
    expect(input).toHaveValue("hospital")

    await waitFor(
      () => {
        expect(screen.getByText("District Civil Hospital")).toBeInTheDocument()
      },
      { timeout: 1000 },
    )
  })
})
