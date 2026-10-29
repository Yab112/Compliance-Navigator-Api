/** Organizations that give services, and the services they describe. */

export type OrgType =
  | "federal_institution"
  | "regional_bureau"
  | "sub_city_office"
  | "woreda_office"
  | "bank"
  | "utility"
  | "health"
  | "education"
  | "embassy"
  | "ngo"
  | "private_provider"
  | "other";

export type OrgStatus = "draft" | "pending" | "verified" | "rejected" | "suspended";
export type ServiceStatus = "draft" | "submitted" | "published" | "scheduled" | "changes_requested" | "archived";

export type Weekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export type HoursDay = {
  day: Weekday;
  closed?: boolean;
  open?: string | null;
  close?: string | null;
  lunch_start?: string | null;
  lunch_end?: string | null;
};

export type Branch = {
  id: string;
  name: string;
  region?: string | null;
  sub_city?: string | null;
  woreda?: string | null;
  address?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  map_url?: string | null;
  phone?: string | null;
  hours?: string | null;
  landmark?: string | null;
  email?: string | null;
  hours_schedule?: HoursDay[];
  /** Readable hours built from the weekly grid (public reads) */
  hours_text?: string | null;
};

export type BranchInput = Omit<Branch, "id" | "hours_text">;

/** A branch as it offers one service: the branch plus the service's window and notes there. */
export type ServiceBranch = Branch & {
  window?: string | null;
  service_phone?: string | null;
  hours_note?: string | null;
  service_notes?: string | null;
};

export type PublicOrganization = {
  id: string;
  slug: string;
  name: string;
  name_am?: string | null;
  org_type: OrgType;
  sector?: string | null;
  description?: string | null;
  logo_url?: string | null;
  website?: string | null;
  phone?: string | null;
  email?: string | null;
  hq_address?: string | null;
  region?: string | null;
  sub_city?: string | null;
  catalog_institution_id?: string | null;
  status: OrgStatus;
  created_at: string;
  service_count?: number;
  branch_count?: number;
};

export type ServiceSummary = {
  id: string;
  slug: string;
  name: string;
  name_am?: string | null;
  summary?: string | null;
  delivery: Delivery;
  fee_amount_min?: number | null;
  fee_amount_max?: number | null;
  fee_currency?: string;
  processing_time_text?: string | null;
  processing_minutes?: number | null;
  is_free?: boolean;
  audience?: Audience[];
  confirmed_days_ago?: number | null;
  confirmation_due?: boolean;
};

export type PublicOrganizationDetail = PublicOrganization & {
  branches: Branch[];
  services: ServiceSummary[];
};

export type OrgMember = {
  id: string;
  email: string;
  role: "owner" | "editor";
  accepted: boolean;
  fullname?: string | null;
};

export type MemberOrganization = PublicOrganization & {
  representative_name?: string | null;
  representative_title?: string | null;
  official_email?: string | null;
  has_authorization_letter: boolean;
  verification_note?: string | null;
  reviewed_at?: string | null;
  updated_at: string;
  branches?: Branch[];
  members?: OrgMember[];
  role?: "owner" | "editor";
  my_role?: "owner" | "editor" | "admin";
  onboarding_step?: number;
  submitted_at?: string | null;
  steward_name?: string | null;
  steward_role?: string | null;
  steward_phone?: string | null;
  steward_email?: string | null;
  data_commitment_at?: string | null;
};

export type Completeness = {
  score: number;
  missing: { key: string; label: string; core: boolean }[];
  core_missing: string[];
};

export type OrgServiceListItem = {
  id: string;
  org_id: string;
  slug: string;
  name: string;
  name_am?: string | null;
  summary?: string | null;
  status: ServiceStatus;
  version: number;
  published_at?: string | null;
  updated_at: string;
  admin_note?: string | null;
  is_live: boolean;
  last_confirmed_at?: string | null;
  confirmed_days_ago?: number | null;
  confirmation_due?: boolean;
  completeness?: Completeness | null;
  scheduled_change?: { effective_at: string; summary?: string | null } | null;
};

export type Delivery = "in_person" | "online" | "both";

export type Requirement = {
  key: string;
  kind: "document" | "prerequisite_service";
  name: string;
  document_id?: string | null;
  issuing_service_id?: string | null;
  required: "always" | "conditional";
  notes?: string | null;
  original_or_copy?: "original" | "copy" | "both" | null;
  copies?: number | null;
  notarized?: boolean;
  translated?: boolean;
  max_age_days?: number | null;
  photo_specs?: string | null;
  applies_to?: "applicant" | "each_party" | "each_partner" | "company" | "representative" | null;
  alternatives?: string[];
};

