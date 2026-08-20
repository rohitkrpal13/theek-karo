import { expect, test } from "@playwright/test";

// Journey 3 (moderator) and Journey 4 (authority) run against the live API
// through the Next proxy. They depend on dev/test demo accounts seeded by
// `services/api/scripts/seed_demo_data.py` (dev-only; never enabled in prod).

const BASE = "/en";
const DEMO = { password: "DevPassw0rd!2026" };

async function registerCitizen(
  request: { post: (u: string, o?: object) => Promise<{ json: () => Promise<Record<string, unknown>>; status: () => number }> },
) {
  const contact = `9${Math.floor(9e8 + Math.random() * 9e8)}`;
  const reg = await request.post(`/api/v1/auth/register`, {
    data: {
      contact,
      display_name: `Journey Citizen ${contact.slice(-4)}`,
      consent: true,
      terms_version: "2026-08-01",
    },
  });
  expect(reg.status()).toBe(201);
  const regBody = await reg.json();
  expect(regBody?.detail, JSON.stringify(regBody).slice(0, 300)).toBeUndefined();
  const otp = regBody.dev_otp_code as string;
  const ver = await request.post(`/api/v1/auth/verify-otp`, { data: { contact, code: otp } });
  expect(ver.status()).toBe(200);
  const verBody = await ver.json();
  return { contact, token: verBody.access_token as string };
}

async function loginViaApi(
  request: { post: (u: string, o?: object) => Promise<{ json: () => Promise<Record<string, unknown>>; status: () => number }> },
  contact: string,
  password: string,
) {
  const resp = await request.post(`/api/v1/auth/login`, { data: { contact, password } });
  expect(resp.status()).toBe(200);
  const body = await resp.json();
  return body.access_token as string;
}

test.describe("journey 3 — moderator reviews and verifies a citizen report", () => {
  test("citizen reports, moderator verifies via the UI", async ({ page, request }) => {
    test.setTimeout(180_000);
    const { token } = await registerCitizen(request);
    const authr = (init: object) => ({ ...init, headers: { ...(init as { headers?: Record<string, string> }).headers, Authorization: `Bearer ${token}` } });

    const report = await request.post(`/api/v1/reports`, authr({
      data: {
        category_slug: "school",
        title: `Journey3 broken window ${Date.now()}`,
        description: "Glass pane shattered near the corridor with exposed edges",
        severity: "medium",
        location: { type: "Point", coordinates: [77.209, 28.6139] },
        location_accuracy_m: 15,
        coordinate_source: "USER_SELECTED",
        fields: { issue_area: "classroom" },
      },
    }));
    if (report.status() !== 201) {
      throw new Error(
        `REPORT-POST ${report.status()} BODY=${JSON.stringify(await report.json()).slice(0, 400)} TOKEN=${token.slice(0, 26)}`,
      );
    }
    const reportBody = await report.json();
    const reportId = reportBody.id ?? reportBody.report?.id ?? reportBody.ticket_no;

    // Switch to the moderator UI session
    await page.goto(`${BASE}/auth/login`);
    await page.getByRole("form", { name: "Log in with password" }).getByLabel(/Email or phone|contact/i).first().fill("moderator@theekkar.test");
    await page.getByLabel(/^Password/).fill(DEMO.password);
    await page.getByRole("button", { name: /Log in/ }).click();
    await expect(page).toHaveURL(/\/en\/?$/, { timeout: 20_000 });

    await page.goto(`${BASE}/reports/${reportId}`);
    const verifyHeading = page.getByRole("heading", { name: /Verification/i });
    await verifyHeading.waitFor({ timeout: 20_000 });
    const confirmBtn = page.getByRole("button", { name: /Confirm/i });
    await confirmBtn.click();
    const submitVrfBtn = page.getByRole("button", { name: /Submit Verification/i });
    await submitVrfBtn.click();
    await expect(page.getByText(/Verification recorded|Verified/i).first()).toBeVisible({ timeout: 20_000 });

    // The report is now verified and readable publicly
    await page.goto(`${BASE}/reports/${reportId}`);
    await expect(page.getByText(/Verified/i).first()).toBeVisible({ timeout: 20_000 });
  });
});

