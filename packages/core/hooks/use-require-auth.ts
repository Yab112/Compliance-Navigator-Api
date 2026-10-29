"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { useUserStore } from "../store/user-store";

/**
 * "loading" until the session resolves; sends anonymous visitors to sign in and back.
 * Someone who signs out while on the page (here or in another tab) goes to `signedOutTo` instead.
 */
export function useRequireAuth(signedOutTo = "/"): "loading" | "ready" {
  const router = useRouter();
  const pathname = usePathname();
  const status = useUserStore((s) => s.status);
  const wasSignedIn = useRef(false);

  useEffect(() => {
    if (status === "authenticated") wasSignedIn.current = true;
    if (status !== "anonymous") return;
    if (wasSignedIn.current) {
      router.replace(signedOutTo);
      return;
    }
    const query = typeof window === "undefined" ? "" : window.location.search;
    router.replace(`/login?returnTo=${encodeURIComponent(pathname + query)}`);
  }, [status, pathname, router, signedOutTo]);

  return status === "authenticated" ? "ready" : "loading";
}
