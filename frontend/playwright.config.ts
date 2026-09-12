import { defineConfig, devices } from "@playwright/test";

const API_PORT = 8011;
const API_BASE = `http://127.0.0.1:${API_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `python -m backend.dashboard_dev_server`,
      cwd: "..",
      url: `${API_BASE}/api/dashboard/health`,
      env: { PORT: String(API_PORT) },
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: "npm run dev -- --port 3100",
      url: "http://127.0.0.1:3100",
      env: { NEXT_PUBLIC_API_BASE: API_BASE },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
