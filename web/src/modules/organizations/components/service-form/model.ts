import { type Completeness, type ServiceInput, type WorkingService } from "@cn/core/types/organizations";

export const EMPTY_SERVICE: ServiceInput = {
  name: "",
  name_am: "",
  summary: "",
  who_can_apply: "",
  delivery: "in_person",
  online_url: "",
  fee_amount_min: null,
  fee_amount_max: null,
  fee_currency: "ETB",
  fee_notes: "",
  payment_methods: [],
  processing_time_text: "",
  processing_minutes: null,
  legal_basis: "",
  forms: [],
  common_rejection_reasons: [],
  faq: [],
  branch_ids: [],
  outputs: [],
  requirements: [],
  questions: [],
  steps: [],
  fee_schedule: [],
  is_free: false,
  where_to_pay: "",
  no_documents_required: false,
  appointment_required: false,
  appointment_how: "",
  appointment_url: "",
  appointment_phone: "",
  proxy_allowed: null,
  proxy_notes: "",
  online_parts: "",
  languages: ["Amharic"],
  accessibility_notes: "",
  audience: [],
  legal_reference_number: "",
  legal_effective_date: null,
  contact_name: "",
  contact_phone: "",
  contact_email: "",
  output_validity_months: null,
  renewal_service_id: null,
  late_renewal_penalty: "",
  branch_details: [],
};

export const LANGUAGES = ["Amharic", "English", "Afaan Oromo", "Tigrinya", "Somali", "Sign language"];

export function toKey(text: string, taken: string[]): string {
  const base = text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30) || "item";
  let key = base;
  let n = 2;
  while (taken.includes(key)) key = `${base}_${n++}`;
  return key;
}

export const blank = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);
export const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);
export const num = (v: string) => (v === "" ? null : Number(v));

export function fromWorking(s: WorkingService): ServiceInput {
  const keys = Object.keys(EMPTY_SERVICE) as (keyof ServiceInput)[];
  return Object.fromEntries(keys.map((k) => [k, s[k] ?? EMPTY_SERVICE[k]])) as ServiceInput;
}

/** What the API expects: blanks become null, numbers stay numbers. */
export function toPayload(s: ServiceInput): ServiceInput {
  const text = (k: keyof ServiceInput) => blank(s[k] as string | null | undefined);
  return {
    ...s,
    name_am: text("name_am"),
    summary: text("summary"),
    who_can_apply: text("who_can_apply"),
    online_url: text("online_url"),
    fee_notes: text("fee_notes"),
    processing_time_text: text("processing_time_text"),
    legal_basis: text("legal_basis"),
    where_to_pay: text("where_to_pay"),
    appointment_how: text("appointment_how"),
    appointment_url: text("appointment_url"),
    appointment_phone: text("appointment_phone"),
    proxy_notes: text("proxy_notes"),
    online_parts: text("online_parts"),
    accessibility_notes: text("accessibility_notes"),
    legal_reference_number: text("legal_reference_number"),
    legal_effective_date: s.legal_effective_date || null,
    contact_name: text("contact_name"),
    contact_phone: text("contact_phone"),
    contact_email: text("contact_email"),
    late_renewal_penalty: text("late_renewal_penalty"),
    renewal_service_id: s.renewal_service_id || null,
    fee_schedule: s.is_free ? [] : s.fee_schedule.map((r) => ({ ...r, covers: blank(r.covers), notes: blank(r.notes) })),
    branch_details: s.branch_details
      .filter((d) => s.branch_ids.includes(d.branch_id))
      .map((d) => ({ ...d, window: blank(d.window), phone: blank(d.phone), hours_note: blank(d.hours_note), notes: blank(d.notes) })),
    requirements: s.requirements.map((r) => ({
      ...r,
      notes: blank(r.notes),
      photo_specs: blank(r.photo_specs),
      document_id: r.document_id || null,
      issuing_service_id: r.issuing_service_id || null,
      alternatives: (r.alternatives ?? []).filter(Boolean),
    })),
    questions: s.questions.map((q) => ({ ...q, prompt_am: blank(q.prompt_am), rules: q.rules.map((r) => ({ ...r, ineligible: blank(r.ineligible) })) })),
    steps: s.steps.map((st) => ({ ...st, location: blank(st.location), description: blank(st.description) })),
  };
}

/** Mirrors the server's completeness checks (services/org_service.py) so the meter moves as people type. */
export function computeCompleteness(s: ServiceInput): Completeness {
  const has = (v: string | null | undefined) => !!(v && v.trim());
  const online = s.delivery === "online";
  const checks: [string, string, boolean, boolean][] = [
    ["where", "Where people get it: at least one branch, or online only", true, s.branch_ids.length > 0 || online],
    ["fee", "The fee, or that it is free", true, s.is_free || s.fee_schedule.length > 0 || s.fee_amount_min != null],
    ["documents", "Documents to bring, or that none are needed", true, s.requirements.length > 0 || s.no_documents_required],
    ["time", "How long it takes", true, s.processing_minutes != null || has(s.processing_time_text)],
    ["summary", "A short summary", false, has(s.summary)],
    ["who", "Who can apply", false, has(s.who_can_apply)],
    ["audience", "Who the service is for", false, s.audience.length > 0],
    ["payment", "How to pay", false, s.is_free || s.payment_methods.length > 0 || has(s.where_to_pay)],
    ["steps", "Steps at the office", false, s.steps.length > 0 || online],
    [
      "windows",
      "Window or desk at each branch",
      false,
      online || (s.branch_ids.length > 0 && s.branch_ids.every((id) => has(s.branch_details.find((d) => d.branch_id === id)?.window))),
    ],
    [
      "document_details",
      "Original or copy for every document",
      false,
      s.no_documents_required || (s.requirements.length > 0 && s.requirements.every((r) => !!r.original_or_copy)),
    ],
    ["proxy", "Whether someone can apply on the applicant's behalf", false, s.proxy_allowed != null],
    ["outputs", "What the applicant receives", false, s.outputs.length > 0],
    ["legal", "Legal basis", false, has(s.legal_basis)],
    ["contact", "A contact for questions", false, has(s.contact_phone) || has(s.contact_email)],
    ["rejections", "Why applications get sent back", false, s.common_rejection_reasons.length > 0],
    ["languages", "Languages served", false, s.languages.length > 0],
  ];
  const missing = checks.filter((c) => !c[3]).map(([key, label, core]) => ({ key, label, core }));
  return {
    score: Math.round((100 * (checks.length - missing.length)) / checks.length),
    missing,
    core_missing: missing.filter((m) => m.core).map((m) => m.label),
  };
}

export const SECTIONS = [
  { id: "about", title: "About the service", am: "ስለ አገልግሎቱ" },
  { id: "documents", title: "Documents to bring", am: "የሚያስፈልጉ ሰነዶች" },
  { id: "questions", title: "Questions that change the list", am: "ጥያቄዎች" },
  { id: "fees", title: "Fees, payment and time", am: "ክፍያ እና ጊዜ" },
  { id: "where", title: "Where and when", am: "የት እና መቼ" },
  { id: "steps", title: "Steps at the office", am: "ደረጃዎች" },
  { id: "result", title: "Result, rules and contact", am: "ውጤት እና ሕግ" },
  { id: "help", title: "Forms and common questions", am: "ቅጾች" },
  { id: "review", title: "Review and submit", am: "ማጠቃለያ" },
] as const;

export type SectionProps = { form: ServiceInput; set: (patch: Partial<ServiceInput>) => void };
