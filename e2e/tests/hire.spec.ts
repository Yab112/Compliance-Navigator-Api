import { API } from "../lib/env";
import { bearer, createVerifiedClient, signInWeb } from "../lib/accounts";
import { cleanup, providerAction, readyProvider, type SampleProvider } from "../lib/backend";
import { expect, test } from "../lib/fixtures";

const PRICE = 900;
const DELIVERED = "e2e-suite: passport renewed and collected from the Bole office.";

test.describe("hiring a provider", () => {
  const emails: string[] = [];
  let provider: SampleProvider;

  test.beforeAll(async () => {
    provider = await readyProvider();
  });
  test.afterAll(async () => {
    await cleanup(emails);
  });

  test("client hires, provider delivers, client is asked to pay and checkout starts", async ({ page, request }) => {
    const client = await createVerifiedClient(request, "hire");
    emails.push(client.email);
    const title = `e2e-suite: renew my passport ${Date.now()}`;

    await signInWeb(page, client.email, client.password, `/providers/${provider.slug}`);
    await expect(page.getByRole("heading", { level: 1, name: provider.display_name })).toBeVisible();
    await page.getByLabel("What do you need?").fill(title);
    // Name and phone start from the account
    await expect(page.getByLabel("Your name")).toHaveValue(client.fullname);
    await expect(page.getByLabel("Phone to call you on")).toHaveValue("0911000000");
    // Telegram is required: an empty one is refused, then a typed one goes through
    await page.getByLabel("Telegram username").fill("");
    const send = page.getByRole("button", { name: `Send request to ${provider.display_name}` });
    await send.click();
    await expect(page.getByText("Add your Telegram username so the provider can message you")).toBeVisible();
    await page.getByLabel("Telegram username").fill("@e2e_suite_client");
    await send.click();
    await expect(page.getByText(/Request sent/)).toBeVisible();

    const hires = await request.get(`${API}/hires`, { headers: bearer(client.token) });
    const hire = (await hires.json()).payload.items.find((h: { title: string }) => h.title === title);
    expect(hire, "the new hire is in the client's list").toBeTruthy();
    expect(hire.status).toBe("requested");

    // The provider side: sample accounts can't sign in, so these run through the service code
    await providerAction(hire.id, "accept", { price: PRICE });
    await providerAction(hire.id, "start");
    expect((await providerAction(hire.id, "complete", { note: DELIVERED })).status).toBe("completed");

    await page.goto("/account/requests");
    const row = page.getByRole("listitem").filter({ hasText: title });
    const pay = row.getByRole("button", { name: /^Pay [\d,.]+ ETB/ });
    await expect(pay).toBeVisible();

    const mode = (await (await request.get(`${API}/payments/config`)).json()).payload.mode;
    // Never leave for the real Chapa page: answer it locally once the checkout address is known
    await page.route(/^https:\/\/([a-z-]+\.)*chapa\.co\//, (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<title>Chapa test checkout</title><p>Chapa</p>" }),
    );
    // The browser leaves for the checkout as soon as the answer arrives, so read it on the way through
    let answer = null as { status: number; body: string } | null;
    await page.route(/\/hires\/[^/]+\/pay$/, async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      let response = await route.fetch();
      // Chapa's test API throttles back-to-back checkouts ("Please try again in 22 seconds"); wait as told
      for (let tries = 0; tries < 2 && response.status() === 502; tries++) {
        const wait = /try again in (\d+) seconds/.exec(await response.text());
        if (!wait) break;
        await new Promise((r) => setTimeout(r, (Number(wait[1]) + 1) * 1000));
        response = await route.fetch();
      }
      answer = { status: response.status(), body: await response.text() };
      await route.fulfill({ response });
    });
    await pay.click();
    await expect.poll(() => answer, { message: "the pay request answered", timeout: 75_000 }).not.toBeNull();
    const { status, body } = answer!;
    expect(status, body).toBe(200);
    const checkout = JSON.parse(body).payload;

    if (mode === "simulated") {
      // Test mode: our own checkout page, then a successful payment closes the job
      await expect(page).toHaveURL(/\/pay\/test\//);
      await page.getByRole("button", { name: /^Pay .*\(test\)$/ }).click();
      await page.waitForURL(/\/account\/requests/);
      await expect(pay).toHaveCount(0);
      await expect
        .poll(async () => {
          const items = (await (await request.get(`${API}/hires`, { headers: bearer(client.token) })).json()).payload.items;
          return items.find((h: { id: string }) => h.id === hire.id)?.payment_status;
        })
        .toBe("paid");
    } else {
      expect(checkout.checkout_url).toMatch(/^https:\/\/([a-z-]+\.)*chapa\.co\//);
      await expect(page).toHaveURL(/chapa\.co/);
      // Back on the site the hire waits for the payment to finish
      await page.goto("/account/requests");
      await expect(row.getByRole("button", { name: "Continue payment" })).toBeVisible();
    }
  });
});
