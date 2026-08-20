import { afterEach, describe, expect, it, vi } from "vitest"

import { intelligenceApi } from "@/lib/api/intelligence"

const mockDashboard = {
  generated_at: "2026-08-18T10:00:00Z",
  geography_name: null,
  sections: [
    {
      key: "trends",
      title: "Trend comparison",
      data: {
        direction: "increasing",
        change_pct: 12.5,
        series: [{ timestamp: "2026-08-11", value: 4 }],
      },
      limitations: ["Comparable-window ratio; no causation."],
    },
  ],
  methodology_note: "Deterministic engines over stored data.",
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe("intelligenceApi", () => {
  it("fetches the overview with preset params", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockDashboard,
    } as Response)

    const res = await intelligenceApi.overview({ date_preset: "90d" })

    expect(res.sections[0].data.direction).toBe("increasing")
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url] = fetchMock.mock.calls[0]
    expect(String(url)).toContain("/intelligence/overview?date_preset=90d")
  })

  it("lists signals with filters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        items: [
          {
            id: "sig-1",
            signal_type: "anomaly",
            title: "Water complaints spike",
            severity: "HIGH",
            confidence: "MEDIUM",
            status: "NEW",
            evidence_count: 2,
            source_count: 1,
            created_at: "2026-08-18T10:00:00Z",
            review_history: [],
          },
        ],
        count: 1,
        generated_at: "2026-08-18T10:00:00Z",
        note: "review triggers",
      }),
    } as Response)

    const res = await intelligenceApi.listSignals({ signal_status: "NEW", limit: 25 })

    expect(res.items[0].title).toBe("Water complaints spike")
    const [url] = fetchMock.mock.calls[0]
    expect(String(url)).toContain("/intelligence/signals?signal_status=NEW&limit=25")
  })

  it("posts a signal review", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: "sig-1", status: "CONFIRMED" }),
    } as Response)

    await intelligenceApi.reviewSignal("sig-1", { action: "CONFIRM", note: "verified" })

    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain("/intelligence/signals/sig-1/review")
    expect(JSON.parse(String(init?.body))).toEqual({ action: "CONFIRM", note: "verified" })
  })

  it("posts a forecast run request", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: "run-1",
        metric: "reports",
        horizon_days: 30,
        status: "queued",
        created_at: "2026-08-18T10:00:00Z",
        points: [],
      }),
    } as Response)

    const res = await intelligenceApi.runForecast({ horizon_days: 30, interval: "week" })

    expect(res.status).toBe("queued")
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain("/intelligence/forecasts")
    expect(JSON.parse(String(init?.body))).toMatchObject({ horizon_days: 30, interval: "week" })
  })

  it("throws ApiError on RFC 9457 failure", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        type: "…/errors/forbidden",
        title: "Forbidden",
        status: 403,
        detail: "department role required",
      }),
    } as Response)

    await expect(intelligenceApi.runForecast({})).rejects.toMatchObject({
      status: 403,
      body: { detail: "department role required" },
    })
  })
})
