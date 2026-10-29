/**
 * Turns a service snapshot into readable lines per field, generically, so a field added to the
 * service form shows up in the review without anyone remembering to add it here. Every key except
 * the internal ids is shown, including links, with full URLs.
 */

export type Lookups = { branches: Record<string, string>; services: Record<string, string> };
type Snapshot = Record<string, unknown>;

const HIDDEN = new Set(["id", "org_id"]);

/** Labels in the order staff read a service. Unknown keys follow, humanized. */
export const FIELD_LABELS: Record<string, string> = {
  name: "Name",
  name_am: "Name (Amharic)",
  slug: "Web address name",
  summary: "Summary",
  who_can_apply: "Who can apply",
  audience: "Who it is for",
  delivery: "How to apply",
  online_url: "Online application link",
  online_parts: "Parts done online",
  is_free: "Free",
  fee_amount_min: "Fee from",
  fee_amount_max: "Fee up to",
  fee_currency: "Fee currency",
  fee_schedule: "Fee schedule",
  fee_notes: "Fee notes",
  payment_methods: "Payment methods",
  where_to_pay: "Where to pay",
  processing_time_text: "Processing time",
  processing_minutes: "Processing time in minutes",
  branch_ids: "Branches",
  branch_details: "Branch details",
  appointment_required: "Appointment needed",
  appointment_how: "How to book",
  appointment_url: "Booking link",
  appointment_phone: "Booking phone",
  proxy_allowed: "Applying for someone else",
  proxy_notes: "Notes on applying for someone",
  no_documents_required: "No documents needed",
  requirements: "Documents and requirements",
  questions: "Eligibility questions",
  steps: "Steps at the office",
  forms: "Forms (documents to download)",
  outputs: "What the applicant receives",
  output_validity_months: "Valid for (months)",
  renewal_service_id: "Renewed through",
  late_renewal_penalty: "Late renewal penalty",
  legal_basis: "Legal basis",
  legal_reference_number: "Legal reference number",
  legal_effective_date: "Law in force since",
  common_rejection_reasons: "Why applications get sent back",
  faq: "Questions and answers",
  languages: "Languages",
  accessibility_notes: "Accessibility",
  contact_name: "Contact name",
  contact_phone: "Contact phone",
  contact_email: "Contact email",
};

const humanize = (key: string) => FIELD_LABELS[key] ?? key.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

const isEmpty = (v: unknown) => v == null || v === "" || (Array.isArray(v) && v.length === 0);

function scalar(key: string, value: unknown, ctx: Lookups): string {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  const text = String(value);
  if (key === "branch_id" || key === "branch_ids") return ctx.branches[text] ? `${ctx.branches[text]} (${text.slice(0, 8)})` : `Unknown branch ${text}`;
  if (key === "issuing_service_id" || key === "renewal_service_id") return ctx.services[text] ? `${ctx.services[text]} [${text.slice(0, 8)}]` : `Service ${text}`;
  return text;
}

function inline(key: string, value: unknown, ctx: Lookups): string {
  if (isEmpty(value)) return "-";
  if (Array.isArray(value)) return value.map((v) => inline(key, v, ctx)).join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => !isEmpty(v))
      .map(([k, v]) => `${humanize(k)}: ${inline(k, v, ctx)}`)
      .join("; ");
  }
  return scalar(key, value, ctx);
}

/** One or more lines for a field; an empty field gives no lines. */
export function fieldLines(key: string, value: unknown, ctx: Lookups): string[] {
  if (isEmpty(value)) return [];
  if (Array.isArray(value)) {
    return value.map((item, i) =>
      item && typeof item === "object" ? `${i + 1}. ${inline(key, item, ctx)}` : scalar(key, item, ctx),
    );
  }
  if (typeof value === "object") return [inline(key, value, ctx)];
  return [scalar(key, value, ctx)];
}

const normalize = (v: unknown): string => JSON.stringify(isEmpty(v) ? null : v);

export type FieldRow = { key: string; label: string; before: string[]; after: string[]; changed: boolean };

/** Every field of either version, in reading order, with its lines and whether it changed. */
export function diffSnapshots(before: Snapshot | null, after: Snapshot, ctx: Lookups): FieldRow[] {
  const keys = [...new Set([...Object.keys(FIELD_LABELS), ...Object.keys(after), ...Object.keys(before ?? {})])].filter(
    (k) => !HIDDEN.has(k) && (k in after || (before && k in before)),
  );
  return keys.map((key) => ({
    key,
    label: humanize(key),
    before: before ? fieldLines(key, before[key], ctx) : [],
    after: fieldLines(key, after[key], ctx),
    changed: !!before && normalize(before[key]) !== normalize(after[key]),
  }));
}

export const URL_PATTERN = /(https?:\/\/[^\s;,]+|\/uploads\/public\/[A-Za-z0-9._-]+)/g;

/** Every link anywhere in a snapshot, with the field it sits in. */
export function collectLinks(snap: Snapshot | null): { field: string; url: string }[] {
  if (!snap) return [];
  const out: { field: string; url: string }[] = [];
  const walk = (field: string, v: unknown) => {
    if (typeof v === "string") for (const m of v.match(URL_PATTERN) ?? []) out.push({ field, url: m });
    else if (Array.isArray(v)) v.forEach((x) => walk(field, x));
    else if (v && typeof v === "object") Object.values(v).forEach((x) => walk(field, x));
  };
  for (const [k, v] of Object.entries(snap)) if (!HIDDEN.has(k)) walk(humanize(k), v);
  return out;
}

/** Hostname as the browser will use it: look-alike letters show up as xn-- (punycode). */
export function hostOf(url: string): string | null {
  if (url.startsWith("/uploads/public/")) return null;
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}
