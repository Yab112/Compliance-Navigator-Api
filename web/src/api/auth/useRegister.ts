"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiPaths } from "@/lib/constants/api-paths";
import { applySession, broadcastAuth, postAuth } from "@/lib/auth-session";
import type { SessionPayload } from "@/types/user-types";

export interface RegisterInput {
  email: string;
  password: string;
  fullname: string;
  phone?: string;
}

/** Creates the account and signs straight in. */
export const useRegister = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isRegistering, setPending] = useState(false);

  const register = async (input: RegisterInput, returnTo = "/roadmap") => {
    setPending(true);
    try {
      const session = await postAuth<SessionPayload>(apiPaths.auth.register, {
        ...input,
        phone: input.phone?.trim() || undefined,
      });
      applySession(session);
      broadcastAuth({ type: "signed-in" });
      await queryClient.invalidateQueries();
      router.push(returnTo);
      return session;
    } finally {
      setPending(false);
    }
  };

  return { register, isRegistering };
};
