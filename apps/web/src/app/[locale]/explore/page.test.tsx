import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  civicApi,
  geographyApi,
  gisApi,
  institutionsApi,
  reportsApi,
} from "@/lib/api"
import ExplorePage from "./page"

vi.mock("next/navigation", () => ({
  useParams: () => ({ locale: "en" }),
  useSearchParams: () => new URLSearchParams(),
}))

describe("ExplorePage institution discovery", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(civicApi, "listCategories").mockResolvedValue({ items: [] })
    vi.spyOn(geographyApi, "listTypes").mockResolvedValue([])
    vi.spyOn(geographyApi, "list").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      limit: 40,
      pages: 0,
    })
    vi.spyOn(institutionsApi, "listTypes").mockResolvedValue([])
    vi.spyOn(institutionsApi, "list").mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      limit: 20,
      pages: 0,
    })
    vi.spyOn(reportsApi, "list").mockResolvedValue({
      items: [],
      next_cursor: null,
    })
  })

  it("loads server-backed suggestions and applies a selected institution", async () => {
    const institution = {
      id: "school-1",
      name: "Jaipur Public School",
      address: "Jaipur",
      institution_type_id: "school-type",
      normalized_name: "jaipur public school",
      official_identifier: null,
      geography_id: null,
      operational_status: "operational",
      verification_state: "official",
      created_at: "",
      updated_at: "",
    }
    const listInstitutions = vi.spyOn(institutionsApi, "list")
    listInstitutions.mockResolvedValue({
      items: [institution],
      total: 1,
      page: 1,
      limit: 5,
      pages: 1,
    })

    render(<ExplorePage />)
    fireEvent.change(screen.getByRole("combobox", { name: "Find an institution" }), {
      target: { value: "Jaipur" },
    })

    await waitFor(() => {
      expect(listInstitutions).toHaveBeenCalledWith(
        { q: "Jaipur", type_id: undefined, limit: 5 },
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })
    fireEvent.keyDown(screen.getByRole("combobox", { name: "Find an institution" }), {
      key: "ArrowDown",
    })
    expect(screen.getByRole("option", { name: /Jaipur Public School/ })).toHaveAttribute(
      "aria-selected",
      "true",
    )
    fireEvent.keyDown(screen.getByRole("combobox", { name: "Find an institution" }), {
      key: "Enter",
    })

    await waitFor(() => {
      expect(listInstitutions).toHaveBeenCalledWith(
        expect.objectContaining({ q: "Jaipur Public School", limit: 20 }),
      )
    })
    expect(screen.getByRole("tab", { name: /Public Institutions/ })).toHaveAttribute(
      "aria-selected",
      "true",
    )
  })

  it("uses the device location for a first-party nearby lookup", async () => {
    const position = {
      coords: { latitude: 26.9, longitude: 75.7 },
    } as GeolocationPosition
    Object.defineProperty(navigator, "geolocation", {
      configurable: true,
      value: {
        getCurrentPosition: vi.fn((success: PositionCallback) => success(position)),
      },
    })
    vi.spyOn(gisApi, "mapNearby").mockResolvedValue({
      center: { lat: 26.9, lng: 75.7 },
      radius_m: 5000,
      total_count: 1,
      reports: [],
      institutions: [
        {
          id: "school-1",
          name: "Jaipur Public School",
          type_code: "school",
          type_name: "School",
          operational_status: "operational",
          location: { type: "Point", coordinates: [75.7, 26.9] },
          distance_m: 450,
        },
      ],
    })

    render(<ExplorePage />)
    fireEvent.click(screen.getByRole("button", { name: "Use my current location" }))

    await waitFor(() => {
      expect(gisApi.mapNearby).toHaveBeenCalledWith(
        26.9,
        75.7,
        5000,
        "institutions",
        undefined,
        20,
      )
    })
    expect(await screen.findByRole("link", { name: "Jaipur Public School" })).toHaveAttribute(
      "href",
      "/en/institutions/school-1",
    )
    expect(screen.getByText("Within 5 km")).toBeInTheDocument()
  })
})
