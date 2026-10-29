"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useFetchData } from "@cn/core/hooks/use-query";
import { api } from "@cn/core/lib/api";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { useUserStore } from "@cn/core/store/user-store";
import type { APIResponse } from "@cn/core/types/global";

export type AppNotification = {
  id: string;
  kind: string;
  title: string;
  body?: string | null;
  link?: string | null;
  created_at: string;
  read_at?: string | null;
};

/** The signed-in user's notifications; polls every minute while the tab is open. */
export const useNotifications = () => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  return useFetchData<APIResponse<{ items: AppNotification[]; unread: number }>>(
    ["notifications"],
    apiPaths.notifications.list,
    { enabled: signedIn, staleTime: 15 * 1000, refetchInterval: 30 * 1000, refetchOnWindowFocus: true },
  );
};

/** Mark some notifications read, or all of them when ids is omitted. */
export const useMarkNotificationsRead = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (ids?: string[]) => {
      await api.post(`/${apiPaths.notifications.read}`, ids ? { ids } : {});
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notifications"] }),
  });
};