export type FeeCategory = "everyone" | "ethiopian" | "foreign_national" | "diaspora" | "company" | "other";

export type FeeRow = {
  category: FeeCategory;
  speed: "regular" | "urgent";
  amount_min: number;
  amount_max?: number | null;
  currency: "ETB" | "USD";
  covers?: string | null;
  notes?: string | null;
};

export type BranchDetail = {
  branch_id: string;
  window?: string | null;
  phone?: string | null;
  hours_note?: string | null;
  notes?: string | null;
};

export type Audience = "citizen" | "resident" | "company" | "foreigner" | "investor" | "diaspora" | "ngo";
export type ProxyAllowed = "yes" | "with_poa" | "no";

export type Rule = {
  op: "eq" | "gt" | "gte" | "lt" | "lte";
  value: string;
  add_requirements: string[];
  ineligible?: string | null;
};

export type Question = {
  key: string;
  prompt: string;
  prompt_am?: string | null;
  type: "yes_no" | "single_choice" | "number" | "text";
  options: string[];
  rules: Rule[];
};

export type Step = {
  title: string;
  location?: string | null;
  description?: string | null;
  estimated_minutes?: number | null;
};

export type ServiceInput = {
  name: string;
  name_am?: string | null;
  summary?: string | null;
  who_can_apply?: string | null;
  delivery: Delivery;
  online_url?: string | null;
  fee_amount_min?: number | null;
  fee_amount_max?: number | null;
  fee_currency: string;
  fee_notes?: string | null;
  payment_methods: string[];
  processing_time_text?: string | null;
  processing_minutes?: number | null;
  legal_basis?: string | null;
  forms: { title: string; url: string }[];
  common_rejection_reasons: string[];
  faq: { q: string; a: string }[];
  branch_ids: string[];
  outputs: { name: string; document_id?: string | null }[];
  requirements: Requirement[];
  questions: Question[];
  steps: Step[];
  fee_schedule: FeeRow[];
  is_free: boolean;
  where_to_pay?: string | null;
  no_documents_required: boolean;
  appointment_required: boolean;
  appointment_how?: string | null;
  appointment_url?: string | null;
  appointment_phone?: string | null;
  proxy_allowed?: ProxyAllowed | null;
  proxy_notes?: string | null;
  online_parts?: string | null;
  languages: string[];
  accessibility_notes?: string | null;
  audience: Audience[];
  legal_reference_number?: string | null;
  legal_effective_date?: string | null;
  contact_name?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  output_validity_months?: number | null;
  renewal_service_id?: string | null;
  late_renewal_penalty?: string | null;
  branch_details: BranchDetail[];
};

export type WorkingService = ServiceInput & {
  id: string;
  org_id: string;
  slug: string;
  status: ServiceStatus;
  admin_note?: string | null;
  version: number;
  published_at?: string | null;
  updated_at: string;
  is_live: boolean;
  completeness: Completeness;
  org_branch_count?: number;
};

export type IssuedBy = {
  service_id: string;
  service_name: string;
  service_slug: string;
  org_name: string;
  org_slug: string;
};

export type PublicRequirement = Omit<Requirement, "issuing_service_id"> & { issued_by: IssuedBy | null };

export type PublicService = Omit<ServiceInput, "requirements"> & {
  id: string;
  org_id: string;
  slug: string;
  requirements: PublicRequirement[];
  org: { id: string; name: string; slug: string; org_type: OrgType };
  branches: ServiceBranch[];
  confirmed_at?: string | null;
  confirmed_days_ago?: number | null;
  confirmation_due: boolean;
  upcoming_change: {
    effective_at: string;
    summary?: string | null;
    fee_schedule?: FeeRow[];
    fee_amount_min?: number | null;
    fee_amount_max?: number | null;
  } | null;
  change_log: { date: string; summary: string; effective_at?: string | null }[];
  renewal_service: { name: string; slug: string; org_slug: string } | null;
};

export type ImportRow = {
  row: number;
  name: string;
  status: "ready" | "created" | "error";
  errors: string[];
  warnings: string[];
  service_id?: string | null;
  completeness?: number;
};

export type ImportReport = { dry_run: boolean; rows: ImportRow[]; ready: number; created: number; errors: number };

export type OrgReport = {
  id: string;
  service_id?: string | null;
  service_name?: string | null;
  message: string;
  status: "open" | "resolved" | "dismissed";
  org_response?: string | null;
  org_verdict?: "fixed" | "correct" | null;
  /** Staff's closing note, once staff resolve or dismiss the report. */
  resolution_note?: string | null;
  resolved_at?: string | null;
  org_responded_by?: string | null;
  org_responded_at?: string | null;
  created_at: string;
};

