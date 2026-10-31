import { API } from "../lib/env";
import { bearer, createVerifiedClient, signInWeb } from "../lib/accounts";
import { cleanup, notify } from "../lib/backend";
import { expect, test } from "../lib/fixtures";

test.describe("notification bell", () => {
  const emails: string[] = [];
  test.afterAll(async () => {
    await cleanup(emails);
  });

  test("shows the unread count and marks notifications read", async ({ page, request, consoleErrors }) => {
    const client = await createVerifiedClient(request, "bell");
    emails.push(client.email);
    const unread = async () =>
      (await (await request.get(`${API}/notifications`, { headers: bearer(client.token) })).json()).payload.unread as number;
    const before = await unread();
    await notify(client.email, "e2e-suite first note", "The first test notification.");
    await notify(client.email, "e2e-suite second note", "The second test notification.");
    const total = before + 2;

    await signInWeb(page, client.email, client.password, "/account");
    // A fresh load closes the phone menu that signing in opened
    await page.goto("/account");
    // One bell on each layout: the top bar on desktop, the slim bar on phones
    const bell = page.getByRole("button", { name: /^Notifications/ }).filter({ visible: true });
    await expect(bell).toHaveCount(1);
    await expect(bell).toHaveAccessibleName(`Notifications, ${total} unread`);

    await bell.click();
    await expect(page.getByText("e2e-suite first note")).toBeVisible();
    await page.getByRole("button", { name: 'Mark "e2e-suite first note" as read' }).click();
    await expect(bell).toHaveAccessibleName(total - 1 ? `Notifications, ${total - 1} unread` : "Notifications");

    await page.getByRole("button", { name: "Mark all read" }).click();
    await expect(bell).toHaveAccessibleName("Notifications");
    await expect(page.getByRole("button", { name: "Mark all read" })).toHaveCount(0);
    expect(await unread()).toBe(0);

    // Still read after a reload
    await page.reload();
    await expect(page.getByRole("button", { name: /^Notifications/ }).filter({ visible: true })).toHaveAccessibleName("Notifications");
    expect(consoleErrors.errors).toEqual([]);
  });
});
