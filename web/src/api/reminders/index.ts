"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@cn/core/lib/api";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { useUserStore } from "@cn/core/store/user-store";
import type { APIResponse } from "@cn/core/types/global";

export type Reminder = {
  id: string;
  title: string;
  body: string | null;
  due_on: string;
  link: string | null;
  source: "assistant" | "path" | "account";
  created_at: string;
  delivered_at: string | null;
};

const KEY = ["reminders"] as const;

export const useReminders = () => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  return useQuery({
    queryKey: KEY,
    enabled: signedIn,
    queryFn: async () => (await api.get<APIResponse<{ items: Reminder[] }>>(apiPaths.notifications.reminders)).data.payload,
  });
};

export const useAddReminder = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { title: string; due_on: string }) =>
      (await api.post<APIResponse<Reminder>>(apiPaths.notifications.reminders, body)).data.payload,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};

export const useCancelReminder = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => (await api.delete(apiPaths.notifications.reminder(id))).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  });
};
