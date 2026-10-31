import fs from "node:fs";
import path from "node:path";
import { expect } from "@playwright/test";
import { API_LOG, MAILPIT_URL, REPO } from "./env";

export type MailKind = "verify" | "reset";

const LINK = { verify: /https?:\/\/\S+\/verify-email\?token=[\w-]+/g, reset: /https?:\/\/\S+\/reset-password\?token=[\w-]+/g };

/** The newest link of this kind in the email text Mailpit holds for this address. */
async function fromMailpit(address: string, kind: MailKind): Promise<string | null> {
  const query = encodeURIComponent(`to:"${address}"`);
  const list = await fetch(`${MAILPIT_URL}/api/v1/search?query=${query}`).then((r) => r.json());
  for (const m of list.messages ?? []) {
    const full = await fetch(`${MAILPIT_URL}/api/v1/message/${m.ID}`).then((r) => r.json());
    const found = String(full.Text ?? "").match(LINK[kind]);
    if (found) return found[found.length - 1];
  }
  return null;
}

/** Without SMTP the dev API writes each email to its log: "Email to <address>: <subject>" then the body. */
function fromLog(address: string, kind: MailKind): string | null {
  const file = API_LOG ?? path.join(REPO, "api/logs/api.log");
  if (!fs.existsSync(file)) return null;
  // Only the tail: the log can be large and the email was just written
  const size = fs.statSync(file).size;
  const fd = fs.openSync(file, "r");
  const length = Math.min(size, 2_000_000);
  const buf = Buffer.alloc(length);
  fs.readSync(fd, buf, 0, length, size - length);
  fs.closeSync(fd);
  const text = buf.toString("utf8");
  const marker = `Email to ${address}:`;
  let at = text.lastIndexOf(marker);
  while (at >= 0) {
    // The body runs until the next log line, which starts with a level name or uvicorn's "INFO:"
    const rest = text.slice(at + marker.length);
    const end = rest.search(/\n(?:INFO|WARNING|ERROR|DEBUG|CRITICAL)[: ]/);
    const body = end >= 0 ? rest.slice(0, end) : rest;
    const found = body.match(LINK[kind]);
    if (found) return found[0];
    at = text.lastIndexOf(marker, at - 1);
  }
  return null;
}

/** Waits for the email and returns the token from its link. */
export async function tokenFromEmail(address: string, kind: MailKind, timeoutMs = 20_000): Promise<string> {
  let link: string | null = null;
  await expect
    .poll(
      async () => {
        link = MAILPIT_URL ? await fromMailpit(address, kind) : fromLog(address, kind);
        return link;
      },
      { message: `${kind} email for ${address}`, timeout: timeoutMs, intervals: [250, 500, 1000] },
    )
    .not.toBeNull();
  return new URL(link!).searchParams.get("token")!;
}
