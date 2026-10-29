"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useUserStore } from "@/store/user-store";

/** Sign-in pages send visitors who already have a session straight on. Empty `to` disables it. */
export function useRedirectIfSignedIn(to: string) {
  const router = useRouter();
  const status = useUserStore((s) => s.status);
  useEffect(() => {
    if (to && status === "authenticated") router.replace(to);
  }, [status, to, router]);
}
