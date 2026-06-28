"use client";

import { useFetchData } from "@/hooks/use-query";
import { apiPaths } from "@/lib/constants/api-paths";
import { getAccessToken } from "@/lib/auth-token";
import { isMockToken, MOCK_USER } from "@/lib/mock-auth";
import type { APIResponse } from "@/types/global";
import type { User } from "@/types/user-types";

const queryKey = ["auth", "me"] as const;

export const useGetCurrentUser = (enabled = true) => {
  const token = getAccessToken();
  const isMock = isMockToken(token);

  const { data, isLoading, isError, refetch } = useFetchData<
    APIResponse<{ user: User }>
  >(queryKey, apiPaths.auth.me, {
    enabled: enabled && !!token && !isMock,
    refetchOnMount: true,
    refetchOnWindowFocus: false,
    staleTime: 2 * 60 * 1000,
  });

  return {
    currentUser: isMock ? MOCK_USER : (data?.payload?.user ?? null),
    isLoading: isMock ? false : isLoading,
    isError: isMock ? false : isError,
    refetchCurrentUser: refetch,
  };
};
