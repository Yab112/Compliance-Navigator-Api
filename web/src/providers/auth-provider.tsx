"use client";

import { useEffect } from "react";
import { useGetCurrentUser } from "@/api/auth";
import { useUserStore } from "@/store";
import { getAccessToken, setAccessToken, clearAccessToken } from "@/lib/auth-token";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase/client";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setUser } = useUserStore();
  const hasToken = typeof window !== "undefined" && !!getAccessToken();
  const { currentUser, isError } = useGetCurrentUser(hasToken);

  useEffect(() => {
    if (!isSupabaseConfigured()) return;

    const supabase = getSupabase();
    if (!supabase) return;

    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.access_token) {
        setAccessToken(session.access_token);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.access_token) {
        setAccessToken(session.access_token);
      } else if (!getAccessToken()) {
        setUser(null);
      }
    });

    return () => subscription.unsubscribe();
  }, [setUser]);

  useEffect(() => {
    if (currentUser) {
      setUser(currentUser);
      return;
    }
    if (isError && hasToken) {
      clearAccessToken();
      setUser(null);
    }
  }, [currentUser, isError, hasToken, setUser]);

  return <>{children}</>;
}
