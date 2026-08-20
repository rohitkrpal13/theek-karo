import { defineConfig, devices } from "@playwright/test";

const PORT = 3100;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    locale: "en-IN",
    viewport: { width: 390, height: 844 }, // common low-end phone viewport
  },
  projects: [
    {
      name: "mobile",
      testIgnore: /performance\.spec\.ts/,
      use: { ...devices["Pixel 5"] },
    },
    {
      name: "budget",
      testMatch: /performance\.spec\.ts/,
      use: { ...devices["Pixel 5"] },
    },
  ],

  webServer: {
    command: `npm run dev -- --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/en`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});