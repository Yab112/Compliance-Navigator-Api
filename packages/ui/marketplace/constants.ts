import { ADDIS_SUB_CITIES } from "@cn/core/constants/addis-locations";
import type { FeeUnit, HireStatus, ProviderType, PublicProvider } from "@cn/core/types/provider";

export const TYPE_META: Record<ProviderType, { label: string; am: string; plural: string; blurb: string }> = {
  guday_geday: {
    label: "Guday Geday",
    am: "ጉዳይ ገዳይ",
    plural: "Guday Geday agents",
    blurb: "Errand agents who take your file through government and institution offices.",
  },
  agency: {
    label: "Agency",
    am: "ኤጀንሲ",
    plural: "Agencies",
    blurb: "Licensed companies: customs clearing, travel and visa, employment and more.",
  },
};

export const TYPE_ORDER: ProviderType[] = ["guday_geday", "agency"];

export const SPECIALTY_LABELS: Record<string, string> = {
  customs_clearing: "Customs clearing · የጉምሩክ አስተላላፊ",
  travel_visa: "Travel and visa · ጉዞና ቪዛ",
  employment: "Employment agency · የሥራ ስምሪት",
  legal_accounting: "Legal and accounting · ሕግና ሂሳብ",
  consultancy: "Consultancy · ማማከር",
  other: "Other · ሌላ",
};

export const SPECIALTIES: Record<ProviderType, string[]> = {
  guday_geday: [],
  agency: ["customs_clearing", "travel_visa", "employment", "legal_accounting", "consultancy", "other"],
};

export function specialtyLabel(key: string, short = false): string {
  const label = SPECIALTY_LABELS[key] ?? key;
  return short ? label.split(" · ")[0] : label;
}

export const REGIONS = [
  { value: "adama", label: "Adama" },
  { value: "bahir_dar", label: "Bahir Dar" },
  { value: "dire_dawa", label: "Dire Dawa" },
  { value: "hawassa", label: "Hawassa" },
  { value: "mekelle", label: "Mekelle" },
  { value: "gondar", label: "Gondar" },
  { value: "jimma", label: "Jimma" },
  { value: "dessie", label: "Dessie" },
  { value: "harar", label: "Harar" },
  { value: "bishoftu", label: "Bishoftu" },
  { value: "nationwide", label: "Nationwide" },
];

export const AREA_OPTIONS = [...ADDIS_SUB_CITIES.map((s) => ({ value: s.value, label: s.label })), ...REGIONS];

export function areaLabel(value: string): string {
  return AREA_OPTIONS.find((a) => a.value === value)?.label ?? value;
}

export const FEE_UNIT_LABEL: Record<FeeUnit, string> = {
  per_job: "per job",
  percent: "commission",
  per_hour: "per hour",
  negotiable: "negotiable",
};

/** "800 to 1,500 ETB per job", "2 to 3% commission", "Negotiable" */
export function formatFee(p: Pick<PublicProvider, "fee_from" | "fee_to" | "fee_unit">): string {
  const n = (v: number) => v.toLocaleString("en", { maximumFractionDigits: 0 });
  if (p.fee_from == null && p.fee_to == null) return "Fee negotiable";
  const range = p.fee_to != null && p.fee_to !== p.fee_from ? `${n(p.fee_from ?? 0)} to ${n(p.fee_to)}` : n(p.fee_from ?? p.fee_to ?? 0);
  if (p.fee_unit === "percent") return `${range}% commission`;
  if (p.fee_unit === "negotiable") return `From ${range} ETB, negotiable`;
  return `${range} ETB ${FEE_UNIT_LABEL[p.fee_unit]}`;
}

export const HIRE_STATUS: Record<HireStatus, { label: string; className: string }> = {
  open: { label: "Waiting for staff to assign", className: "bg-amber-100 text-amber-900" },
  requested: { label: "Sent to provider", className: "bg-sky-100 text-sky-900" },
  accepted: { label: "Accepted", className: "bg-indigo-100 text-indigo-900" },
  in_progress: { label: "In progress", className: "bg-indigo-100 text-indigo-900" },
  completed: { label: "Completed", className: "bg-emerald-100 text-emerald-900" },
  declined: { label: "Declined", className: "bg-zinc-200 text-zinc-800" },
  cancelled: { label: "Cancelled", className: "bg-zinc-200 text-zinc-700" },
};

export const SUB_RATINGS = [
  { key: "communication", label: "Communication" },
  { key: "fee_honesty", label: "Honest about fees" },
  { key: "speed", label: "Speed" },
  { key: "outcome", label: "Result" },
] as const;

export function memberSince(date?: string | null): string {
  if (!date) return "New";
  return new Date(date).toLocaleDateString("en-GB", { month: "short", year: "numeric" });
}

export function responseLabel(hours?: number | null): string | null {
  if (hours == null) return null;
  if (hours < 1) return "Replies within an hour";
  if (hours < 24) return `Replies in about ${Math.round(hours)} hours`;
  return `Replies in about ${Math.round(hours / 24)} days`;
}
