"use client";

import { useQueryClient } from "@tanstack/react-query";
import useMutationFunc from "../hooks/use-mutation";
import { useFetchData } from "../hooks/use-query";
import { apiPaths } from "../lib/constants/api-paths";
import { MTD } from "../lib/constants/methods";
import { withQuery } from "./catalog/with-query";
import type { APIResponse } from "../types/global";

/** One document a person must accept, and whether they accepted its current version. */
export interface LegalRequirement {
  key: string;
  title: string;
  titleAm: string;
  version: string;
  effective: string;
  path: string;
  accepted: boolean;
  acceptedAt: string | null;
}

export interface LegalStatus {
  documents: LegalRequirement[];
  pending: string[];
  upToDate: boolean;
}

export interface LegalConsent {
  document: string;
  title: string;
  titleAm: string | null;
  version: string;
  /** False when a newer version has since been published */
  current: boolean;
  path: string | null;
  acceptedAt: string;
}

export const CONSENTS_PAGE_SIZE = 10;

/** What the signed-in person still has to accept (empty `pending` when up to date). */
export const useLegalStatus = (enabled = true) =>
  useFetchData<APIResponse<LegalStatus>>(["legal", "status"], apiPaths.legal.status, {
    enabled,
    staleTime: 0,
    refetchOnMount: true,
  });

/** One page of the versions this person agreed to, newest first. */
export const useMyConsents = (page = 0, enabled = true) =>
  useFetchData<APIResponse<{ items: LegalConsent[]; total: number }>>(
    ["legal", "consents", page],
    withQuery(apiPaths.legal.consents, { limit: CONSENTS_PAGE_SIZE, offset: page * CONSENTS_PAGE_SIZE }),
    { enabled, staleTime: 0 },
  );

/** Accept documents: `{ terms: "1.0" }` (key -> the version the person read). */
export const useAcceptLegal = () => {
  const queryClient = useQueryClient();
  const { mutateAsync, isPending } = useMutationFunc<APIResponse<LegalStatus>, { accept: Record<string, string> }>();
  const accept = async (versions: Record<string, string>) => {
    const data = await mutateAsync({ url: apiPaths.legal.accept, method: MTD.POST, body: { accept: versions } });
    queryClient.setQueryData(["legal", "status"], data);
    await queryClient.invalidateQueries({ queryKey: ["legal", "consents"] });
    // Accepting can list a provider again (their dashboard shows why they are hidden)
    await queryClient.invalidateQueries({ queryKey: ["providers", "me"] });
    return data.payload;
  };
  return { accept, isAccepting: isPending };
};
