import { describe, expect, it, vi, beforeEach } from "vitest"

import { getCache, setCache, mutate, fetchWithCache } from "@/lib/cache"

describe("cache (SWR + persistence)", () => {
  beforeEach(() => {
    // clear memory via mutate null
    mutate("test-key", null)
    localStorage.clear()
  })

  it("sets and gets cache", () => {
    setCache("k1", { a: 1 })
    expect(getCache("k1")).toEqual({ a: 1 })
  })

  it("mutate null deletes", () => {
    setCache("k1", { a: 1 })
    mutate("k1", null)
    expect(getCache("k1")).toBeNull()
  })

  it("fetchWithCache dedupes in-flight", async () => {
    let calls = 0
    const fetcher = async (): Promise<number> => {
      calls += 1
      await new Promise((r) => setTimeout(r, 5))
      return 42
    }
    const p1 = fetchWithCache("dedup-key", fetcher)
    const p2 = fetchWithCache("dedup-key", fetcher)
    const [v1, v2] = await Promise.all([p1, p2])
    expect(v1).toBe(42)
    expect(v2).toBe(42)
    expect(calls).toBe(1)
  })

  it("fetchWithCache fetches fresh when no cache", async () => {
    const fetcher = vi.fn(async () => ({ v: 2 }))
    const data = await fetchWithCache("fresh-key", fetcher, { ttlMs: 10000 })
    expect(data).toEqual({ v: 2 })
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(getCache("fresh-key")).toEqual({ v: 2 })
  })
})
