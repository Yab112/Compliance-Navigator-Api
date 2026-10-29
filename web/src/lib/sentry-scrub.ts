/**
 * What we send to Sentry (error monitoring, see the Privacy Policy) never includes who the person is or
 * anything that could open their account: no emails, phone numbers, tokens, cookies or IP addresses.
 * Used by the browser, server and edge Sentry set-ups.
 */
import type { Breadcrumb, Event } from "@sentry/nextjs";

const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi;
// Ethiopian mobile numbers: +2519..., 2519..., 09..., 07...
const PHONE = /(?:\+?251|\b0)[79]\d{8}\b/g;
const JWT = /\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]{5,}/g;
const BEARER = /\bBearer\s+[\w.~+/-]+=*/gi;
// One-time codes travel in links: reset and verification tokens, Fayda state and code, payment references
const SECRET_PARAMS = /([?&](?:token|code|state|tx_ref|trx_ref|payment|session_state)=)[^&#\s]*/gi;

export function scrubText(value: string): string {
  return value
    .replace(SECRET_PARAMS, "$1[hidden]")
    .replace(JWT, "[token]")
    .replace(BEARER, "Bearer [token]")
    .replace(EMAIL, "[email]")
    .replace(PHONE, "[phone]");
}

function scrubDeep<T>(value: T, depth = 0): T {
  if (typeof value === "string") return scrubText(value) as T;
  if (depth > 6 || value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map((v) => scrubDeep(v, depth + 1)) as T;
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
    out[k] = /pass(word)?|token|secret|authorization|cookie|account_number/i.test(k) ? "[hidden]" : scrubDeep(v, depth + 1);
  }
  return out as T;
}

function scrubEvent<E extends Event>(event: E): E {
  if (event.request) {
    delete event.request.cookies;
    delete event.request.data;
    if (event.request.headers) {
      event.request.headers = Object.fromEntries(
        Object.entries(event.request.headers).filter(([k]) => !/^(authorization|cookie)$/i.test(k)),
      );
    }
    if (typeof event.request.query_string === "string") event.request.query_string = scrubText(`?${event.request.query_string}`).slice(1);
    else delete event.request.query_string;
  }
  // Keep the account id (to group a person's errors), never who they are or where they are
  if (event.user) event.user = event.user.id ? { id: event.user.id } : {};
  return scrubDeep(event);
}

export const beforeSend = <E extends Event>(event: E): E => scrubEvent(event);
export const beforeSendTransaction = <E extends Event>(event: E): E => scrubEvent(event);
export const beforeBreadcrumb = (crumb: Breadcrumb) => scrubDeep(crumb);

/** Share of page loads traced for performance; errors are always reported. Defaults to 10%. */
export function tracesSampleRate(raw: string | undefined): number {
  const n = Number(raw);
  return raw && Number.isFinite(n) && n >= 0 && n <= 1 ? n : 0.1;
}
