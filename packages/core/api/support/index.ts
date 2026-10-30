"use client";

import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { withQuery } from "../catalog/with-query";
import { useFetchData } from "../../hooks/use-query";
import useMutationFunc from "../../hooks/use-mutation";
import { apiPaths } from "../../lib/constants/api-paths";
import { MTD } from "../../lib/constants/methods";
import { useUserStore } from "../../store/user-store";
import useAxiosAuth from "../../hooks/use-axios-auth";
import { useAdminMutation, useAdminQuery } from "../admin/use-admin-query";
import type { APIResponse } from "../../types/global";
import type {
  AdminTicketDetail,
  CannedReply,
  CannedReplyInput,
  CannedReplyList,
  CustomerContext,
  NewTicketInput,
  SupportMeta,
  SupportSummary,
  SupportTicket,
  TicketFilters,
  TicketPatch,
  TicketThread,
} from "../../types/support";

export type { TicketFilters } from "../../types/support";

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

function ticketQuery(filters: TicketFilters): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) if (v !== undefined && v !== "") qs.set(k, String(v));
  return qs.toString();
}

export const useSupportSummary = (enabled = true) =>
  useAdminQuery<SupportSummary>(["support", "summary"], a.supportSummary, { refetchInterval: 60 * 1000, enabled });

export const useSupportTickets = (filters: TicketFilters) =>
  useAdminQuery<{ total: number; items: SupportTicket[] }>(
    ["support", "tickets", filters],
    `${a.supportTickets}?${ticketQuery(filters)}`,
    { refetchInterval: 30 * 1000 },
  );

/** Downloads the filtered list as CSV (built on the server, at most 5,000 rows). */
export const useSupportExport = () => {
  const axiosAuth = useAxiosAuth();
  return useCallback(
    async (filters: TicketFilters) => {
      const res = await axiosAuth.get<Blob>(`/${a.supportExport}?${ticketQuery({ ...filters, limit: undefined, offset: undefined })}`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([res.data], { type: "text/csv;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `support-requests-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    [axiosAuth],
  );
};

/** The person behind a ticket: account, hires, payments and other requests. */
export const useSupportCustomer = (id: string) =>
  useAdminQuery<CustomerContext>(["support", "customer", id], a.supportCustomer(id));

export const CANNED_PAGE_SIZE = 25;

/** Saved replies. With ticketId: only that team's, filled in for the ticket. */
export const useCannedReplies = (opts: { ticketId?: string; queue?: string; q?: string; page?: number; limit?: number } = {}) => {
  const limit = opts.limit ?? CANNED_PAGE_SIZE;
  const qs = new URLSearchParams({ limit: String(limit), offset: String((opts.page ?? 0) * limit) });
  if (opts.ticketId) qs.set("ticket_id", opts.ticketId);
  if (opts.queue) qs.set("queue", opts.queue);
  if (opts.q) qs.set("q", opts.q);
  return useAdminQuery<CannedReplyList>(["support", "replies", opts], `${a.supportReplies}?${qs.toString()}`);
};

export const useCannedReplyAdmin = () => {
  const { run, isPending } = useAdminMutation<CannedReply, CannedReplyInput | undefined>([["support"]]);
  return {
    create: (body: CannedReplyInput) => run(a.supportReplies, MTD.POST, body),
    update: (id: string, body: CannedReplyInput) => run(a.supportReply(id), MTD.PUT, body),
    remove: (id: string) => run(a.supportReply(id), MTD.DELETE),
    isPending,
  };
};

export const useSupportTicket = (id: string) =>
  useAdminQuery<AdminTicketDetail>(["support", "ticket", id], a.supportTicket(id), { refetchInterval: 20 * 1000 });

export const useSupportDesk = () => {
  const { run, isPending } = useAdminMutation<TicketThread, unknown>([["support"]]);
  return {
    reply: (id: string, body: string, internal: boolean, opts: { resolve?: boolean; cannedReplyId?: string | null } = {}) =>
      run(a.supportMessages(id), MTD.POST, {
        body,
        internal,
        resolve: !!opts.resolve,
        ...(opts.cannedReplyId && { canned_reply_id: opts.cannedReplyId }),
      }),
    update: (id: string, patch: TicketPatch) => run(a.supportTicket(id), MTD.PATCH, patch),
    isPending,
  };
};
