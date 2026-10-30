/** MESOB one-stop service catalog (mesobcenter.et) */

export type CatalogInstitution = {
  id: string;
  name: string;
  name_am?: string;
  short_name?: string;
  logo_url?: string;
  service_count?: number;
};

export type CatalogService = {
  id: string;
  source_id: number;
  language: "en" | "am";
  name: string;
  institution_id: string;
  institution_short_name?: string | null;
  institution_name?: string;
  required_documents: string[];
  processing_time_text?: string | null;
  processing_minutes?: number | null;
  fee_text?: string | null;
  /** Readable line, e.g. "At ICS: official fee 21,000 ETB, about 5 days" */
  summary?: string;
  fee_etb_min?: number | null;
  fee_etb_max?: number | null;
  fee_has_usd: boolean;
  online_url?: string | null;
  source_url?: string | null;
  institution: {
    id: string;
    name?: string;
    name_am?: string;
    short_name?: string;
    logo_url?: string;
  };
};

export type MesobCenter = {
  id: string;
  name: string;
  city?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  map_url?: string | null;
};

export type CatalogStats = {
  fetchedAt: string | null;
  institutions: number;
  centers: number;
  services: number;
  servicesAm: number;
};

/** Compact MESOB info attached to a roadmap step */
export type MesobStepSummary = {
  available: boolean;
  serviceId: string;
  serviceName: string;
  institution: string;
  feeText?: string | null;
  feeEtbMin?: number | null;
  processingTimeText?: string | null;
  processingMinutes?: number | null;
  requiredDocuments: string[];
  onlineUrl?: string | null;
  sourceUrl?: string | null;
  alternatives: { serviceId: string; serviceName: string }[];
};

/** MESOB service card returned alongside chat replies */
export type CatalogMatch = {
  id: string;
  name: string;
  institution: string;
  feeText?: string | null;
  processingTimeText?: string | null;
  requiredDocuments: string[];
};

/** One row of the unified service directory (any source). */
export type DirectorySource = "organization" | "path" | "mesob";

export type DirectoryItem = {
  id: string;
  source: DirectorySource;
  title: string;
  titleAm?: string | null;
  summary?: string | null;
  provider?: string | null;
  providerAm?: string | null;
  providerLogo?: string | null;
  providerShort?: string | null;
  verified: boolean;
  feeMin?: number | null;
  feeMax?: number | null;
  feeCurrency: string;
  feeText?: string | null;
  time?: string | null;
  documentCount: number;
  href: string;
  updatedAt?: string | null;
};

export type DirectoryResult = {
  total: number;
  counts: Record<DirectorySource, number>;
  items: DirectoryItem[];
};
