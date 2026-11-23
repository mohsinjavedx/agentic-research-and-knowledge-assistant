import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "proxy.spec.ts",
  workers: 1,
  timeout: 90_000,
  reporter: "list",
  outputDir: "test-results/proxy",
  use: { baseURL: "http://127.0.0.1:3101" },
  webServer: {
    command: "npm run dev -- --port 3101",
    url: "http://127.0.0.1:3101",
    env: { API_INTERNAL_URL: "http://127.0.0.1:18005", PHASE7_PROXY_TEST: "1" },
    timeout: 120_000,
  },
});
