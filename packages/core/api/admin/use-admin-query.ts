"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useFetchData } from "../../hooks/use-query";
import useMutationFunc from "../../hooks/use-mutation";
import type { APIResponse } from "../../types/global";

type QueryOpts = { enabled?: boolean; refetchInterval?: number | false };

/**
 * GET an admin endpoint and unwrap `payload`. Data counts as fresh for 30 seconds, so moving between
 * pages shows it at once, and it is fetched again when staff come back to the tab (new approvals,
 * tickets or payouts appear without a reload).
 */
export function useAdminQuery<T>(key: readonly unknown[], url: string, opts: QueryOpts = {}) {
  const query = useFetchData<APIResponse<T>>(["admin", ...key], url, {
    staleTime: 30 * 1000,
    retry: false,
    refetchOnWindowFocus: true,
    enabled: opts.enabled,
    refetchInterval: opts.refetchInterval,
  });
  return { ...query, payload: query.data?.payload };
}

/**
 * What to fetch again after a change succeeds:
 * - "all": every admin query (the default; use it for money, access, settings and anything that can
 *   start an approval, since those show up on several pages)
 * - a list of admin keys without the "admin" prefix, e.g. [["support"]], when the change only touches them
 * - "none": for calls that only read (searches, test prompts, queries)
 */
export type AdminRefresh = "all" | "none" | readonly (readonly unknown[])[];

export function useAdminMutation<TResp, TBody>(refresh: AdminRefresh = "all") {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<TResp>, TBody>();
  const run = async (url: string, method: string, body?: TBody) => {
    const res = await mutateAsync({
      url,
      method,
      body,
      headers: { "Content-Type": "application/json" },
    });
    if (refresh === "all") {
      await queryClient.invalidateQueries({ queryKey: ["admin"] });
    } else if (refresh !== "none") {
      await Promise.all(refresh.map((key) => queryClient.invalidateQueries({ queryKey: ["admin", ...key] })));
    }
    return res.payload;
  };
  return { run, isPending };
}
