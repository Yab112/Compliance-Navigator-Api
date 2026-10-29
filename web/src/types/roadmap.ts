import type { MesobStepSummary } from "@cn/core/types/catalog";
import type { FeeRow, IssuedBy, ProxyAllowed, ServiceBranch } from "@cn/core/types/organizations";

/** What the issuing organization published about this step (newer than catalog data). */
export type OrgStepService = {
  serviceId: string;
  serviceName: string;
  serviceNameAm?: string | null;
  orgName: string;
  orgSlug: string;
  serviceSlug: string;
  summary?: string | null;
  branch: ServiceBranch | null;
  otherBranches: number;
  delivery: "in_person" | "online" | "both";
  onlineUrl?: string | null;
  onlineParts?: string | null;
  isFree: boolean;
  feeSchedule: FeeRow[];
  feeAmountMin?: number | null;
  feeAmountMax?: number | null;
  feeCurrency: string;
  feeNotes?: string | null;
  paymentMethods: string[];
  whereToPay?: string | null;
  processingTimeText?: string | null;
  processingMinutes?: number | null;
  requirements: {
    name: string;
    required: "always" | "conditional";
    original_or_copy?: "original" | "copy" | "both" | null;
    copies?: number | null;
    notarized?: boolean;
    translated?: boolean;
    max_age_days?: number | null;
    photo_specs?: string | null;
    applies_to?: string | null;
    alternatives?: string[];
    notes?: string | null;
    issued_by: IssuedBy | null;
  }[];
  noDocumentsRequired: boolean;
  hasQuestions: boolean;
  steps: { title: string; location?: string | null; estimated_minutes?: number | null }[];
  appointment: { required: boolean; how?: string | null; url?: string | null; phone?: string | null };
  proxyAllowed?: ProxyAllowed | null;
  proxyNotes?: string | null;
  languages: string[];
  accessibilityNotes?: string | null;
  legalBasis?: string | null;
  legalReferenceNumber?: string | null;
  forms: { title: string; url: string }[];
  rejectionReasons: string[];
  outputValidityMonths?: number | null;
  lateRenewalPenalty?: string | null;
  contact: { name?: string | null; phone?: string | null; email?: string | null };
  confirmedAt?: string | null;
  confirmedDaysAgo?: number | null;
  confirmationDue: boolean;
  upcomingChange: { effective_at: string; summary?: string | null } | null;
};

export type StepStatus = "completed" | "active" | "blocked";

export type OfficeInfo = {
  name: string;
  parentInstitution: string;
  subCity: string;
  address: string;
  landmark?: string;
  latitude?: number;
  longitude?: number;
  phones: string[];
  workingHours: string;
  referenceImageUrl?: string;
};

export type RoadmapStep = {
  id: string;
  order: number;
  title: string;
  titleAm?: string;
  issuingAuthority: string;
  formCode?: string;
  feeEtb: number | null;
  paymentMethods: string[];
  estimatedDays: string;
  legalBasis?: string;
  sourceUrl?: string;
  status: StepStatus;
  sectorSpecific?: boolean;
  /** What to prepare and bring to the office (data dictionary: required_inputs) */
  requiredInputs: string[];
  /** Document IDs that must be obtained before this step (graph REQUIRES edges) */
  prerequisiteIds: string[];
  /** Office node, ISSUED_BY + LOCATED_IN per data dictionary §3.2 */
  office?: OfficeInfo;
  rejectionReasons: string[];
  lastVerified?: string;
  /** Where this step can be done at a MESOB one-stop center */
  mesob?: MesobStepSummary;
  /** Published by the organization that issues this document */
  orgService?: OrgStepService;
};

export type RoadmapRequest = {
  goal: string;
  goalLabel: string;
  category: string;
  subCity: string;
  subCityLabel: string;
  industry?: string;
  documentsHeld: string[];
};

export type Roadmap = {
  id: string;
  createdAt: string;
  request: RoadmapRequest;
  steps: RoadmapStep[];
  totalEstimatedDays: string;
  /** User-marked completed steps (includes documentsHeld at creation) */
  trackedCompleted: string[];
};
