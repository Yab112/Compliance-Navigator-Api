import axios from "axios";
import { env } from "../config/env";
import { useUserStore } from "../store/user-store";
import type { SessionPayload } from "../types/user-types";

/**
 * Session plumbing shared by the API client and the auth hooks.
 * The refresh token is an httpOnly cookie scoped to /api/v1/auth; the access token
 * lives only in memory, so a page load starts with one silent refresh.
 */

// A bare client: the main `api` instance retries 401s through refreshSession, which must not recurse
const authClient = axios.create({ baseURL: env.NEXT_PUBLIC_API_BASE_URL, withCredentials: true });

const CHANNEL = "cn-auth";
type AuthMessage = { type: "signed-in" } | { type: "signed-out" };

let refreshTimer: ReturnType<typeof setTimeout> | undefined;
let expiresAt = 0;
let inFlight: Promise<boolean> | null = null;

function channel(): BroadcastChannel | null {
  return typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(CHANNEL);
}

/** Tell other tabs, which share the cookie, to pick up the new state. */
export function broadcastAuth(message: AuthMessage): void {
  const ch = channel();
  ch?.postMessage(message);
  ch?.close();
}

export function listenForAuthChanges(onMessage: (message: AuthMessage) => void): () => void {
  const ch = channel();
  if (!ch) return () => {};
  ch.onmessage = (e) => onMessage(e.data as AuthMessage);
  return () => ch.close();
}

export function applySession(payload: SessionPayload): void {
  useUserStore.getState().setSession(payload.user, payload.accessToken);
  // Refresh a minute before the access token expires so requests never hit a 401
  clearTimeout(refreshTimer);
  expiresAt = Date.now() + payload.expiresIn * 1000;
  const delay = Math.max(15, payload.expiresIn - 60) * 1000;
  refreshTimer = setTimeout(() => void refreshSession(), delay);
}

/** Timers stall while a laptop sleeps, renew on wake if the token is (nearly) expired. */
export function refreshIfStale(): void {
  if (useUserStore.getState().status === "authenticated" && Date.now() > expiresAt - 60_000) {
    void refreshSession();
  }
}

export function endSession(): void {
  clearTimeout(refreshTimer);
  useUserStore.getState().clearSession();
  // Per-session reminders (e.g. "add your bank account") show again after the next sign-in
  try {
    for (const key of Object.keys(sessionStorage)) if (key.startsWith("cn-payout-prompt:")) sessionStorage.removeItem(key);
  } catch {}
}

/**
 * Exchange the refresh cookie for a new access token. Concurrent callers share one
 * request. Resolves false when there is no valid session (the user is signed out).
 */
export function refreshSession(): Promise<boolean> {
  inFlight ??= authClient
    .post<{ payload: SessionPayload }>("auth/refresh")
    .then((res) => {
      applySession(res.data.payload);
      return true;
    })
    .catch((error) => {
      // Keep the current state when the API is merely unreachable
      if (axios.isAxiosError(error) && error.response) {
        endSession();
        return false;
      }
      if (useUserStore.getState().status === "loading") endSession();
      return useUserStore.getState().status === "authenticated";
    })
    .finally(() => {
      inFlight = null;
    });
  return inFlight;
}

export async function postAuth<T>(path: string, body?: unknown): Promise<T> {
  const token = useUserStore.getState().accessToken;
  const res = await authClient.post<{ payload: T }>(path, body, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  return res.data.payload;
}
