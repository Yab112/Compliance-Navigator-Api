"use client";

import { useFetchData } from "../../hooks/use-query";
import useMutationFunc from "../../hooks/use-mutation";
import { apiPaths } from "../../lib/constants/api-paths";
import { useUserStore } from "../../store/user-store";
import type { APIResponse } from "../../types/global";
import type { AuthEvent, AuthSession, User } from "../../types/user-types";

export const useMySessions = () =>
  useFetchData<APIResponse<{ sessions: AuthSession[] }>>(["auth", "sessions"], apiPaths.auth.sessions, {
    staleTime: 0,
    refetchOnMount: true,
  });

export const useMyActivity = () =>
  useFetchData<APIResponse<{ events: AuthEvent[] }>>(["auth", "activity"], apiPaths.auth.activity, {
    staleTime: 0,
    refetchOnMount: true,
  });

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
