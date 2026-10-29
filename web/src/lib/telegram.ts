/** Telegram usernames as people type them ("@meron", "t.me/meron") reduced to "meron"; mirrors the server's rule. */
export function cleanTelegram(value: string): string {
  return value.trim().replace(/^(https?:\/\/)?(www\.)?(t\.me|telegram\.me)\//i, "").replace(/^@/, "").replace(/\/$/, "");
}

export const TELEGRAM_RE = /^[A-Za-z][A-Za-z0-9_]{4,31}$/;
export const TELEGRAM_HINT = "Your Telegram username, e.g. @dawit_g. 5 to 32 letters, digits or _";
