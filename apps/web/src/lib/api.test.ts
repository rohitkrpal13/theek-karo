import { describe, expect, it, beforeEach, vi } from "vitest"
import {
  api,
  ApiError,
  buildQueryString,
  getToken,
  setToken,
} from "./api"

describe("api client utilities", () => {
  beforeEach(() => {
    setToken(null)
    vi.restoreAllMocks()
  })

  it("buildQueryString formats valid parameters safely", () => {
    expect(buildQueryString()).toBe("")
    expect(buildQueryString({})).toBe("")
    expect(
      buildQueryString({
        q: "school",
        limit: 10,
        empty: "",
        nil: null,
        undef: undefined,
      }),
    ).toBe("?q=school&limit=10")
  })

  it("manages localStorage access token correctly", () => {
    expect(getToken()).toBeNull()
    setToken("test-jwt-token")
    expect(getToken()).toBe("test-jwt-token")
    setToken(null)
    expect(getToken()).toBeNull()
  })

  it("parses successful JSON response", async () => {
    const mockData = { id: "geo-1", name: "Bihar" }
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    } as Response)

    const res = await api.get<{ id: string; name: string }>("/geography/geo-1")
    expect(res).toEqual(mockData)
  })

  it("handles 204 No Content safely", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: async () => ({}),
    } as Response)

    const res = await api.delete("/reports/123/follow")
    expect(res).toBeUndefined()
  })

  it("throws ApiError on HTTP error with RFC 9457 body", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        type: "https://api.theekkar.in/errors/not-found",
        title: "Not Found",
        status: 404,
        detail: "Institution not found",
      }),
    } as Response)

    await expect(api.get("/institutions/invalid-id")).rejects.toThrowError(
      ApiError,
    )
  })
})
