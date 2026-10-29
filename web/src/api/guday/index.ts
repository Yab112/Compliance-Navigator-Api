"use client";

import { useQueryClient } from "@tanstack/react-query";
import useMutationFunc from "@cn/core/hooks/use-mutation";
import { useFetchData } from "@cn/core/hooks/use-query";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import type { APIResponse } from "@cn/core/types/global";
import type { FaydaStatus, IdVerification } from "@cn/core/types/guday";

// ---------------------------------------------------------------- Fayda ID verification

export const useFaydaStatus = (enabled = true) =>
  useFetchData<APIResponse<FaydaStatus>>(["guday", "fayda"], apiPaths.guday.faydaStatus, {
    enabled,
    staleTime: 0,
    refetchOnMount: true,
  });

export type FaydaSandboxInput = {
  state: string;
  id_number: string;
  full_name: string;
  otp: string;
  birthdate?: string;
  gender?: "Male" | "Female";
};

/** Start → redirect URL (Fayda, or the sandbox page); complete → verified identity. */
export const useFaydaActions = () => {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<unknown>, unknown>();
  const done = () => queryClient.invalidateQueries({ queryKey: ["guday", "fayda"] });
  return {
    isPending,
    start: async () => {
      const res = (await mutateAsync({ url: apiPaths.guday.faydaStart, method: MTD.POST })) as APIResponse<{
        mode: string;
        redirect_url: string;
      }>;
      return res.payload.redirect_url;
    },
    complete: async (code: string, state: string) => {
      const res = (await mutateAsync({
        url: apiPaths.guday.faydaComplete,
        method: MTD.POST,
        body: { code, state },
      })) as APIResponse<{ verification: IdVerification }>;
      await done();
      return res.payload.verification;
    },
    completeSandbox: async (body: FaydaSandboxInput) => {
      const res = (await mutateAsync({
        url: apiPaths.guday.faydaSandboxComplete,
        method: MTD.POST,
        body,
      })) as APIResponse<{ verification: IdVerification }>;
      await done();
      return res.payload.verification;
    },
  };
};
