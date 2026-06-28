"use client";

import { useRouter } from "next/navigation";
import useMutationFunc from "@/hooks/use-mutation";
import { MTD } from "@/lib/constants/methods";
import { apiPaths } from "@/lib/constants/api-paths";
import { setAccessToken } from "@/lib/auth-token";
import { isMockCredentials, MOCK_TOKEN } from "@/lib/mock-auth";
import { getSupabase, isSupabaseConfigured } from "@/lib/supabase/client";
import type { APIResponse } from "@/types/global";
import type { User } from "@/types/user-types";

export interface RegisterInput {
  email: string;
  password: string;
  fullname: string;
}

export const useRegister = () => {
  const router = useRouter();

  const { mutateAsync, isPending } = useMutationFunc<
    APIResponse<{ user: User }>,
    RegisterInput
  >({
    onSuccess: () => {
      router.push("/login");
    },
  });

  const register = async (input: RegisterInput) => {
    if (isMockCredentials(input.email, input.password)) {
      setAccessToken(MOCK_TOKEN);
      router.push("/login");
      return;
    }

    if (isSupabaseConfigured()) {
      const supabase = getSupabase()!;
      const { error } = await supabase.auth.signUp({
        email: input.email,
        password: input.password,
        options: { data: { fullname: input.fullname } },
      });
      if (error) {
        throw new Error(error.message);
      }
      router.push("/login");
      return;
    }

    return mutateAsync({
      url: apiPaths.users.register,
      method: MTD.POST,
      body: input,
      headers: { "Content-Type": "application/json" },
    });
  };

  return {
    register,
    isRegistering: isPending,
  };
};
