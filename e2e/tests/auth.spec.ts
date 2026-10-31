import { API, WEB_URL, randomPassword, uniqueEmail } from "../lib/env";
import { apiLogin, createVerifiedClient, expectSignedIn, openAccountMenu, signInWeb, signOutWeb } from "../lib/accounts";
import { cleanup, helper } from "../lib/backend";
import { expect, test } from "../lib/fixtures";
import { tokenFromEmail } from "../lib/mail";

test.describe("sign-up and sign-in", () => {
  const emails: string[] = [];
  test.afterAll(async () => {
    await cleanup(emails);
  });

  test("register, confirm the email, sign in, reload keeps the session, sign out", async ({ page, consoleErrors }) => {
    const email = uniqueEmail("auth");
    emails.push(email);
    const password = randomPassword();

    await page.goto("/register");
    await page.getByLabel(/^Full name/).fill("E2E Suite Auth");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel(/^Password/).fill(password);
    for (const box of await page.getByRole("checkbox").all()) await box.check();
    await page.getByRole("button", { name: "Create account" }).click();
    // A new account can be used before it is confirmed, so sign-up signs straight in
    await page.waitForURL((url) => !url.pathname.startsWith("/register"));
    await expectSignedIn(page);

    const token = await tokenFromEmail(email, "verify");
    await page.goto(`/verify-email?token=${encodeURIComponent(token)}`);
    await expect(page.getByText("your email is confirmed")).toBeVisible();
    // The link works once; the second try is refused (Chrome logs the 400)
    consoleErrors.allow(/status of 400 .*\/auth\/verify-email/);
    await page.goto(`/verify-email?token=${encodeURIComponent(token)}`);
    await expect(page.getByRole("alert").filter({ hasText: /invalid or has expired/ })).toBeVisible();

    await signOutWeb(page);
    await signInWeb(page, email, password, "/account");
    await expect(page).toHaveURL(/\/account$/);
    await page.reload();
    await expect(page).toHaveURL(/\/account$/);
    await expectSignedIn(page);

    await signOutWeb(page);
    await page.goto("/account");
    await expect(page).toHaveURL(/\/login\?returnTo=%2Faccount/);
    expect(consoleErrors.errors).toEqual([]);
  });

  test("forgot password, reset it, sign in with the new password", async ({ page, request, consoleErrors }) => {
    const client = await createVerifiedClient(request, "reset");
    emails.push(client.email);
    // The forgot-password form allows 10 a network an hour; repeated local runs would hit it
    await helper("clear-local-limits").catch(() => undefined);

    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(client.email);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByText(/we sent a link to reset the password/)).toBeVisible();

    const token = await tokenFromEmail(client.email, "reset");
    const fresh = randomPassword();
    await page.goto(`/reset-password?token=${encodeURIComponent(token)}`);
    await page.getByLabel("New password", { exact: true }).fill(fresh);
    await page.getByLabel("Repeat new password").fill(fresh);
    await page.getByRole("button", { name: "Save new password" }).click();
    await expect(page).toHaveURL(/\/login\?reset=1/);
    await expect(page.getByText("Your password was changed")).toBeVisible();

    await signInWeb(page, client.email, fresh, "/account");
    // The old password is gone
    const old = await request.post(`${API}/auth/login`, { data: { email: client.email, password: client.password } });
    expect(old.status()).toBe(401);
    await apiLogin(request, client.email, fresh);
    expect(consoleErrors.errors).toEqual([]);
  });

  test("a wrong password says so and stays on the sign-in page", async ({ page, request }) => {
    const client = await createVerifiedClient(request, "wrongpw");
    emails.push(client.email);
    await page.goto(`${WEB_URL}/login`);
    await page.getByLabel("Email").fill(client.email);
    await page.getByLabel("Password", { exact: true }).fill(`${client.password}-wrong`);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert").filter({ hasText: /\S/ })).toHaveText("Incorrect email or password");
    await expect(page).toHaveURL(/\/login/);
    // Still signed out
    await openAccountMenu(page);
    await expect(page.getByRole("link", { name: /Sign in/ }).first()).toBeAttached();
  });
});
