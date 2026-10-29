"use client";

import { useUserStore } from "@/store/user-store";

/**
 * Whether the visitor is signed in. `null` until the session check on page load
 * finishes, so callers can avoid flashing a sign-in prompt.
 */
export function useHasToken(): boolean | null {
  const status = useUserStore((s) => s.status);
  return status === "loading" ? null : status === "authenticated";
}
