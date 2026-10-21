"use client"

export function reportWebVitals(): void {
  if (typeof window === "undefined") return
  try {
    // CLS, LCP, INP, FCP via PerformanceObserver when available
    const obs = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        // send to console in dev, to /api/v1/telemetry in prod if needed
        if (process.env.NODE_ENV === "development") {
          console.debug("[vitals]", entry.name, Math.round(entry.startTime), entry)
        }
      }
    })
    obs.observe({ type: "largest-contentful-paint", buffered: true } as unknown as PerformanceObserverInit)
    obs.observe({ type: "layout-shift", buffered: true } as unknown as PerformanceObserverInit)
  } catch {}
}

export function useVitals(): void {
  if (typeof window === "undefined") return
  // Next.js will call reportWebVitals from next.config if we export it in _app, but App Router uses manual observer
  reportWebVitals()
}
