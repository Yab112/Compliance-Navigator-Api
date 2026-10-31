import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { ADMIN_URL, API, WEB_URL, randomPassword, uniqueEmail } from "./env";
import { tokenFromEmail } from "./mail";

export type Client = { email: string; password: string; fullname: string; id: string; token: string };
export type Staff = { email: string; password: string; fullname: string };

/** The document versions the sign-up form ticks. */
export async function legalAcceptance(request: APIRequestContext): Promise<Record<string, string>> {
  const res = await request.get(`${API}/legal/documents`);
  expect(res.ok()).toBeTruthy();
  const { documents, clientRequired } = (await res.json()).payload;
  return Object.fromEntries(
    documents.filter((d: { key: string }) => clientRequired.includes(d.key)).map((d: { key: string; version: string }) => [d.key, d.version]),
  );
}

/** A public account made through the API and confirmed with the link from its email. */
export async function createVerifiedClient(request: APIRequestContext, kind = "client"): Promise<Client> {
  const email = uniqueEmail(kind);
  const password = randomPassword();
  const fullname = `E2E Suite ${kind}`;
  const res = await request.post(`${API}/auth/register`, {
    data: { email, password, fullname, phone: "0911000000", accept: await legalAcceptance(request) },
  });
  expect(res.status(), await res.text()).toBe(201);
  const token = await tokenFromEmail(email, "verify");
  const verified = await request.post(`${API}/auth/verify-email`, { data: { token } });
  expect(verified.status(), await verified.text()).toBe(200);
  return { email, password, fullname, ...(await apiLogin(request, email, password)) };
}

/** Signs in through the API; returns the account id and an access token for API checks. */
export async function apiLogin(request: APIRequestContext, email: string, password: string): Promise<{ id: string; token: string }> {
  const res = await request.post(`${API}/auth/login`, { data: { email, password } });
  expect(res.status(), await res.text()).toBe(200);
  const { user, accessToken } = (await res.json()).payload;
  return { id: user.id, token: accessToken };
}

export const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });

export const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1366) < 768;

/** The header's account controls: in the top bar on desktop, inside the Menu on phones. */
export async function openAccountMenu(page: Page) {
  if (!isPhone(page)) return;
  // The toggle reads "Menu" when closed and "Close" when open; aria-controls finds it either way
  const menu = page.locator('button[aria-controls="mobile-menu"]');
  if ((await menu.getAttribute("aria-expanded")) !== "true") await menu.click();
}

/** Signs in on the public site with the form and waits until the header shows the account. */
export async function signInWeb(page: Page, email: string, password: string, returnTo = "/account") {
  await page.goto(`${WEB_URL}/login?returnTo=${encodeURIComponent(returnTo)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await expectSignedIn(page);
}

export async function expectSignedIn(page: Page) {
  await openAccountMenu(page);
  await expect(page.getByRole("button", { name: "Sign out" }).first()).toBeVisible();
}

export async function signOutWeb(page: Page) {
  await openAccountMenu(page);
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await openAccountMenu(page);
  await expect(page.getByRole("link", { name: /Sign in/ }).first()).toBeVisible();
}

export async function signInAdmin(page: Page, staff: Staff) {
  await page.goto(`${ADMIN_URL}/login`);
  await page.getByLabel("Email").fill(staff.email);
  await page.getByLabel("Password", { exact: true }).fill(staff.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"));
  await expect(page.getByRole("navigation", { name: "Staff sections" })).toBeVisible();
}

/** A staff access token straight from the API, for setting up and undoing admin changes. */
export async function staffToken(request: APIRequestContext, staff: Staff): Promise<string> {
  const res = await request.post(`${API}/staff/auth/login`, { data: { email: staff.email, password: staff.password } });
  expect(res.status(), await res.text()).toBe(200);
  return (await res.json()).payload.accessToken;
}
