import { Badge } from "../badge";
import type { PayoutStatus } from "@cn/core/types/payments";

export const PAYOUT_STATUS: Record<PayoutStatus, { label: string; className: string }> = {
  requested: { label: "Requested", className: "bg-amber-100 text-amber-900" },
  approved: { label: "Processing", className: "bg-sky-100 text-sky-900" },
  paid: { label: "Paid", className: "bg-emerald-100 text-emerald-900" },
  rejected: { label: "Rejected", className: "bg-red-100 text-red-900" },
  failed: { label: "Failed", className: "bg-red-100 text-red-900" },
};

export function PayoutStatusBadge({ status }: { status: PayoutStatus }) {
  const meta = PAYOUT_STATUS[status];
  return <Badge className={meta?.className}>{meta?.label ?? status}</Badge>;
}

/** "CBE ••••6789" */
export function bankLine(bank: string | null | undefined, last4: string | null | undefined): string {
  return [bank, last4 ? `••••${last4}` : null].filter(Boolean).join(" ") || "Bank account";
}
