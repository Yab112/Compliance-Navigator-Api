"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { apiPaths } from "../../lib/constants/api-paths";
import { applySession, broadcastAuth, postAuth } from "../../lib/auth-session";
import type { SessionPayload } from "../../types/user-types";

export interface RegisterInput {
  email: string;
  password: string;
  fullname: string;
  phone?: string;
  /** Legal documents ticked on the form: key -> version. The server refuses sign-up without them. */
  accept: Record<string, string>;
}

/** "signed-in": a new account, now signed in (unconfirmed until they open the emailed link).
 *  "check-email": the server answered without a new account to sign in to; the email explains. */
export type RegisterResult = "signed-in" | "check-email";

/**
 * Creates the account, then signs in with the same password. The server answers sign-up the same way
 * whether or not the email is already taken (so nobody can test who has an account); if signing in
 * doesn't work, the person is told to check their email, where the next step is waiting.
 */
export const useRegister = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isRegistering, setPending] = useState(false);

  const register = async (input: RegisterInput, returnTo = "/roadmap"): Promise<RegisterResult> => {
    setPending(true);
    try {
      await postAuth<{ message: string }>(apiPaths.auth.register, {
        ...input,
        phone: input.phone?.trim() || undefined,
      });
      let session: SessionPayload;
      try {
        session = await postAuth<SessionPayload>(apiPaths.auth.login, { email: input.email, password: input.password });
      } catch (err) {
        if (err instanceof AxiosError && (err.response?.status === 401 || err.response?.status === 403)) return "check-email";
        throw err;
      }
      applySession(session);
      broadcastAuth({ type: "signed-in" });
      await queryClient.invalidateQueries();
      router.push(returnTo);
      return "signed-in";
    } finally {
      setPending(false);
    }
  };

  return { register, isRegistering };
};
