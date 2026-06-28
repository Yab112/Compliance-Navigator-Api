"use client";

import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { clearAccessToken, getAccessToken } from "@/lib/auth-token";
import { isMockToken } from "@/lib/mock-auth";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase/client";
import { useUserStore } from "@/store";

export const useLogout = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { setUser } = useUserStore();

  const logout = async () => {
    if (!isMockToken(getAccessToken()) && isSupabaseConfigured()) {
      const supabase = getSupabase();
      if (supabase) {
        await supabase.auth.signOut();
      }
    }
    clearAccessToken();
    setUser(null);
    queryClient.clear();
    router.push("/");
  };

  return {
    logout,
    isLoggingOut: false,
  };
};
