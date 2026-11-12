import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  testMatch: process.env.ACERO_REAL_SMOKE
    ? "**/backend-smoke.spec.ts"
    : "**/workstation.spec.ts",
  use: {
    baseURL: process.env.ACERO_REAL_SMOKE
      ? "http://127.0.0.1:8011"
      : "http://127.0.0.1:5175",
    trace: "retain-on-failure",
    channel:
      process.env.PLAYWRIGHT_CHANNEL ||
      (process.platform === "win32" ? "msedge" : "chromium"),
    permissions: ["camera"],
    launchOptions: {
      args: [
        "--use-fake-device-for-media-stream",
        "--use-fake-ui-for-media-stream",
      ],
    },
  },
  projects: [
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  webServer: process.env.ACERO_REAL_SMOKE
    ? undefined
    : {
        command: "npm run dev -- --host 127.0.0.1 --port 5175",
        url: "http://127.0.0.1:5175/static/",
        reuseExistingServer: false,
      },
});
