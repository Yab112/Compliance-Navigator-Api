/** Provider marketplace: Guday Geday agents and agencies. */

import type { AgentEvent } from "./guday";
import type { HirePaymentStatus, PayoutAccount } from "./payments";

export type ProviderType = "guday_geday" | "agency";
export type EntityType = "individual" | "company";
export type ProviderStatus = "pending" | "approved" | "rejected" | "suspended";
export type FeeUnit = "per_job" | "percent" | "per_hour" | "negotiable";
export type LicenseStatus = "none" | "pending" | "verified" | "rejected";
export type ProviderAdminAction = "approve" | "reject" | "suspend" | "reinstate" | "renew";
export type HireStatus = "open" | "requested" | "accepted" | "in_progress" | "completed" | "declined" | "cancelled";
export type SortKey = "score" | "rating" | "reviews" | "newest";

export type ScorePart = { key: string; label: string; max: number; points: number; detail: string };

export type ProviderService = {
  id: string;
  name: string;
  institution?: string | null;
  fee_text?: string | null;
  processing_time_text?: string | null;
};

export type TeamMember = {
  membership_id: string;
  status: "pending" | "active";
  initiated_by: "member" | "agency";
  role_title?: string | null;
  invited_email?: string | null;
  id: string;
  slug: string;
  display_name: string;
  photo_url?: string | null;
  headline?: string | null;
  trust_score: number;
  rating_avg: number;
  rating_count: number;
  completed_count: number;
  id_verified: boolean;
};

export type AgencyLink = {
  membership_id: string;
  status: "pending" | "active";
  initiated_by: "member" | "agency";
  id: string;
  slug: string;
  display_name: string;
  photo_url?: string | null;
  trust_score: number;
};

export type Review = {
  id: string;
  rating: number;
  communication?: number | null;
  fee_honesty?: number | null;
  speed?: number | null;
  outcome?: number | null;
  would_hire_again?: boolean | null;
  comment?: string | null;
  reply?: string | null;
  replied_at?: string | null;
  created_at: string;
  job_title?: string | null;
  service_name?: string | null;
  client_name: string;
  hidden?: boolean;
  hidden_reason?: string | null;
  hidden_by?: string | null;
  /** The client paid for this job through Compliance Navigator */
  paid_through_platform?: boolean;
};

/** What anyone can see */
export type PublicProvider = {
  id: string;
  slug: string;
  provider_type: ProviderType;
  entity_type: EntityType;
  registration_no: string | null;
  display_name: string;
  display_name_am?: string | null;
  legal_name?: string | null;
  headline?: string | null;
  bio?: string | null;
  photo_url?: string | null;
  /** Only on your own profile: contact details reach clients through an accepted hire */
  phone?: string;
  telegram_username?: string | null;
  email?: string | null;
  website?: string | null;
  sub_city?: string | null;
  service_areas: string[];
  specialties: string[];
  service_ids: string[];
  languages: string[];
  experience_years: number;
  fee_from?: number | null;
  fee_to?: number | null;
  fee_unit: FeeUnit;
  pricing_notes?: string | null;
  highlights: string[];
  external_license_type?: string | null;
  external_license_status: LicenseStatus;
  accepting_work: boolean;
  completed_count: number;
  response_hours?: number | null;
  trust_score: number;
  score_breakdown: ScorePart[];
  rating_avg: number;
  rating_count: number;
  /** Job Success percent over closed jobs (last 24 months); null until 3 closed jobs */
  job_success?: number | null;
  closed_jobs?: number;
  id_verified: boolean;
  registered_business: boolean;
  license_expires_at?: string | null;
  approved_at?: string | null;
  created_at: string;
  is_sample?: boolean;
};

export type ProviderProfileView = PublicProvider & {
  services: ProviderService[];
  team: TeamMember[];
  agency: AgencyLink | null;
  reviews: { total: number; items: Review[] };
  is_new: boolean;
  /** Review counts per star, "5" down to "1" */
  rating_distribution: Record<string, number>;
  rating_breakdown: {
    communication: number | null;
    fee_honesty: number | null;
    speed: number | null;
    outcome: number | null;
    would_hire_again: number | null;
  };
};

/** Owner and admin view */
export type Provider = PublicProvider & {
  user_id?: string | null;
  status: ProviderStatus;
  national_id?: string | null;
  tin?: string | null;
  trade_license_no?: string | null;
  license_document_url?: string | null;
  id_document_url?: string | null;
  representative_title?: string | null;
  address?: string | null;
  external_license_no?: string | null;
  external_license_verified_by?: string | null;
  external_license_verified_at?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  updated_at: string;
  /** Registered for VAT: 15% is added to the price and the provider files it */
  vat_registered?: boolean;
  vat_number?: string | null;
  id_verification_method?: "fayda" | "fayda_sandbox" | null;
  verified_name?: string | null;
  services?: ProviderService[];
  team?: TeamMember[];
  agency?: AgencyLink | null;
};

export type MyProvider = Provider & {
  payout?: PayoutAccount;
  tips: string[];
  completeness: { percent: number; items: { key: string; label: string; done: boolean }[] };
};

export type AdminProvider = Provider & {
  open_jobs?: number;
  open_disputes?: number;
  events?: AgentEvent[];
  engagements?: Pick<Hire, "id" | "title" | "client_name" | "service_name" | "status" | "disputed" | "dispute_status" | "created_at">[];
  reviews?: { total: number; items: Review[] };
  name_mismatch?: boolean;
};

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

export type ProviderFormValues = {
  display_name: string;
  display_name_am?: string;
  headline?: string;
  bio?: string;
  phone: string;
  telegram_username?: string;
  email?: string;
  website?: string;
  address?: string;
  service_areas: string[];
  specialties: string[];
  service_ids: string[];
  languages: string[];
  experience_years: number;
  fee_from?: number | null;
  fee_to?: number | null;
  fee_unit: FeeUnit;
  pricing_notes?: string;
  highlights: string[];
  accepting_work?: boolean;
  legal_name?: string;
  tin?: string;
  trade_license_no?: string;
  representative_title?: string;
  external_license_type?: string;
  external_license_no?: string;
  vat_registered?: boolean;
  vat_number?: string | null;
};

export type ProviderJoinInput = ProviderFormValues & {
  provider_type: ProviderType;
  entity_type: EntityType;
  national_id?: string;
};

export type ProviderListParams = {
  type?: ProviderType;
  entity?: EntityType;
  specialty?: string;
  service_id?: string;
  area?: string;
  min_score?: number;
  verified_only?: boolean;
  q?: string;
  language?: string;
  max_fee?: number;
  sort?: SortKey;
  limit?: number;
  offset?: number;
};

export type MarketplaceStats = {
  agents: Partial<Record<ProviderStatus, number>>;
  cases: Partial<Record<HireStatus, number>>;
  approvedBySubCity: { sub_city: string; c: number }[];
  licensesExpiringIn30Days: number;
  byType: { provider_type: ProviderType; entity_type: EntityType; c: number }[];
  licensesPending: number;
  openDisputes: number;
  reviews: number;
  hiddenReviews: number;
};

export type AdminReview = Review & {
  provider_name: string;
  provider_slug: string;
  client_email?: string | null;
};
