import type { Hire } from "@cn/core/types/provider";

/**
 * Where a hire stands, and what each side does next. One source of truth for the client's card,
 * the provider's card and the "needs your action" counts in the header.
 *
 * requested -> accepted (price agreed) -> in progress -> delivered (provider's note; this asks the
 * client to pay) -> paid = closed -> reviewed. Without online payment the client confirms delivery
 * instead, or it closes after AUTO_CLOSE_DAYS.
 */
export type HireStage =
  | "matching"
  | "requested"
  | "agree_price"
  | "accepted"
  | "in_progress"
  | "delivered"
  | "paying"
  | "closed"
  | "reviewed"
  | "declined"
  | "cancelled";

export const AUTO_CLOSE_DAYS = 7;

export const TIMELINE = [
  { key: "requested", label: "Requested" },
  { key: "accepted", label: "Accepted" },
  { key: "in_progress", label: "In progress" },
  { key: "delivered", label: "Delivered" },
  { key: "closed", label: "Paid and closed" },
] as const;

export function hireStage(h: Hire): HireStage {
  if (h.status === "declined") return "declined";
  if (h.status === "cancelled") return "cancelled";
  if (h.status === "open") return "matching";
  if (h.status === "requested") return "requested";
  if (h.status === "completed") {
    if (h.client_confirmed_at) return h.review_id ? "reviewed" : "closed";
    return h.payment_status === "pending" ? "paying" : "delivered";
  }
  if (h.status === "in_progress") return "in_progress";
  return h.agreed_price == null ? "agree_price" : "accepted";
}

/** How far along the timeline a stage is (index into TIMELINE). */
export function timelineIndex(stage: HireStage): number {
  switch (stage) {
    case "matching":
    case "requested":
      return 0;
    case "agree_price":
    case "accepted":
      return 1;
    case "in_progress":
      return 2;
    case "delivered":
    case "paying":
      return 3;
    default:
      return 4;
  }
}

export const STAGE_LABEL: Record<HireStage, string> = {
  matching: "Finding a provider",
  requested: "Waiting for acceptance",
  agree_price: "Accepted · agreeing the price",
  accepted: "Accepted · work starts next",
  in_progress: "In progress",
  delivered: "Delivered · waiting for payment",
  paying: "Payment in progress",
  closed: "Paid and closed",
  reviewed: "Paid and closed · reviewed",
  declined: "Declined",
  cancelled: "Cancelled",
};

export function autoCloseDate(h: Hire): Date | null {
  if (!h.completed_at) return null;
  return new Date(new Date(h.completed_at).getTime() + AUTO_CLOSE_DAYS * 24 * 3600 * 1000);
}

const birr = (n?: number | null) => (n == null ? "" : `${n.toLocaleString("en", { maximumFractionDigits: 2 })} ETB`);

/** What the client should know or do now. */
export function clientNext(h: Hire, stage: HireStage, paymentsOn = true): string {
  const who = h.provider_name?.split(" ")[0] ?? "The provider";
  switch (stage) {
    case "matching":
      return "Our staff are matching you with a verified provider.";
    case "requested":
      return `${who} will accept or decline. Their phone and Telegram appear here once they accept.`;
    case "agree_price":
      return `Agree the details with ${who} on Telegram or by phone. ${who} then sets the price.`;
    case "accepted":
      return `${who} starts the work next. You pay ${birr(h.agreed_price)} only once it's delivered.`;
    case "in_progress":
      return `${who} is working on it. You'll be asked to pay once it's delivered.`;
    case "delivered":
      return paymentsOn
        ? `${who} delivered. Check the note below, then pay ${birr(h.agreed_price)} to close the job. Something wrong? Report a problem instead.`
        : `${who} says it's done. Confirm it, or it closes on its own after ${AUTO_CLOSE_DAYS} days.`;
    case "paying":
      return "We are confirming your payment with the payment provider.";
    case "closed":
      return `Paid and closed. Tell others how ${who} did: only people who hired can review.`;
    case "reviewed":
      return "";
    case "declined":
      return `${who} declined${h.declined_reason ? `: ${h.declined_reason}` : ""}. You can choose another provider.`;
    case "cancelled":
      return "This request was cancelled.";
  }
}

/** What the provider should know or do now. */
export function providerNext(h: Hire, stage: HireStage, paymentsOn = true): string {
  const who = h.client_name.split(" ")[0];
  switch (stage) {
    case "requested":
      return `Accept with your price to see ${who}'s phone and Telegram.`;
    case "agree_price":
      return `Set your price. ${who} pays it once you deliver.`;
    case "accepted":
      return "Start the work when you begin.";
    case "in_progress":
      return paymentsOn
        ? `When you're done, mark it delivered and say what you delivered. That asks ${who} to pay ${birr(h.agreed_price)}.`
        : "When you're done, mark it delivered and say what you delivered.";
    case "delivered":
      return paymentsOn
        ? `Waiting for ${who} to pay ${birr(h.agreed_price)}. We follow up if it takes more than two days.`
        : `Waiting for ${who} to confirm.`;
    case "paying":
      return `${who} is paying now.`;
    case "closed":
      return "Paid and closed. Your share is in Earnings.";
    case "reviewed":
      return "";
    default:
      return "";
  }
}

/** Does this hire wait on the client? (header badge) */
export function clientMustAct(h: Hire): boolean {
  const s = hireStage(h);
  return s === "delivered" || s === "closed";
}

/** Does this job wait on the provider? (header badge) */
export function providerMustAct(h: Hire): boolean {
  const s = hireStage(h);
  return s === "requested" || s === "agree_price" || s === "accepted" || s === "in_progress";
}
