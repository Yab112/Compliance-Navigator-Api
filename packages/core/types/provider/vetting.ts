import type { PayoutAccount } from "../payments";
import type { Provider } from "./profile";

// ---------------------------------------------------------------- vetting

export type VettingDocKind =
  | "police_clearance" | "education" | "photo" | "trade_licence" | "tin_certificate" | "id_copy"
  | "guarantee_letter" | "guarantor_id" | "guarantor_employment";
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

/** The provider's guarantor (ተያዥ). The ID number is never sent back, only its last 4 digits. */
export type VettingGuarantor = {
  id: string;
  provider_id: string;
  full_name: string;
  phone: string;
  relationship: string;
  sub_city?: string | null;
  woreda?: string | null;
  address?: string | null;
  occupation: string;
  employer?: string | null;
  id_last4: string;
  status: "pending" | "confirmed" | "failed" | "superseded";
  /** Staff only */
  checked_by?: string | null;
  checked_at?: string | null;
  /** Staff's call note; the provider sees it only when the check failed */
  note?: string | null;
  created_at: string;
  superseded_at?: string | null;
};

export type GuarantorInput = {
  full_name: string;
  phone: string;
  relationship: string;
  sub_city: string;
  woreda?: string;
  address?: string;
  occupation: string;
  employer?: string;
  id_number: string;
  consent: boolean;
};

export type VettingItem = {
  key: string;
  type: "identity" | "document" | "references" | "telegram" | "guarantor";
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
  /** Guarantor item: the current guarantor and their papers (each a document item) */
  guarantor?: VettingGuarantor | null;
  documents?: VettingItem[];
  /** Staff only */
  how_to_verify?: string;
  sensitive?: boolean;
  /** Staff only: replaced guarantors, kept on file */
  history?: VettingGuarantor[];
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

/** One reason a provider is not ready to work. fix says where to go: listing (staff), vetting, profile, agreement. */
export type NotReadyReason = { key: string; label: string; fix: "listing" | "vetting" | "profile" | "agreement" };

/** Listed and able to take new work only when every rule holds */
export type ProviderReadiness = {
  listed: boolean;
  reasons: NotReadyReason[];
  checked_at?: string | null;
  profile_required?: Record<string, string>;
};

export type MyProvider = Provider & {
  vetting?: Vetting;
  readiness?: ProviderReadiness;
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
