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
  /** Office node — ISSUED_BY + LOCATED_IN per data dictionary §3.2 */
  office?: OfficeInfo;
  rejectionReasons: string[];
  lastVerified?: string;
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
