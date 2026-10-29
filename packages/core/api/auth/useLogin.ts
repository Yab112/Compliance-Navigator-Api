"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiPaths } from "../../lib/constants/api-paths";
import { applySession, broadcastAuth, postAuth } from "../../lib/auth-session";
import type { SessionPayload } from "../../types/user-types";

export interface LoginCredentials {
  email: string;
  password: string;
}

export const useLogin = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isLoggingIn, setPending] = useState(false);

  const login = async (credentials: LoginCredentials, redirectTo = "/roadmap") => {
    setPending(true);
    try {
      const session = await postAuth<SessionPayload>(apiPaths.auth.login, credentials);
      applySession(session);
      broadcastAuth({ type: "signed-in" });
      await queryClient.invalidateQueries();
      router.push(redirectTo);
      return session;
    } finally {
      setPending(false);
    }
  };

  return { login, isLoggingIn };
};
