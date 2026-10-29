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

// ---------------------------------------------------------------- vetting

export type VettingDocKind = "police_clearance" | "education" | "photo" | "trade_licence" | "tin_certificate" | "id_copy";
export type EducationLevel = "grade_10" | "grade_12" | "tvet" | "diploma" | "degree";
export type VettingDocStatus = "pending" | "verified" | "rejected" | "expired" | "superseded";
/** A requirement's state: verified and expiring both count as done */
export type VettingStatus = "missing" | "pending" | "verified" | "expiring" | "rejected" | "expired" | "below_minimum";

export type VettingDocument = {
  id: string;
  provider_id: string;
  kind: VettingDocKind;
  label: string;
  level?: EducationLevel | null;
  level_label?: string;
  content_type?: string | null;
  size_bytes?: number | null;
  issued_on?: string | null;
  expires_on?: string | null;
  /** When it stops counting: the printed date, or for a police clearance its issue date plus the accepted age */
  valid_until?: string | null;
  days_left?: number | null;
  reference_no?: string | null;
  issuer?: string | null;
  status: VettingDocStatus;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  uploaded_at: string;
  consent_at?: string | null;
};

export type VettingReference = {
  id: string;
  name: string;
  phone: string;
  relationship: string;
  status: "pending" | "confirmed" | "failed";
  checked_by?: string | null;
  checked_at?: string | null;
  note?: string | null;
  created_at: string;
};

export type VettingItem = {
  key: string;
  type: "identity" | "document" | "references" | "telegram";
  kind?: VettingDocKind;
  label: string;
  label_am: string;
  required: boolean;
  status: VettingStatus;
  message?: string | null;
  help?: string;
  needs?: { issued_on: boolean; expires_on: boolean; reference_no: boolean; level: boolean; images_only: boolean };
  reference_label?: string;
  current?: VettingDocument | null;
  waiting?: VettingDocument | null;
  max_age_days?: number;
  min_level?: EducationLevel;
  min_level_label?: string;
  references?: VettingReference[];
  /** Staff only */
  how_to_verify?: string;
  sensitive?: boolean;
};

export type Vetting = {
  complete: boolean;
  /** Why the listing can't be approved or renewed yet */
  blocker: string | null;
  items: VettingItem[];
  max_upload_mb: number;
  education_levels: { key: EducationLevel; label: string }[];
};

export type VettingUpload = {
  kind: VettingDocKind;
  file: File;
  issued_on?: string;
  expires_on?: string;
  reference_no?: string;
  issuer?: string;
  level?: EducationLevel;
  /** Police clearance only: the provider agrees we keep and check it (required) */
  consent?: boolean;
};

/** A name, registration or VAT change from an approved provider, held until staff check it */
export type ProviderChangeRequest = {
  id: string;
  provider_id: string;
  changes: Record<string, string | boolean | null>;
  old_values: Record<string, string | boolean | null>;
  status: "pending" | "approved" | "rejected";
  requested_by?: string | null;
  requested_at: string;
  decided_by?: string | null;
  decided_at?: string | null;
  note?: string | null;
};

export type MyProvider = Provider & {
  vetting?: Vetting;
  pending_change?: ProviderChangeRequest | null;
  /** Refused in the last 30 days, with the reason */
  rejected_change?: ProviderChangeRequest | null;
  payout?: PayoutAccount;
  tips: string[];
  completeness: { percent: number; items: { key: string; label: string; done: boolean }[] };
};

/** What Fayda returned when the person verified their national ID: the proof of identity. */
export type FaydaIdentity = {
  method: "fayda" | "fayda_sandbox";
  id_type: string | null;
  id_last4: string | null;
  verified_name: string | null;
  birthdate: string | null;
  gender: string | null;
  phone: string | null;
  verified_at: string;
};

export type AdminProvider = Provider & {
  /** When renewal opens, and why it can't happen now (null when it can) */
  renewal?: { opens_on: string | null; blocker: string | null };
  identity?: FaydaIdentity | null;
  vetting?: Vetting;
  pending_change?: ProviderChangeRequest | null;
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

/** A provider staff could assign to an open request */
export type AssignCandidate = {
  id: string;
  display_name: string;
  registration_no: string | null;
  provider_type: ProviderType;
  entity_type: EntityType;
  sub_city: string | null;
  service_areas: string[];
  specialties: string[];
  trust_score: number;
  rating_avg: number | null;
  rating_count: number;
  completed_count: number;
  license_expires_at: string | null;
  offers_service: boolean;
  same_specialty: boolean;
  covers_area: boolean;
  open_jobs: number;
};

/** A row of the staff providers list: no national ID, TIN, documents or payout details */
export type AdminProviderRow = Pick<
  PublicProvider,
  | "id" | "slug" | "provider_type" | "entity_type" | "registration_no" | "display_name" | "photo_url"
  | "sub_city" | "service_areas" | "specialties" | "accepting_work" | "id_verified" | "registered_business"
  | "external_license_status" | "trust_score" | "rating_avg" | "rating_count" | "completed_count"
  | "license_expires_at" | "approved_at" | "created_at" | "is_sample"
> & {
  phone: string | null;
  status: ProviderStatus;
  id_verification_method?: "fayda" | "fayda_sandbox" | null;
  has_external_license: boolean;
  open_jobs: number;
  open_disputes: number;
};

/** Whether "Remove sample data" may run here */
export type SampleStatus = { providers: number; can_purge: boolean; reason: string | null };

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
  engagement_id?: string;
};
