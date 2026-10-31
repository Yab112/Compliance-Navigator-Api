import { API } from "../lib/env";
import { openAccountMenu } from "../lib/accounts";
import { expect, expectNoHorizontalScroll, test } from "../lib/fixtures";

// Read-only: these pages need no account and change nothing, so there is nothing to clean up

test.describe("public pages", () => {
  test("home page", async ({ page, consoleErrors }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalScroll(page);
    // Signed out, the header offers sign-in (inside the Menu on phones)
    await openAccountMenu(page);
    await expect(page.getByRole("link", { name: /Sign in/ }).first()).toBeVisible();
    expect(consoleErrors.errors).toEqual([]);
  });

  test("services search", async ({ page, consoleErrors }) => {
    await page.goto("/services");
    await expect(page.getByRole("heading", { name: /Services/ }).first()).toBeVisible();
    const search = page.getByLabel("Search services");
    await search.fill("passport");
    await expect(page).toHaveURL(/q=passport|query=passport|search=passport/);
    await expect(page.getByText(/^\d+ results?/)).toBeVisible();
    await expect(page.getByRole("listitem").filter({ hasText: /passport/i }).first()).toBeVisible();
    await expectNoHorizontalScroll(page);
    await search.fill("zzzz-no-such-service-e2e");
    await expect(page.getByText("No services match")).toBeVisible();
    expect(consoleErrors.errors).toEqual([]);
  });

  test("provider profile", async ({ page, request, consoleErrors }) => {
    const res = await request.get(`${API}/providers`, { params: { limit: 50 } });
    expect(res.ok()).toBeTruthy();
    const payload = (await res.json()).payload;
    const items = Array.isArray(payload) ? payload : payload.items;
    // The hire page opens on Guday Geday agents; agencies are a tab of their own
    const provider = items.find((p: { provider_type: string }) => p.provider_type === "guday_geday");
    test.skip(!provider, "No listed Guday Geday agent on this stack (run scripts.seed_providers)");

    await page.goto("/hire");
    await expect(page.getByRole("link", { name: provider.display_name, exact: true }).first()).toBeVisible();
    await page.goto(`/providers/${provider.slug}`);
    await expect(page.getByRole("heading", { level: 1, name: provider.display_name })).toBeVisible();
    // Signed out, the request form asks to sign in first
    await expect(page.getByText("Sign in to send a request")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expectNoHorizontalScroll(page);
    expect(consoleErrors.errors).toEqual([]);
  });

  for (const slug of ["terms", "privacy", "marketplace-rules", "refunds", "provider-agreement"]) {
    test(`legal page ${slug}`, async ({ page, consoleErrors }) => {
      const res = await page.goto(`/legal/${slug}`);
      expect(res?.status()).toBe(200);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText(/version/i).first()).toBeVisible();
      await expectNoHorizontalScroll(page);
      expect(consoleErrors.errors).toEqual([]);
    });
  }

  test("legal index and an unknown page", async ({ page }) => {
    await page.goto("/legal");
    await expect(page.getByRole("link", { name: "Terms of Service" }).first()).toBeVisible();
    const missing = await page.goto("/no-such-page-e2e");
    expect(missing?.status()).toBe(404);
  });
});
