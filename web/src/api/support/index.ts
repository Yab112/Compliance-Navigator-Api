"use client";

import { useQueryClient } from "@tanstack/react-query";
import { withQuery } from "@/api/catalog/with-query";
import { useFetchData } from "@/hooks/use-query";
import useMutationFunc from "@/hooks/use-mutation";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import { useUserStore } from "@/store/user-store";
import { useAdminMutation, useAdminQuery } from "@/api/admin/use-admin-query";
import type { APIResponse } from "@/types/global";
import type {
  AdminTicketDetail,
  NewTicketInput,
  SupportMeta,
  SupportSummary,
  SupportTicket,
  TicketPatch,
  TicketThread,
} from "@/types/support";

const p = apiPaths.support;
const a = apiPaths.admin;

/** Queues and how to reach the team; public. */
export const useSupportMeta = () =>
  useFetchData<APIResponse<SupportMeta>>(["support", "meta"], p.meta, { staleTime: 60 * 60 * 1000, retry: false });

export const MY_TICKETS_PAGE_SIZE = 20;

/** One page of the signed-in person's tickets; refreshes every minute so staff replies show up. */
export const useMyTickets = (page = 0, limit = MY_TICKETS_PAGE_SIZE) => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  return useFetchData<APIResponse<{ items: SupportTicket[]; total: number }>>(
    ["support", "mine", limit, page],
    withQuery(p.tickets, { limit, offset: page * limit }),
    {
      enabled: signedIn,
      staleTime: 0,
      refetchInterval: 60 * 1000,
    },
  );
};

export const useMyTicket = (id: string) => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  return useFetchData<APIResponse<TicketThread>>(["support", "ticket", id], p.ticket(id), {
    enabled: signedIn && !!id,
    staleTime: 0,
    refetchInterval: 30 * 1000,
  });
};

/** Customer writes: new ticket (works signed out) and replies on their own ticket. */
export const useSupportWrite = () => {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<{ ticket: SupportTicket; messages?: TicketThread["messages"] }>, unknown>();
  const run = async (url: string, body: unknown) => {
    const res = await mutateAsync({ url, method: MTD.POST, body, headers: { "Content-Type": "application/json" } });
    await queryClient.invalidateQueries({ queryKey: ["support"] });
    return res.payload;
  };
  return {
    createTicket: (body: NewTicketInput) => run(p.tickets, body),
    reply: (id: string, body: string) => run(p.messages(id), { body }),
    isPending,
  };
};

// ---------------------------------------------------------------- staff

export type TicketFilters = {
  queue?: string;
  status?: string;
  assigned?: "me" | "none";
  priority?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

export const useSupportSummary = () =>
  useAdminQuery<SupportSummary>(["support", "summary"], a.supportSummary, { refetchInterval: 60 * 1000 });

export const useSupportTickets = (filters: TicketFilters) => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v !== undefined && v !== "") qs.set(k, String(v));
  return useAdminQuery<{ total: number; items: SupportTicket[] }>(
    ["support", "tickets", filters],
    `${a.supportTickets}?${qs.toString()}`,
    { refetchInterval: 30 * 1000 },
  );
};

export const useSupportTicket = (id: string) =>
  useAdminQuery<AdminTicketDetail>(["support", "ticket", id], a.supportTicket(id), { refetchInterval: 20 * 1000 });

export const useSupportDesk = () => {
  const { run, isPending } = useAdminMutation<TicketThread, unknown>();
  return {
    reply: (id: string, body: string, internal: boolean) => run(a.supportMessages(id), MTD.POST, { body, internal }),
    update: (id: string, patch: TicketPatch) => run(a.supportTicket(id), MTD.PATCH, patch),
    isPending,
  };
};
