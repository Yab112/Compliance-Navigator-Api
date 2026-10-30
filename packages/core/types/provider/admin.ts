import type { AgentEvent } from "../guday";
import type { ProviderType, EntityType, ProviderStatus, HireStatus, Review, PublicProvider, Provider } from "./profile";
import type { Vetting, ProviderChangeRequest, NotReadyReason, ProviderReadiness, FaydaIdentity } from "./vetting";
import type { Hire } from "./hire";

export type AdminProvider = Provider & {
  /** When renewal opens, and why it can't happen now (null when it can) */
  renewal?: { opens_on: string | null; blocker: string | null };
  identity?: FaydaIdentity | null;
  vetting?: Vetting;
  readiness?: ProviderReadiness;
  pending_change?: ProviderChangeRequest | null;
  open_jobs?: number;
  open_disputes?: number;
  events?: AgentEvent[];
  engagements?: Pick<Hire, "id" | "title" | "client_name" | "service_name" | "status" | "disputed" | "dispute_status" | "created_at">[];
  reviews?: { total: number; items: Review[] };
  name_mismatch?: boolean;
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
  ready_to_work: boolean;
  not_ready_reasons: NotReadyReason[];
};

/** Whether "Remove sample data" may run here */
export type SampleStatus = { providers: number; can_purge: boolean; reason: string | null };

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
