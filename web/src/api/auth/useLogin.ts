"use client";

import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import useMutationFunc from "@/hooks/use-mutation";
import { MTD } from "@/lib/constants/methods";
import { apiPaths } from "@/lib/constants/api-paths";
import { setAccessToken } from "@/lib/auth-token";
import {
  isMockCredentials,
  MOCK_TOKEN,
  MOCK_USER,
} from "@/lib/mock-auth";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase/client";
import { useUserStore } from "@/store";
import type { TokenResponse } from "@/lib/api";

export interface LoginCredentials {
  email: string;
  password: string;
}

export const useLogin = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { setUser } = useUserStore();

  const { mutateAsync, isPending } = useMutationFunc<
    TokenResponse,
    LoginCredentials
  >({
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });

  const login = async (
    credentials: LoginCredentials,
    redirectTo = "/roadmap",
  ) => {
    if (isMockCredentials(credentials.email, credentials.password)) {
      setAccessToken(MOCK_TOKEN);
      setUser(MOCK_USER);
      router.push(redirectTo);
      return { access_token: MOCK_TOKEN, type: "Bearer" };
    }

    if (isSupabaseConfigured()) {
      const supabase = getSupabase()!;
      const { data, error } = await supabase.auth.signInWithPassword({
        email: credentials.email,
        password: credentials.password,
      });
      if (error) {
        throw new Error(error.message);
      }
      const token = data.session?.access_token;
      if (!token) {
        throw new Error("No session returned");
      }
      setAccessToken(token);
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      router.push(redirectTo);
      return { access_token: token, type: "Bearer" };
    }

    const data = await mutateAsync({
      url: apiPaths.users.login,
      method: MTD.POST,
      body: credentials,
      headers: { "Content-Type": "application/json" },
    });

    setAccessToken(data.access_token);
    queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    router.push(redirectTo);
    return data;
  };

  return {
    login,
    isLoggingIn: isPending,
  };
};
