import { defineConfig, devices } from "@playwright/test";
import { CHROME, WEB_URL } from "./lib/env";

const CI = !!process.env.CI;
const cnTest = /\.cn\.test\b/.test(`${process.env.E2E_WEB_URL ?? ""}${process.env.E2E_API_URL ?? ""}`);

/** The rehearsal stack's *.cn.test names point at this machine; its certificates are self-signed. */
const args = cnTest ? ["--host-resolver-rules=MAP *.cn.test 127.0.0.1"] : [];

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results",
  globalSetup: "./global-setup.ts",
  globalTeardown: "./global-teardown.ts",
  // Dev servers compile pages on first visit, so allow for a slow first load
  timeout: 90_000,
  expect: { timeout: 15_000 },
  retries: CI ? 1 : 0,
  // The specs share one database and one money setting; one at a time keeps them from stepping on each other
  workers: Number(process.env.E2E_WORKERS ?? 1),
  fullyParallel: false,
  forbidOnly: CI,
  reporter: CI ? [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]] : [["list"]],
  use: {
    baseURL: WEB_URL,
    ignoreHTTPSErrors: cnTest,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { executablePath: CHROME, args },
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1366, height: 900 } } },
    {
      name: "phone",
      // A 390px phone, on Chromium (devices["iPhone 13"] would need WebKit)
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
});
