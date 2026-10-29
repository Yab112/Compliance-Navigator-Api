"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useFetchData } from "@/hooks/use-query";
import useMutationFunc from "@/hooks/use-mutation";
import type { APIResponse } from "@/types/global";

type QueryOpts = { enabled?: boolean; refetchInterval?: number | false };

/** GET an admin endpoint and unwrap `payload`. Admin data is always fresh. */
export function useAdminQuery<T>(key: readonly unknown[], url: string, opts: QueryOpts = {}) {
  const query = useFetchData<APIResponse<T>>(["admin", ...key], url, {
    staleTime: 0,
    retry: false,
    refetchOnWindowFocus: false,
    enabled: opts.enabled,
    refetchInterval: opts.refetchInterval,
  });
  return { ...query, payload: query.data?.payload };
}

/** Mutation that invalidates every admin query on success. */
export function useAdminMutation<TResp, TBody>() {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<TResp>, TBody>();
  const run = async (url: string, method: string, body?: TBody) => {
    const res = await mutateAsync({
      url,
      method,
      body,
      headers: { "Content-Type": "application/json" },
    });
    await queryClient.invalidateQueries({ queryKey: ["admin"] });
    return res.payload;
  };
  return { run, isPending };
}
