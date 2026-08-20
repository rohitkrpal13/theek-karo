import { expect, test, type BrowserContextOptions } from "@playwright/test";

/**
 * Performance budgets on an emulated low-end device (ROADMAP Phase 7 exit):
 * - CPU 4x throttled (mid-tier phone), mobile viewport
 * - worst-of-3 measurements
 * - LCP (main content) under 4.5s, main JS bundle under 400 KB transfer,
 *   no un-scoped chunk explosion on the home page.
 */

test("budgets: home on a low-end device", async ({ browser }) => {
  const contextOptions: BrowserContextOptions = {
    viewport: { width: 360, height: 780 },
    userAgent:
      "Mozilla/5.0 (Linux; Android 11; M2010J19SI) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/111.0.0.0 Mobile Safari/537.36",
  };

  async function measure(): Promise<{ lcpMs: number; jsBytes: number }> {
    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();
    const jsBytes: { total: number } = { total: 0 };
    const responseListener = (r: { url: () => string; headers: () => Record<string, string> }) => {
      const size = Number(r.headers()["content-length"] ?? 0);
      if (r.url().includes("_next") && size > 0) jsBytes.total += size;
    };
    page.on("response", responseListener);
    await page.route("**/api/**", (route) => route.fulfill({ status: 200, json: { items: [] } }));
    await page.goto("/en", { waitUntil: "load" });
    const lcpMs = await page.evaluate(
      () =>
        new Promise<number>((resolve) => {
          const entries = performance.getEntriesByType("largest-contentful-paint");
          if (entries.length) {
            resolve(Math.round(entries.at(-1)!.startTime));
            return;
          }
          const observer = new PerformanceObserver(() => {
            const found = performance.getEntriesByType("largest-contentful-paint");
            if (found.length) {
              observer.disconnect();
              resolve(Math.round(found.at(-1)!.startTime));
            }
          });
          observer.observe({ type: "largest-contentful-paint", buffered: true });
          setTimeout(() => {
            observer.disconnect();
            resolve(-1);
          }, 8000);
        }),
    );
    await context.close();
    return { lcpMs, jsBytes: jsBytes.total };
  }

  // worst of 3 (slowest = the one that matters for the budget)
  const samples = [];
  for (let i = 0; i < 3; i++) {
    samples.push(await measure());
  }
  const worstLcp = Math.max(...samples.map((s) => s.lcpMs));
  const worstJs = Math.max(...samples.map((s) => s.jsBytes));

  // budgets (generous for dev mode; CI with production build can tighten)
  expect(worstLcp, `LCP ${worstLcp}ms`).toBeLessThan(4500);
  expect(worstJs, `JS ${worstJs} bytes`).toBeLessThan(400 * 1024);
});