test.describe("journey 4 — authority responds and submits resolution proof", () => {
  test("officer handles an assigned case through the UI", async ({ page, request }) => {
    test.setTimeout(240_000);
    const { token: citizenToken } = await registerCitizen(request);
    const cAuth = (init: object) => ({ ...init, headers: { ...(init as { headers?: Record<string, string> }).headers, Authorization: `Bearer ${citizenToken}` } });

    const report = await request.post(`/api/v1/reports`, cAuth({
      data: {
        category_slug: "road",
        title: `Journey4 pothole ${Date.now()}`,
        description: "Deep pothole on the main road causing near misses during rain",
        severity: "high",
        location: { type: "Point", coordinates: [75.7873, 26.9124] },
        location_accuracy_m: 10,
        coordinate_source: "USER_SELECTED",
        fields: { issue_type: "pothole", lanes_affected: 1 },
      },
    }));
    if (report.status() !== 201) {
      throw new Error(
        `REPORT-POST ${report.status()} BODY=${JSON.stringify(await report.json()).slice(0, 400)} TOKEN=${citizenToken.slice(0, 26)}`,
      );
    }
    const reportBody = await report.json();
    const reportId = reportBody.id ?? reportBody.report?.id ?? reportBody.ticket_no;

    // Two verifications (moderator + officer) push trust ≥ 0.30 → "verified".
    // (UI verification is covered in journey 3; API calls here keep the case
    // creation precondition deterministic across repeated runs.)
    const modToken = await loginViaApi(request, "moderator@theekkar.test", DEMO.password);
    const mAuth = (init: object) => ({ ...init, headers: { ...(init as { headers?: Record<string, string> }).headers, Authorization: `Bearer ${modToken}` } });
    const v1 = await request.post(`/api/v1/reports/${reportId}/verifications`, mAuth({
      data: { kind: "confirm", notes: "seen on site" },
    }));
    expect(v1.status(), `VERIFY1 ${v1.status()} ${JSON.stringify(await v1.json()).slice(0, 200)}`).toBe(201);
    const officerToken = await loginViaApi(request, "officer@theekkar.test", DEMO.password);
    const oAuth = (init: object) => ({ ...init, headers: { ...(init as { headers?: Record<string, string> }).headers, Authorization: `Bearer ${officerToken}` } });
    const v2 = await request.post(`/api/v1/reports/${reportId}/verifications`, oAuth({
      data: { kind: "confirm", notes: "verified on field visit" },
    }));
    expect(v2.status(), `VERIFY2 ${v2.status()} ${JSON.stringify(await v2.json()).slice(0, 200)}`).toBe(201);

    let reportStatus = "";
    for (let i = 0; i < 10; i++) {
      const st = await (await request.get(`/api/v1/reports/${reportId}`, mAuth({}))).json();
      reportStatus = st.status as string;
      if (reportStatus === "verified") break;
      await page.waitForTimeout(500);
    }
    expect(reportStatus).toBe("verified");

    const depts = await request.get(`/api/v1/departments`, oAuth({}));
    const deptBody = await depts.json();
    const deptId = deptBody.items?.[0]?.id ?? deptBody[0]?.id;
    expect(deptId).toBeTruthy();

    const caseResp = await request.post(`/api/v1/cases`, oAuth({ data: { report_id: reportId, department_id: deptId } }));
    expect([201, 200, 409], `CASE-POST ${caseResp.status()} ${JSON.stringify(await caseResp.json()).slice(0, 200)}`).toContain(caseResp.status());
    const caseBody = await caseResp.json();
    const caseId = caseBody.id ?? caseBody.case?.id;
    expect(caseId, `CASE-ID from ${JSON.stringify(caseBody).slice(0, 200)}`).toBeTruthy();

    // Officer UI: open the case, post a public response, then submit resolution proof
    await page.goto(`${BASE}/auth/login`);
    await page.getByRole("form", { name: "Log in with password" }).getByLabel(/Email or phone|contact/i).first().fill("officer@theekkar.test");
    await page.getByLabel(/^Password/).fill(DEMO.password);
    await page.getByRole("button", { name: /Log in/ }).click();
    await expect(page).toHaveURL(/\/en\/?$/, { timeout: 20_000 });

    await page.goto(`${BASE}/cases/${caseId}`);
    await page.getByPlaceholder(/Write a response/).fill("Road repair crew dispatched; work scheduled this week.");
    await page.getByRole("button", { name: /Post response/ }).click();
    await expect(page.getByText(/Road repair crew dispatched/).first()).toBeVisible({ timeout: 20_000 });

    // Drive the case into "in_progress" via the API (staff transition), then
    // submit resolution proof through the UI.
    for (const to_status of ["under_review", "in_progress"]) {
      const tr = await request.post(`/api/v1/cases/${caseId}/transition`, oAuth({ data: { to_status, reason: "review and act" } }));
      expect(tr.status(), JSON.stringify(await tr.json()).slice(0, 200)).toBe(200);
    }

    await page.reload();
    await page.getByPlaceholder(/Explanation/).fill("Repair completed and surface relaid.");
    await page.getByPlaceholder(/Evidence notes/).fill("Asphalt relaid; photos attached in field report.");
    await page.getByRole("button", { name: /Submit resolution/ }).click();
    await expect(page.getByText(/Resolution submitted/).first()).toBeVisible({ timeout: 20_000 });
  });
});