import { expect, test } from "@playwright/test";

test.describe("core flows (live API through the Next proxy)", () => {
  test("home renders the new landing experience", async ({ page }) => {
    await page.goto("/en");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Find what needs to be improved");
    await expect(page.getByRole("link", { name: "Explore" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Submit a report" }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Map" }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Recent reports" }).first()).toBeVisible();
  });

  test("full submit flow with OTP registration", async ({ page }) => {
    test.setTimeout(240_000);
    await page.goto("/en/auth/register");
    const phone = `9${Math.floor(9e8 + Math.random() * 9e8)}`;
    await page.getByLabel(/Display name/).fill("E2E Tester");
    await page.getByLabel(/Email or phone/).fill(phone);
    await page.getByLabel(/^Password/).fill("s3cure-pass!");
    await page.getByRole("checkbox", { name: /I agree to the Terms of Service/ }).check();
    await page.getByRole("button", { name: /Create free account/ }).click();

    // the register endpoint rate-limits (10/min/IP) — tolerate one backoff retry
    const devCode = page.getByText(/Dev OTP:/).first();
    const alert = page.getByRole("alert").first();
    try {
      await expect(devCode).toBeVisible({ timeout: 10_000 });
    } catch {
      const alertText = (await alert.textContent().catch(() => "")) ?? ""
      if (alertText.includes("429") || /rate|limit/i.test(alertText)) {
        await page.waitForTimeout(65_000)
        await page.getByRole("button", { name: /Create free account/ }).click()
        await expect(devCode).toBeVisible({ timeout: 15_000 }).catch(() => undefined)
      } else {
        throw new Error(`register failed unexpectedly: ${alertText}`)
      }
      await expect(devCode).toBeVisible({ timeout: 10_000 });
    }
    const code = (await devCode.textContent()) ?? "";
    await page.getByLabel(/One-time code/).fill(code.trim());
    await page.getByRole("button", { name: /Verify & sign in/ }).click();
    await expect(page).toHaveURL(/\/en\/?$/);

    // now submit a report through the wizard
    await page.goto("/en/submit");
    await page.getByRole("button", { name: "Close Next.js Dev Tools" }).click({ timeout: 3000 }).catch(() => {});
    await page.getByText("Select Civic Domain Category").waitFor({ timeout: 20_000 });
    await page.getByRole("button", { name: /school/i }).first().click();
    const next = async () => {
      const btn = page.locator('[data-testid="wizard-next"]:not([disabled])');
      await btn.focus();
      await page.keyboard.press("Enter");
    };
    await next(); // step 1: shared location — supply non-zero coordinates
    await page.getByLabel(/Latitude/).fill("28.6139");
    await page.getByLabel(/Longitude/).fill("77.2090");
    await next(); // step 2: institution (optional)
    await next(); // step 3: details
    const typeSel = page.getByRole("combobox", { name: /Specific Issue Type/ });
    if (await typeSel.count()) await typeSel.selectOption({ index: 1 });
    await page.getByLabel(/Issue Title/).fill("Broken classroom window on ground floor");
    await page.getByLabel(/Severity Level/).selectOption("medium");
    await page.getByLabel(/Detailed Description/).fill("Windows on the ground floor remain broken since May with sharp edges near the corridor");
    const dynFields = page.locator('input[id^="field-"]:visible');
    const dynCount = await dynFields.count();
    for (let i = 0; i < dynCount; i++) {
      await dynFields.nth(i).fill(i < dynCount && (await dynFields.nth(i).getAttribute("type")) === "number" ? "1" : "test value");
    }
    await next(); // step 4: evidence (optional)
    await next(); // step 5: review
    const submitBtn = page.getByRole("button", { name: /Submit report/ });
    await submitBtn.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByText(/Report submitted!/)).toBeVisible();

    // activity feed shows the new report
    await page.goto("/en/activity");
    await expect(page.getByRole("link", { name: /Broken classroom window/ }).first()).toBeVisible();
  });

  test("report detail shows stepper and verification controls", async ({ page }) => {
    await page.goto("/en/explore");
    const first = page.locator("a", { hasText: /Broken classroom window|Windows/ }).first();
    try {
      await first.waitFor({ state: "visible", timeout: 8000 });
    } catch {
      test.skip(true, "no reports on this API instance");
    }
    await first.click();
    await expect(page.getByRole("heading", { name: "Verification", exact: false }).first()).toBeVisible();
    await expect(page.getByText(/Submitted/).first()).toBeVisible();
  });

  test("hindi locale renders", async ({ page }) => {
    await page.goto("/hi");
    await expect(page.locator("html")).toHaveAttribute("lang", "hi");
    const mobileNav = page.getByRole("navigation", { name: "Primary mobile" });
    await expect(mobileNav.getByText("होम")).toBeVisible();
    await expect(mobileNav.getByText("रिपोर्ट करें")).toBeVisible();
  });
});