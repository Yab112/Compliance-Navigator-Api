import type { HirePaymentStatus } from "../payments";
import type { DeliveryMode, ProviderType, HireStatus } from "./profile";

export type Hire = {
  id: string;
  client_user_id?: string | null;
  client_name: string;
  /** Hidden from the provider until they accept */
  client_phone: string | null;
  /** True once the provider accepted: both sides can see each other's number */
  contact_shared?: boolean;
  provider_id?: string | null;
  title: string;
  service_id?: string | null;
  service_name?: string | null;
  specialty?: string | null;
  sub_city?: string | null;
  details?: string | null;
  budget?: string | null;
  delivery_mode?: DeliveryMode | null;
  status: HireStatus;
  admin_note?: string | null;
  created_at: string;
  updated_at: string;
  accepted_at?: string | null;
  completed_at?: string | null;
  client_confirmed_at?: string | null;
  declined_reason?: string | null;
  disputed: boolean;
  dispute_reason?: string | null;
  dispute_status?: "open" | "upheld" | "dismissed" | null;
  dispute_note?: string | null;
  provider_name?: string | null;
  provider_slug?: string | null;
  provider_phone?: string | null;
  provider_registration_no?: string | null;
  provider_type?: ProviderType | null;
  provider_photo_url?: string | null;
  review_id?: string | null;
  review_rating?: number | null;
  /** Price the provider named, in birr */
  agreed_price?: number | null;
  price_note?: string | null;
  payment_status?: HirePaymentStatus;
  paid_at?: string | null;
  /** Client view: what the client pays, the price plus VAT when the provider is VAT-registered */
  amount_due?: number | null;
  /** Client view: the VAT part of amount_due (0 when the provider is not VAT-registered) */
  vat_due?: number | null;
  /** The provider charges 15% VAT on their price */
  provider_vat_registered?: boolean;
  /** tx_ref of the successful payment, for the receipt link */
  paid_tx_ref?: string | null;
  /** The provider has a payout account, so the client can pay online */
  provider_accepts_online?: boolean;
  /** Telegram usernames (no @), shared with the other side once the job is accepted */
  provider_telegram?: string | null;
  client_telegram?: string | null;
  /** What the provider said they delivered */
  completion_note?: string | null;
  /** Closed automatically after a week without confirmation or complaint */
  auto_confirmed?: boolean;
  /** The client's review of the provider, on closed jobs */
  review_comment?: string | null;
  review_reply?: string | null;
  review_edited_at?: string | null;
  /** Latest staff decision on a requested review change */
  review_change_status?: "pending" | "approved" | "rejected" | null;
  /** The provider's rating of the client, on closed jobs */
  client_rating?: number | null;
  client_rating_comment?: string | null;
  /** Provider view only: the client's record */
  client_record?: ClientRecord | null;
  /** Staff only: an upheld complaint on a paid job, waiting for a refund */
  refund_needed?: boolean;
  refund_flagged_at?: string | null;
  refund_flagged_by?: string | null;
  dispute_resolved_by?: string | null;
  dispute_resolved_at?: string | null;
};

/** What staff may do to a hire now (the server refuses anything else) */
export type HireStaffAction = "assign" | "cancel" | "reopen" | "note";

/** One line of a hire's history */
export type HireEvent = {
  id: number | null;
  action: string;
  actor_kind: "client" | "provider" | "staff" | "system";
  actor: string | null;
  from_status: HireStatus | null;
  to_status: HireStatus | null;
  note: string | null;
  provider_id: string | null;
  provider_name: string | null;
  created_at: string;
};

export type HirePaymentRow = {
  tx_ref: string;
  gateway: string;
  amount: number;
  status: "pending" | "success" | "failed" | "cancelled";
  payment_method: string | null;
  gateway_reference: string | null;
  commission_amount: number | null;
  provider_amount: number | null;
  created_at: string;
  verified_at: string | null;
};

export type HireTicketRow = {
  id: string;
  ref: string;
  subject: string;
  status: string;
  queue: string;
  from_side: "client" | "provider";
  created_at: string;
  updated_at: string;
};

/** GET admin/marketplace/engagements/{id}. payments and tickets are null without the permission to see them. */
export type AdminHireDetail = {
  hire: Hire;
  events: HireEvent[];
  payments: HirePaymentRow[] | null;
  tickets: HireTicketRow[] | null;
  actions: HireStaffAction[];
};

/** A client's record as providers see it (and as the client sees their own). Never public. */
export type ClientRecord = {
  paid_jobs: number;
  closed_jobs: number;
  cancelled_after_accept: number;
  left_unpaid: number;
  /** Accepted requests that ended: paid, cancelled after acceptance, or left unpaid a week */
  decided: number;
  /** paid / decided, percent; null until 3 decided requests ("New client") */
  hire_rate: number | null;
  rating_avg: number | null;
  rating_count: number;
  member_since: string | null;
};

export type ReviewChange = {
  id: string;
  review_id: string;
  old_rating: number;
  old_comment?: string | null;
  new_rating: number;
  new_comment?: string | null;
  reason: string;
  status: "pending" | "approved" | "rejected";
  decided_by?: string | null;
  decision_note?: string | null;
  decided_at?: string | null;
  created_at: string;
  engagement_id: string;
  job_title: string;
  client_name: string;
  provider_name: string;
  provider_slug: string;
};

export type HireInput = {
  provider_id?: string;
  service_id?: string;
  specialty?: string;
  title?: string;
  client_name: string;
  client_phone: string;
  client_telegram?: string;
  sub_city?: string;
  details?: string;
  budget?: string;
  delivery_mode?: DeliveryMode;
};

export type ReviewInput = {
  rating: number;
  communication?: number;
  fee_honesty?: number;
  speed?: number;
  outcome?: number;
  would_hire_again?: boolean;
  comment?: string;
};
