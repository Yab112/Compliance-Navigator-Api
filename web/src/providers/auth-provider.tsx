"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { endSession, listenForAuthChanges, refreshIfStale, refreshSession } from "@/lib/auth-session";

const LEGACY_TOKEN_KEY = "compliance_navigator_access_token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient();

  useEffect(() => {
    // Tokens used to be kept in localStorage; never leave one behind
    try {
      localStorage.removeItem(LEGACY_TOKEN_KEY);
    } catch {}

    void refreshSession();

    const stopListening = listenForAuthChanges((message) => {
      if (message.type === "signed-out") {
        endSession();
        queryClient.clear();
      } else {
        void refreshSession().then(() => queryClient.invalidateQueries());
      }
    });
    // Coming back to a tab after a long sleep: make sure the session is still alive
    const onVisible = () => {
      if (document.visibilityState === "visible") refreshIfStale();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stopListening();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [queryClient]);

  return <>{children}</>;
}
