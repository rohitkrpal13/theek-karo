import { expect, test } from "@playwright/test";
import axe from "axe-core";

/** Axe WCAG 2.2 AA scan of the public routes (mobile viewport). */

const ROUTES = [
  "/en", "/hi", "/en/explore", "/en/submit", "/en/map", "/en/activity",
  "/en/analytics", "/en/assistant", "/en/languages", "/en/notifications",
  "/en/profile", "/en/search", "/en/campaigns", "/en/government-data",
  "/en/institutions/00000000-0000-0000-0000-000000000000",
];

for (const route of ROUTES) {
  test(`axe: ${route} has no serious/critical violations`, async ({ page }) => {
    await page.goto(route);
    await page.addScriptTag({ content: axe.source });
    const results = (await page.evaluate(async () => {
      const runner = (window as unknown as { axe: typeof axe }).axe;
      return await runner.run(document, {
        rules: { "color-contrast": { enabled: true } },
      });
    })) as {
      violations: Array<{ impact: string; id: string; nodes: unknown[] }>;
    };
    const severe = results.violations.filter(
      (v) => v.impact === "serious" || v.impact === "critical",
    );
    expect(severe, JSON.stringify(results.violations, null, 2)).toEqual([]);
  });
}