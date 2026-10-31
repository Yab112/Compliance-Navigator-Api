import type { NotReadyReason } from "./vetting";

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
  /** Readable line, e.g. "At ICS: official fee 21,000 ETB, about 5 days" */
  summary?: string | null;
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
  /** Verified only on the Fayda sandbox (test) screen: shown as "Test ID only", never as verified */
  id_test?: boolean;
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
  /** Every rule holds (listing, vetting, agreements, profile); not_ready_reasons says what is missing */
  ready_to_work?: boolean;
  not_ready_reasons?: NotReadyReason[];
  /** Last four characters of the national ID; the full number is never stored */
  national_id_last4?: string | null;
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