export type PathStep = {
  service_id: string;
  name: string;
  slug: string;
  org: { id: string; name: string; slug: string; org_type: OrgType };
  fee_amount_min?: number | null;
  fee_amount_max?: number | null;
  fee_currency?: string;
  processing_time_text?: string | null;
  processing_minutes?: number | null;
  provides: string[];
  is_target: boolean;
};

export type ServicePath = {
  steps: PathStep[];
  organizations: number;
  total_minutes: number;
  cycles: string[][];
};

export type EligibilityResult = {
  eligible: boolean;
  ineligible_reasons: string[];
  unanswered: string[];
  checklist: PublicRequirement[];
  path: ServicePath | null;
};

export type RequirementOptions = {
  services: { service_id: string; name: string; org_name: string; outputs: string[] }[];
  documents: { document_id: string; name?: string | null; issuing_authority?: string | null }[];
};

export type OrgAnalytics = {
  services: {
    service_id: string;
    name: string;
    views: number;
    eligibility_checks: number;
    path_views: number;
    last_30_days: number;
  }[];
};

export type OrgEvent = { action: string; actor?: string | null; note?: string | null; created_at: string; service_id?: string | null };

export type AdminOrganization = MemberOrganization & {
  authorization_letter_key?: string | null;
  reviewed_by?: string | null;
  created_by_email?: string | null;
  live_services?: number;
  services_due?: number;
  open_reports?: number;
  completeness?: number | null;
  services?: OrgServiceListItem[];
  events?: OrgEvent[];
};

export type ServiceSnapshot = Omit<ServiceInput, never> & { id: string; org_id: string; slug: string };

export type Submission = {
  id: string;
  status: "pending" | "scheduled" | "published" | "changes_requested" | "superseded";
  change_summary?: string | null;
  effective_at?: string | null;
  submitted_by?: string | null;
  created_at: string;
  reviewed_at?: string | null;
  admin_note?: string | null;
  service_id: string;
  service_name?: string;
  is_update?: boolean;
  org_id: string;
  org_name: string;
  org_status?: OrgStatus;
};

export type SubmissionDetail = Submission & {
  snapshot: ServiceSnapshot;
  published_snapshot: ServiceSnapshot | null;
  version: number;
  org_slug: string;
  reviewed_by?: string | null;
  change_reason?: string | null;
  live_at?: string | null;
  completeness: Completeness;
  /** Branch id to name, so snapshots read as names. */
  branch_names?: Record<string, string>;
  /** Service id to "name (organization)" for linked services in the snapshots. */
  service_names?: Record<string, string>;
};

/** An invitation waiting for the invited person to accept or decline. */
export type OrgInvite = {
  id: string;
  role: "owner" | "editor";
  created_at: string;
  org_id: string;
  org_name: string;
  org_name_am?: string | null;
  logo_url?: string | null;
  org_status?: OrgStatus;
};

export const ORG_TYPE_LABEL: Record<OrgType, string> = {
  federal_institution: "Federal institution",
  regional_bureau: "Regional bureau",
  sub_city_office: "Sub-city office",
  woreda_office: "Woreda office",
  bank: "Bank",
  utility: "Utility",
  health: "Health facility",
  education: "Education",
  embassy: "Embassy",
  ngo: "NGO",
  private_provider: "Private provider",
  other: "Other",
};

export const SERVICE_STATUS_LABEL: Record<ServiceStatus, string> = {
  draft: "Draft",
  submitted: "In review",
  published: "Live",
  scheduled: "Change scheduled",
  changes_requested: "Changes requested",
  archived: "Archived",
};

export const FEE_CATEGORY_LABEL: Record<FeeCategory, string> = {
  everyone: "Everyone",
  ethiopian: "Ethiopian citizens",
  foreign_national: "Foreign nationals",
  diaspora: "Ethiopian diaspora",
  company: "Companies",
  other: "Other",
};

export const AUDIENCE_LABEL: Record<Audience, string> = {
  citizen: "Citizens",
  resident: "Residents",
  company: "Companies",
  foreigner: "Foreign nationals",
  investor: "Investors",
  diaspora: "Diaspora",
  ngo: "NGOs",
};

export const PROXY_LABEL: Record<ProxyAllowed, string> = {
  yes: "Yes, someone else can apply",
  with_poa: "Yes, with a notarized power of attorney",
  no: "No, the applicant must come in person",
};

export const APPLIES_TO_LABEL: Record<NonNullable<Requirement["applies_to"]>, string> = {
  applicant: "the applicant",
  each_party: "each party",
  each_partner: "each partner",
  company: "the company",
  representative: "the representative",
};
