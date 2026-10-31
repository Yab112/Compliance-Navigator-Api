import type { APIRequestContext } from "@playwright/test";
import { ADMIN_URL, API, randomPassword, uniqueEmail } from "../lib/env";
import { bearer, signInAdmin, staffToken, type Staff } from "../lib/accounts";
import { cleanup, createStaff } from "../lib/backend";
import { expect, test } from "../lib/fixtures";

const KEY = "payout_hold_days";
const LABEL = "Hold new earnings for";

type Field = { key: string; value: number; is_default: boolean };

async function holdDays(request: APIRequestContext, token: string): Promise<Field> {
  const res = await request.get(`${API}/admin/settings`, { headers: bearer(token) });
  expect(res.ok(), await res.text()).toBeTruthy();
  const groups: { fields: Field[] }[] = (await res.json()).payload.groups;
  return groups.flatMap((g) => g.fields).find((f) => f.key === KEY)!;
}

/** A money change from `asker`, approved by `approver`, all through the API. */
async function changeWithApproval(request: APIRequestContext, asker: string, approver: string, original: Field) {
  const asked = original.is_default
    ? await request.delete(`${API}/admin/settings/${KEY}`, { headers: bearer(asker) })
    : await request.patch(`${API}/admin/settings`, { headers: bearer(asker), data: { values: { [KEY]: original.value } } });
  if (asked.status() === 200) return; // waived (nobody else could approve) or nothing to do
  expect(asked.status(), await asked.text()).toBe(202);
  const id = (await asked.json()).payload.approval.id;
  const done = await request.post(`${API}/admin/access/approvals/${id}/approve`, {
    headers: bearer(approver),
    data: { note: "e2e-suite: restore after the test" },
  });
  expect(done.status(), await done.text()).toBe(200);
}

test.describe("staff app", () => {
  const first: Staff = { email: uniqueEmail("staff-a"), password: randomPassword(), fullname: "E2E Suite Staff A" };
  const second: Staff = { email: uniqueEmail("staff-b"), password: randomPassword(), fullname: "E2E Suite Staff B" };
  let original: Field | null = null;

  test.beforeAll(async () => {
    await createStaff(first.email, first.fullname, first.password);
    await createStaff(second.email, second.fullname, second.password);
  });

  test.afterAll(async ({ request }) => {
    try {
      if (original) {
        const [a, b] = [await staffToken(request, first), await staffToken(request, second)];
        const now = await holdDays(request, a);
        if (now.value !== original.value || now.is_default !== original.is_default) await changeWithApproval(request, a, b, original);
        const back = await holdDays(request, a);
        expect(back.value, "the setting is back to what it was").toBe(original.value);
      }
    } finally {
      await cleanup([first.email, second.email]);
    }
  });

  test("staff signs in, the menus open and navigate, Overview shows its numbers", async ({ page, consoleErrors }) => {
    await signInAdmin(page, first);
    await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
    for (const stat of ["Registered users", "Approved providers", "Open hires", "MESOB services"]) {
      await expect(page.getByText(stat, { exact: true })).toBeVisible();
    }

    const nav = page.getByRole("navigation", { name: "Staff sections" });
    const visits: [string, string, RegExp][] = [
      ["Marketplace", "Hires and complaints", /\/marketplace\/hires$/],
      ["Money", "Payouts", /\/marketplace\/payouts$/],
      ["People", "Public users", /\/users$/],
      ["Administration", "Platform settings", /\/settings$/],
    ];
    for (const [menu, item, url] of visits) {
      await nav.getByRole("button", { name: menu }).click();
      await page.getByRole("menuitem", { name: item }).click();
      await expect(page).toHaveURL(url);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    }
    await nav.getByRole("link", { name: "Overview" }).click();
    await expect(page).toHaveURL(`${ADMIN_URL}/`);

    // The session survives a reload
    await page.reload();
    await expect(nav).toBeVisible();
    await expect(page.getByLabel("Password", { exact: true })).toHaveCount(0);
    expect(consoleErrors.errors).toEqual([]);
  });

  test("the staff app serves a favicon", async ({ request }) => {
    const res = await request.get(`${ADMIN_URL}/favicon.ico`);
    expect(res.status()).toBe(200);
  });

  test("a money setting change needs a second staff member", async ({ page, browser, request }, testInfo) => {
    // One shared setting: change it once per run, on the desktop layout
    test.skip(testInfo.project.name !== "desktop", "Runs once, on desktop; the phone run covers sign-in and menus");
    const tokenA = await staffToken(request, first);
    original = await holdDays(request, tokenA);
    const next = original.value >= 60 ? original.value - 1 : original.value + 1;

    await signInAdmin(page, first);
    await page.goto(`${ADMIN_URL}/settings?group=money`);
    await page.getByLabel(LABEL).fill(String(next));
    await page.getByRole("button", { name: "Save 1 change" }).click();
    await expect(page.getByRole("status")).toContainText("sent to Approvals");
    expect((await holdDays(request, tokenA)).value, "nothing changes before approval").toBe(original.value);

    // The asker sees their request but can't approve it
    await page.goto(`${ADMIN_URL}/access/approvals?box=mine`);
    const mine = page.getByRole("listitem").filter({ hasText: `${LABEL}:` }).filter({ hasText: first.email }).first();
    await expect(mine).toBeVisible();
    await expect(mine.getByRole("button", { name: "Cancel my request" })).toBeVisible();
    await expect(mine.getByRole("button", { name: "Approve and carry out" })).toHaveCount(0);
    const pending = await request.get(`${API}/admin/access/approvals`, { headers: bearer(tokenA), params: { box: "mine" } });
    const request0 = (await pending.json()).payload.items.find(
      (a: { status: string; requested_by_email: string }) => a.status === "pending" && a.requested_by_email === first.email,
    );
    expect(request0, "the request is listed for its asker").toBeTruthy();
    const self = await request.post(`${API}/admin/access/approvals/${request0.id}/approve`, { headers: bearer(tokenA), data: { note: "mine" } });
    expect(self.status()).toBe(403);

    // A second staff member approves it in their own browser
    const other = await browser.newContext({ viewport: page.viewportSize() });
    const page2 = await other.newPage();
    try {
      await signInAdmin(page2, second);
      await page2.goto(`${ADMIN_URL}/access/approvals`);
      const card = page2.getByRole("listitem").filter({ hasText: `${LABEL}:` }).filter({ hasText: first.email }).first();
      await card.getByRole("button", { name: "Approve and carry out" }).click();
      await expect(page2.getByText(/Approved\. The change has been made/)).toBeVisible();
    } finally {
      await other.close();
    }
    expect((await holdDays(request, tokenA)).value).toBe(next);
  });
});
