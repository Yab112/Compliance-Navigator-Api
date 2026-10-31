import fs from "node:fs";
import path from "node:path";

/** Where the stack under test lives. Defaults match the local dev servers. */
const here = path.dirname(new URL(import.meta.url).pathname);
export const REPO = path.resolve(here, "../..");

const trim = (u: string) => u.replace(/\/+$/, "");

export const WEB_URL = trim(process.env.E2E_WEB_URL ?? "http://localhost:3000");
export const ADMIN_URL = trim(process.env.E2E_ADMIN_URL ?? "http://localhost:3001");
/** The API root, without /api/v1 */
export const API_ROOT = trim((process.env.E2E_API_URL ?? "http://localhost:8080").replace(/\/api\/v1\/?$/, ""));
export const API = `${API_ROOT}/api/v1`;

/** Links in emails come from Mailpit when set, otherwise from the API log (dev without SMTP). */
export const MAILPIT_URL = process.env.E2E_MAILPIT_URL ? trim(process.env.E2E_MAILPIT_URL) : null;
export const API_LOG = process.env.E2E_API_LOG ?? null;

/**
 * How to run the API's Python, as a command line. Locally the api venv; against containers for example
 * "docker compose -f api/docker-compose.yml exec -T web python".
 */
export const PYTHON = process.env.E2E_PYTHON ?? path.join(REPO, "api/.venv/bin/python");
export const PYTHON_CWD = process.env.E2E_PYTHON_CWD ?? path.join(REPO, "api");

/** System Chrome instead of a downloaded Playwright browser. */
export const CHROME = process.env.E2E_CHROME ?? (fs.existsSync("/usr/bin/google-chrome") ? "/usr/bin/google-chrome" : undefined);

/** Every account and record the suite makes starts with this, so cleanup can find leftovers. */
export const PREFIX = "e2e-suite-";

export function uniqueEmail(kind: string): string {
  const rand = Math.random().toString(36).slice(2, 8);
  return `${PREFIX}${kind}-${Date.now().toString(36)}${rand}@example.com`;
}

/** A password that passes the rules (8+ characters, a letter and a number). Kept in memory only. */
export function randomPassword(): string {
  return `E2e${Math.random().toString(36).slice(2, 10)}${Math.floor(Math.random() * 90 + 10)}x`;
}
