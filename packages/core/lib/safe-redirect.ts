// Parsed against a fixed placeholder origin so it gives the same answer in the browser and while the
// page renders on the server: a value is safe only if it stays on that origin.
const BASE = "https://return-to.invalid";

// Control characters and spaces (browsers strip tabs and newlines from URLs: "/\t/evil.com" is "//evil.com")
const CONTROL = /[\u0000-\u001F\u007F\s]/;
// Encoded slashes, backslashes and control characters, which some servers and browsers decode again
const ENCODED = /%(?:2f|5c|[01][0-9a-f]|7f)/i;

/** Only follow same-site paths from ?returnTo=, never "//evil.com", "/\t/evil.com" or absolute URLs. */
export function safeReturnTo(value: string | null | undefined, fallback = "/roadmap"): string {
  if (!value || value[0] !== "/" || value[1] === "/" || value.includes("\\") || CONTROL.test(value) || ENCODED.test(value)) {
    return fallback;
  }
  let url: URL;
  try {
    url = new URL(value, BASE);
  } catch {
    return fallback;
  }
  if (url.origin !== BASE || !url.pathname.startsWith("/") || url.pathname.startsWith("//")) return fallback;
  return url.pathname + url.search + url.hash;
}
