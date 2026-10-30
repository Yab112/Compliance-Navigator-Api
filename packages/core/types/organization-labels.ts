import type { OrgType, ServiceStatus, Requirement, FeeCategory, Audience, ProxyAllowed } from "./organizations";

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
