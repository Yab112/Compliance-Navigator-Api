"use client";

import { useFetchData } from "../../hooks/use-query";
import useMutationFunc from "../../hooks/use-mutation";
import { apiPaths } from "../../lib/constants/api-paths";
import { withQuery } from "../catalog/with-query";
import { useUserStore } from "../../store/user-store";
import type { APIResponse } from "../../types/global";
import type { AuthEvent, AuthSession, User } from "../../types/user-types";

export const SECURITY_PAGE_SIZE = 10;

/** One page of the devices this account is signed in on, most recently used first. */
export const useMySessions = (page = 0) =>
  useFetchData<APIResponse<{ sessions: AuthSession[]; total: number }>>(
    ["auth", "sessions", page],
    withQuery(apiPaths.auth.sessions, { limit: SECURITY_PAGE_SIZE, offset: page * SECURITY_PAGE_SIZE }),
    { staleTime: 0, refetchOnMount: true },
  );

/** One page of sign-ins, password changes and other security events, newest first. */
export const useMyActivity = (page = 0) =>
  useFetchData<APIResponse<{ events: AuthEvent[]; total: number }>>(
    ["auth", "activity", page],
    withQuery(apiPaths.auth.activity, { limit: SECURITY_PAGE_SIZE, offset: page * SECURITY_PAGE_SIZE }),
    { staleTime: 0, refetchOnMount: true },
  );

export const useUpdateProfile = () =>
  useMutationFunc<APIResponse<{ user: User }>, Partial<Pick<User, "fullname" | "phone">> & { preferred_sub_city?: string | null; telegram_username?: string | null }>({
    onSuccess: (data) => {
      const { accessToken, setSession } = useUserStore.getState();
      if (accessToken) setSession(data.payload.user, accessToken);
    },
  });

export const useChangePassword = () =>
  useMutationFunc<APIResponse<{ otherSessionsSignedOut: number }>, { current_password: string; new_password: string }>();

export const useRevokeSession = () => useMutationFunc<APIResponse<null>, undefined>();

/** Ask for a new confirmation link (signed in). Limited to a few an hour. */
export const useResendVerification = () =>
  useMutationFunc<APIResponse<{ sent: boolean; alreadyVerified: boolean }>, undefined>();
