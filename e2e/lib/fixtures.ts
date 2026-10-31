import { test as base, expect, type Page } from "@playwright/test";

/**
 * Browser console errors that are part of normal use, not bugs:
 * - the session check on first load answers 401 for a signed-out visitor (Chrome logs every failed request);
 * - React and Next dev-only notices.
 */
const EXPECTED = [
  /Failed to load resource: the server responded with a status of 401/,
  /Download the React DevTools/,
  /\[Fast Refresh\]/,
  /\[HMR\]/,
];

export type ConsoleWatch = { errors: string[]; allow: (pattern: RegExp) => void };

export const test = base.extend<{ consoleErrors: ConsoleWatch }>({
  consoleErrors: async ({ page }, use) => {
    const errors: string[] = [];
    const allowed = [...EXPECTED];
    page.on("console", (m) => {
      if (m.type() !== "error") return;
      const text = `${m.text()} (${m.location().url})`;
      if (!allowed.some((re) => re.test(text))) errors.push(text.slice(0, 400));
    });
    page.on("pageerror", (e) => errors.push(`pageerror: ${e.message.slice(0, 400)}`));
    await use({ errors, allow: (re) => allowed.push(re) });
  },
});

export { expect };

/** Fails when the page is wider than the screen (a sideways scroll on phones). */
export async function expectNoHorizontalScroll(page: Page) {
  const { scroll, client } = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(scroll, `page is ${scroll}px wide on a ${client}px screen`).toBeLessThanOrEqual(client + 1);
}
