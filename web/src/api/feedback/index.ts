"use client";

import useMutationFunc from "@/hooks/use-mutation";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";

export type FeedbackTarget =
  | "document"
  | "gov_service"
  | "office"
  | "agent"
  | "roadmap_step"
  | "org_service"
  | "other";

export type FeedbackInput = { target_type: FeedbackTarget; target_id?: string; message: string };

export const useReportIssue = () => {
  const { mutateAsync, isPending } = useMutationFunc<unknown, FeedbackInput>();
  const report = (body: FeedbackInput) =>
    mutateAsync({ url: apiPaths.feedback, method: MTD.POST, body });
  return { report, isReporting: isPending };
};
