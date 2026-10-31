import { ADMIN_URL, API } from "../lib/env";
import { bearer, createVerifiedClient, signInWeb } from "../lib/accounts";
import { cleanup, readyProvider } from "../lib/backend";
import { expect, test } from "../lib/fixtures";

test.describe("access from the browser", () => {
  const emails: string[] = [];
  test.afterAll(async () => {
    await cleanup(emails);
  });

  test("signed-out visitors are sent to sign in", async ({ page }) => {
    for (const path of ["/account", "/account/requests", "/me/provider"]) {
      await page.goto(path);
      await expect(page).toHaveURL(new RegExp(`/login\\?returnTo=${encodeURIComponent(path)}`));
    }
    for (const path of ["/", "/users", "/settings", "/access/approvals", "/marketplace/payouts"]) {
      await page.goto(`${ADMIN_URL}${path}`);
      await expect(page).toHaveURL(new RegExp(`^${ADMIN_URL}/login`));
      await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
    }
  });

  test("a client can't open or change another client's hire", async ({ page, request }) => {
    const provider = await readyProvider();
    const owner = await createVerifiedClient(request, "owner");
    const other = await createVerifiedClient(request, "other");
    emails.push(owner.email, other.email);
    const title = `e2e-suite: private hire ${Date.now()}`;
    const made = await request.post(`${API}/hires`, {
      headers: bearer(owner.token),
      data: { provider_id: provider.slug, title, client_name: "E2E Suite Owner", client_phone: "0911000000" },
    });
    expect(made.status(), await made.text()).toBe(201);
    const id = (await made.json()).payload.hire.id;

    for (const action of ["cancel", "pay", "dispute", "complete"]) {
      const res = await request.post(`${API}/hires/${id}/${action}`, {
        headers: bearer(other.token),
        data: { reason: "e2e-suite: not my hire" },
      });
      expect([403, 404], `${action} on someone else's hire answered ${res.status()}`).toContain(res.status());
    }
    const review = await request.post(`${API}/hires/${id}/review`, {
      headers: bearer(other.token),
      data: { rating: 1, comment: "e2e-suite: not my hire" },
    });
    expect([403, 404, 409, 422]).toContain(review.status());
    expect(review.status()).not.toBe(201);

    const list = await request.get(`${API}/hires`, { headers: bearer(other.token) });
    expect((await list.json()).payload.items.map((h: { id: string }) => h.id)).not.toContain(id);
    const mine = await request.get(`${API}/hires`, { headers: bearer(owner.token) });
    const still = (await mine.json()).payload.items.find((h: { id: string }) => h.id === id);
    expect(still.status, "the hire is untouched").toBe("requested");

    // The other client's page doesn't show it either
    await signInWeb(page, other.email, other.password, "/account/requests");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByText(title)).toHaveCount(0);
  });

  test("a public account's token can't call staff endpoints", async ({ request }) => {
    const client = await createVerifiedClient(request, "notstaff");
    emails.push(client.email);
    const calls: [string, string][] = [
      ["GET", "/admin/settings"],
      ["GET", "/admin/users"],
      ["GET", "/admin/access/approvals"],
      ["GET", "/admin/marketplace/payments"],
      ["PATCH", "/admin/settings"],
    ];
    for (const [method, path] of calls) {
      const withToken = await request.fetch(`${API}${path}`, {
        method,
        headers: bearer(client.token),
        data: method === "PATCH" ? { values: { payout_hold_days: 0 } } : undefined,
      });
      expect([401, 403], `${method} ${path} with a public token answered ${withToken.status()}`).toContain(withToken.status());
      const anonymous = await request.fetch(`${API}${path}`, { method });
      expect([401, 403]).toContain(anonymous.status());
    }
    const me = await request.get(`${API}/staff/me`, { headers: bearer(client.token) });
    expect([401, 403]).toContain(me.status());
  });
});
