/** Only follow same-site paths from ?returnTo=, never "//evil.com" or absolute URLs. */
export function safeReturnTo(value: string | null | undefined, fallback = "/roadmap"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) return fallback;
  return value;
}
