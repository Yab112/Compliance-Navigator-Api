"use client";

import Link from "next/link";
import { useState } from "react";
import {
  useOrgAction,
  useOrgUpload,
  useRequirementOptions,
  useSaveService,
} from "@/api/organizations";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { apiPaths } from "@/lib/constants/api-paths";
import { MTD } from "@/lib/constants/methods";
import { getErrorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import { Field, NativeSelect, useDebounced } from "@/modules/guday/components/shared";
import {
  APPLIES_TO_LABEL,
  AUDIENCE_LABEL,
  FEE_CATEGORY_LABEL,
  PROXY_LABEL,
  type Audience,
  type Branch,
  type BranchDetail,
  type Completeness,
  type FeeCategory,
  type FeeRow,
  type MemberOrganization,
  type OrgServiceListItem,
  type ProxyAllowed,
  type Question,
  type Requirement,
  type Rule,
  type ServiceInput,
  type Step,
  type WorkingService,
} from "@/types/organizations";
import { CompletenessMeter, Panel, ServiceStatusChip } from "./shared";

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

const LANGUAGES = ["Amharic", "English", "Afaan Oromo", "Tigrinya", "Somali", "Sign language"];

function toKey(text: string, taken: string[]): string {
  const base = text.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 30) || "item";
  let key = base;
  let n = 2;
  while (taken.includes(key)) key = `${base}_${n++}`;
  return key;
}

const blank = (v: string | null | undefined) => (v && v.trim() ? v.trim() : null);
const lines = (v: string) => v.split("\n").map((s) => s.trim()).filter(Boolean);
const num = (v: string) => (v === "" ? null : Number(v));

function fromWorking(s: WorkingService): ServiceInput {
  const keys = Object.keys(EMPTY_SERVICE) as (keyof ServiceInput)[];
  return Object.fromEntries(keys.map((k) => [k, s[k] ?? EMPTY_SERVICE[k]])) as ServiceInput;
}

/** What the API expects: blanks become null, numbers stay numbers. */
function toPayload(s: ServiceInput): ServiceInput {
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

const SECTIONS = [
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

type SectionProps = { form: ServiceInput; set: (patch: Partial<ServiceInput>) => void };

type ServiceFormProps = {
  orgId: string;
  org: MemberOrganization | undefined;
  serviceId: string | null;
  loaded: WorkingService | undefined;
  /** Other services of this organization, for the renewal link */
  services?: OrgServiceListItem[];
  /** Called after the first save creates the service */
  onCreated?: (id: string) => void;
  onSubmitted?: () => void;
  /** Where "Back" goes from the first section (the dashboard or the wizard list) */
  onExit: () => void;
  exitLabel: string;
};

/**
 * Everything a path step shows about one service, in sections people move through with
 * Back and Next. Unsaved edits stay in the form while moving between sections.
 */
export function ServiceForm({ orgId, org, serviceId, loaded, services = [], onCreated, onSubmitted, onExit, exitLabel }: ServiceFormProps) {
  const saveService = useSaveService(orgId);
  const action = useOrgAction();
  const [form, setForm] = useState<ServiceInput>(() => (loaded ? fromWorking(loaded) : EMPTY_SERVICE));
  const [id, setId] = useState<string | null>(serviceId);
  const [status, setStatus] = useState(loaded?.status);
  const [isLive, setIsLive] = useState(!!loaded?.is_live);
  const [section, setSection] = useState(0);
  const [visited, setVisited] = useState(0);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [change, setChange] = useState({ change_summary: "", change_reason: "", effective_at: "" });

  const set = (patch: Partial<ServiceInput>) => setForm((f) => ({ ...f, ...patch }));
  const completeness = computeCompleteness(form);
  const branches = org?.branches ?? [];
  const canSave = form.name.trim().length >= 3;

  const go = (i: number) => {
    setSection(i);
    setVisited((v) => Math.max(v, i));
    setMsg(null);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const save = async (): Promise<string | null> => {
    setMsg(null);
    try {
      const saved = await saveService.mutateAsync({ serviceId: id, body: toPayload(form) });
      setForm(fromWorking(saved));
      setStatus(saved.status);
      setIsLive(saved.is_live);
      if (!id) {
        setId(saved.id);
        onCreated?.(saved.id);
      }
      setMsg({ ok: true, text: "Draft saved." });
      return saved.id;
    } catch (err) {
      setMsg({ ok: false, text: getErrorMessage(err, "Could not save") });
      return null;
    }
  };

  const submit = async () => {
    const savedId = await save();
    if (!savedId) return;
    try {
      await action.mutateAsync({
        url: apiPaths.org.submit(orgId, savedId),
        method: MTD.POST,
        body: isLive
          ? { change_summary: change.change_summary.trim(), change_reason: blank(change.change_reason), effective_at: change.effective_at || null }
          : undefined,
      });
      setStatus("submitted");
      setMsg({ ok: true, text: "Submitted. The platform team reviews it before it goes live." });
      onSubmitted?.();
    } catch (err) {
      setMsg({ ok: false, text: getErrorMessage(err) });
    }
  };

  const current = SECTIONS[section];

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      <aside className="space-y-4 lg:sticky lg:top-[calc(var(--nav-h)+1rem)] lg:self-start">
        <div className="border-border bg-card rounded-md border p-3">
          <p className="mb-2 text-xs font-semibold">Path data filled in</p>
          <CompletenessMeter completeness={completeness} compact />
          {status && <div className="mt-2"><ServiceStatusChip status={status} isLive={isLive} /></div>}
        </div>
        <nav aria-label="Service sections">
          <ol className="space-y-1 text-sm">
            {SECTIONS.map((s, i) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => go(i)}
                  disabled={i > visited && !id}
                  aria-current={i === section ? "step" : undefined}
                  className={cn(
                    "w-full rounded-md px-2 py-1.5 text-left disabled:opacity-50",
                    i === section ? "bg-secondary text-primary font-semibold" : "hover:bg-muted",
                  )}
                >
                  {i + 1}. {s.title}
                </button>
              </li>
            ))}
          </ol>
        </nav>
      </aside>

      <div className="min-w-0 space-y-4">
        {status === "changes_requested" && loaded?.admin_note && (
          <p className="rounded-md bg-amber-50 px-4 py-3 text-sm text-amber-900">The platform team asked for changes: {loaded.admin_note}</p>
        )}
        <Panel title={`${section + 1}. ${current.title}`} am={current.am}>
          {current.id === "about" && <AboutSection form={form} set={set} />}
          {current.id === "documents" && <DocumentsSection form={form} set={set} />}
          {current.id === "questions" && <QuestionsSection form={form} set={set} />}
          {current.id === "fees" && <FeesSection form={form} set={set} />}
          {current.id === "where" && <WhereSection form={form} set={set} branches={branches} orgId={orgId} />}
          {current.id === "steps" && <StepsSection form={form} set={set} />}
          {current.id === "result" && <ResultSection form={form} set={set} services={services.filter((s) => s.id !== id)} />}
          {current.id === "help" && <HelpSection form={form} set={set} orgId={orgId} />}
          {current.id === "review" && (
            <ReviewSection
              completeness={completeness}
              isLive={isLive}
              status={status}
              change={change}
              setChange={setChange}
              liveUrl={isLive && org && loaded ? `/organizations/${org.slug}/services/${loaded.slug}` : null}
            />
          )}
        </Panel>

        <div className="border-border bg-card sticky bottom-0 z-10 flex flex-wrap items-center gap-3 border-t py-3">
          <Button type="button" variant="outline" size="lg" onClick={() => (section === 0 ? onExit() : go(section - 1))}>
            ← {section === 0 ? exitLabel : "Back"}
          </Button>
          <Button type="button" variant="outline" size="lg" loading={saveService.isPending} onClick={() => void save()} disabled={!canSave}>
            Save draft
          </Button>
          {section < SECTIONS.length - 1 ? (
            <Button type="button" size="lg" disabled={!canSave} onClick={() => go(section + 1)}>
              Next: {SECTIONS[section + 1].title} →
            </Button>
          ) : (
            <Button
              type="button"
              size="lg"
              loading={action.isPending}
              onClick={() => void submit()}
              disabled={!canSave || status === "submitted" || (isLive && change.change_summary.trim().length < 5)}
            >
              {status === "submitted" ? "Waiting for review" : isLive ? "Submit the change" : "Submit for review"}
            </Button>
          )}
          {id && status !== "archived" && section === SECTIONS.length - 1 && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => action.mutateAsync({ url: apiPaths.org.archive(orgId, id), method: MTD.POST }).then(onExit)}
            >
              Archive service
            </Button>
          )}
          {msg && <p className={msg.ok ? "text-primary text-sm" : "text-destructive text-sm"}>{msg.text}</p>}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- sections

function Checks<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: [T, string][];
  value: T[];
  onChange: (v: T[]) => void;
  label: string;
}) {
  return (
    <fieldset>
      <legend className="text-xs font-medium">{label}</legend>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {options.map(([v, l]) => (
          <label key={v} className="flex items-center gap-1.5">
            <input type="checkbox" checked={value.includes(v)} onChange={(e) => onChange(e.target.checked ? [...value, v] : value.filter((x) => x !== v))} />
            {l}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function AboutSection({ form, set }: SectionProps) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Service name (English)" htmlFor="s-name" required>
        <Input id="s-name" value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="e.g. New trade license" />
      </Field>
      <Field label="ስም (Amharic)" htmlFor="s-name-am">
        <Input id="s-name-am" value={form.name_am ?? ""} onChange={(e) => set({ name_am: e.target.value })} />
      </Field>
      <Field label="Summary" htmlFor="s-summary" required className="sm:col-span-2" hint="One or two sentences people see first on the path">
        <Textarea id="s-summary" rows={2} value={form.summary ?? ""} onChange={(e) => set({ summary: e.target.value })} />
      </Field>
      <Field label="Who can apply" htmlFor="s-who" className="sm:col-span-2" hint="e.g. Residents aged 18 or older registered in the woreda">
        <Textarea id="s-who" rows={2} value={form.who_can_apply ?? ""} onChange={(e) => set({ who_can_apply: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Checks
          label="Who the service is for"
          options={Object.entries(AUDIENCE_LABEL) as [Audience, string][]}
          value={form.audience}
          onChange={(audience) => set({ audience })}
        />
      </div>
      <Field label="How people apply" htmlFor="s-delivery">
        <NativeSelect id="s-delivery" className="h-9" value={form.delivery} onChange={(e) => set({ delivery: e.target.value as ServiceInput["delivery"] })}>
          <option value="in_person">In person at a branch</option>
          <option value="online">Online only</option>
          <option value="both">Online or in person</option>
        </NativeSelect>
      </Field>
      <Field label="Online application link" htmlFor="s-online">
        <Input id="s-online" type="url" value={form.online_url ?? ""} onChange={(e) => set({ online_url: e.target.value })} placeholder="https://" />
      </Field>
      <Field label="What can be done online" htmlFor="s-online-parts" className="sm:col-span-2" hint="e.g. Fill the form and book a slot online, then bring originals">
        <Input id="s-online-parts" value={form.online_parts ?? ""} onChange={(e) => set({ online_parts: e.target.value })} />
      </Field>
      <div className="sm:col-span-2">
        <Checks label="Languages served at the window" options={LANGUAGES.map((l) => [l, l] as [string, string])} value={form.languages} onChange={(languages) => set({ languages })} />
      </div>
      <Field label="Accessibility" htmlFor="s-access" className="sm:col-span-2" hint="e.g. Ground floor window for people with limited mobility">
        <Input id="s-access" value={form.accessibility_notes ?? ""} onChange={(e) => set({ accessibility_notes: e.target.value })} />
      </Field>
    </div>
  );
}

function RequirementLinker({ req, onChange }: { req: Requirement; onChange: (patch: Partial<Requirement>) => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(req.name);
  const q = useDebounced(query.trim(), 300);
  const options = useRequirementOptions(q, open);
  const data = open ? options.data?.payload : undefined;
  const linked = req.issuing_service_id ? "Linked to the service that issues it" : req.document_id ? `Linked to known document "${req.document_id}"` : null;

  return (
    <div className="sm:col-span-2">
      {linked ? (
        <p className="text-primary text-xs">
          ✓ {linked}{" "}
          <button type="button" className="text-destructive ml-1" onClick={() => onChange({ issuing_service_id: null, document_id: null, kind: "document" })}>
            Unlink
          </button>
        </p>
      ) : (
        <button type="button" className="text-primary text-xs font-medium hover:underline" onClick={() => setOpen((v) => !v)}>
          {open ? "Close" : "Link to the organization or document that issues it (connects your service to theirs on the path)"}
        </button>
      )}
      {open && !linked && (
        <div className="bg-secondary/40 mt-2 rounded-md p-3">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search services and documents" aria-label="Search issuers" />
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <div>
              <p className="text-muted-foreground text-[11px] font-semibold uppercase">Services on the platform</p>
              <ul className="mt-1 space-y-1 text-sm">
                {(data?.services ?? []).map((s) => (
                  <li key={s.service_id}>
                    <button
                      type="button"
                      className="hover:text-primary text-left"
                      onClick={() => {
                        onChange({ issuing_service_id: s.service_id, document_id: null, kind: "prerequisite_service" });
                        setOpen(false);
                      }}
                    >
                      {s.name} <span className="text-muted-foreground text-xs">· {s.org_name}</span>
                    </button>
                  </li>
                ))}
                {data && !data.services.length && <li className="text-muted-foreground text-xs">No matching services yet</li>}
              </ul>
            </div>
            <div>
              <p className="text-muted-foreground text-[11px] font-semibold uppercase">Known documents</p>
              <ul className="mt-1 space-y-1 text-sm">
                {(data?.documents ?? []).map((d) => (
                  <li key={d.document_id}>
                    <button
                      type="button"
                      className="hover:text-primary text-left"
                      onClick={() => {
                        onChange({ document_id: d.document_id, issuing_service_id: null, kind: "document" });
                        setOpen(false);
                      }}
                    >
                      {d.name ?? d.document_id}
                      {d.issuing_authority && <span className="text-muted-foreground text-xs"> · {d.issuing_authority}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DocumentsSection({ form, set }: SectionProps) {
  const update = (i: number, patch: Partial<Requirement>) => set({ requirements: form.requirements.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  const add = () =>
    set({
      no_documents_required: false,
      requirements: [
        ...form.requirements,
        {
          key: toKey(`doc ${form.requirements.length + 1}`, form.requirements.map((r) => r.key)),
          kind: "document",
          name: "",
          required: "always",
          notes: "",
          original_or_copy: null,
          copies: null,
          notarized: false,
          translated: false,
          max_age_days: null,
          photo_specs: "",
          applies_to: null,
          alternatives: [],
        },
      ],
    });
  const remove = (i: number) => {
    const key = form.requirements[i].key;
    set({
      requirements: form.requirements.filter((_, j) => j !== i),
      questions: form.questions.map((q) => ({ ...q, rules: q.rules.map((r) => ({ ...r, add_requirements: r.add_requirements.filter((k) => k !== key) })) })),
    });
  };

  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        Everything people must bring to the window. These become their checklist on every path that passes through your office.
      </p>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.no_documents_required} disabled={form.requirements.length > 0} onChange={(e) => set({ no_documents_required: e.target.checked })} />
        No documents are needed for this service
      </label>
      <ol className="space-y-4">
        {form.requirements.map((r, i) => (
          <li key={i} className="border-border grid gap-3 rounded-md border p-4 sm:grid-cols-2">
            <Field label={`Document ${i + 1}`} htmlFor={`r-name-${i}`} required>
              <Input id={`r-name-${i}`} value={r.name} placeholder="e.g. TIN certificate" onChange={(e) => update(i, { name: e.target.value })} />
            </Field>
            <Field label="When is it needed?" htmlFor={`r-req-${i}`} hint={r.required === "conditional" ? "An answer in section 3 adds it" : undefined}>
              <NativeSelect id={`r-req-${i}`} className="h-9" value={r.required} onChange={(e) => update(i, { required: e.target.value as Requirement["required"] })}>
                <option value="always">Always</option>
                <option value="conditional">Only in some cases</option>
              </NativeSelect>
            </Field>
            <Field label="Original or copy" htmlFor={`r-orig-${i}`}>
              <NativeSelect id={`r-orig-${i}`} className="h-9" value={r.original_or_copy ?? ""} onChange={(e) => update(i, { original_or_copy: (e.target.value || null) as Requirement["original_or_copy"] })}>
                <option value="">Not specified</option>
                <option value="original">Original</option>
                <option value="copy">Copy</option>
                <option value="both">Original and a copy</option>
              </NativeSelect>
            </Field>
            <Field label="Number of copies" htmlFor={`r-copies-${i}`}>
              <Input id={`r-copies-${i}`} type="number" min={1} value={r.copies ?? ""} onChange={(e) => update(i, { copies: num(e.target.value) })} />
            </Field>
            <Field label="Needed from" htmlFor={`r-applies-${i}`}>
              <NativeSelect id={`r-applies-${i}`} className="h-9" value={r.applies_to ?? ""} onChange={(e) => update(i, { applies_to: (e.target.value || null) as Requirement["applies_to"] })}>
                <option value="">The applicant (default)</option>
                {(Object.entries(APPLIES_TO_LABEL) as [NonNullable<Requirement["applies_to"]>, string][]).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l.charAt(0).toUpperCase() + l.slice(1)}
                  </option>
                ))}
              </NativeSelect>
            </Field>
            <Field label="Must be issued within (days)" htmlFor={`r-age-${i}`} hint="e.g. 90 for documents from the last 3 months">
              <Input id={`r-age-${i}`} type="number" min={1} value={r.max_age_days ?? ""} onChange={(e) => update(i, { max_age_days: num(e.target.value) })} />
            </Field>
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm sm:col-span-2">
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={!!r.notarized} onChange={(e) => update(i, { notarized: e.target.checked })} />
                Must be notarized
              </label>
              <label className="flex items-center gap-1.5">
                <input type="checkbox" checked={!!r.translated} onChange={(e) => update(i, { translated: e.target.checked })} />
                Needs an Amharic translation
              </label>
            </div>
            <Field label="Photo requirements" htmlFor={`r-photo-${i}`} hint="Only for photos: size, background, how recent">
              <Input id={`r-photo-${i}`} value={r.photo_specs ?? ""} onChange={(e) => update(i, { photo_specs: e.target.value })} placeholder="3x4 cm, white background" />
            </Field>
            <Field label="Accepted instead (one per line)" htmlFor={`r-alt-${i}`}>
              <Textarea id={`r-alt-${i}`} rows={2} value={(r.alternatives ?? []).join("\n")} onChange={(e) => update(i, { alternatives: lines(e.target.value) })} />
            </Field>
            <Field label="Notes" htmlFor={`r-notes-${i}`} className="sm:col-span-2">
              <Input id={`r-notes-${i}`} value={r.notes ?? ""} onChange={(e) => update(i, { notes: e.target.value })} />
            </Field>
            <RequirementLinker req={r} onChange={(patch) => update(i, patch)} />
            <div className="flex justify-end sm:col-span-2">
              <button type="button" className="text-destructive text-xs" onClick={() => remove(i)}>
                Remove document
              </button>
            </div>
          </li>
        ))}
      </ol>
      <Button type="button" variant="outline" onClick={add}>
        + Add a document
      </Button>
    </div>
  );
}

function RuleEditor({ q, rule, conditional, onChange, onRemove }: { q: Question; rule: Rule; conditional: Requirement[]; onChange: (patch: Partial<Rule>) => void; onRemove: () => void }) {
  return (
    <div className="bg-secondary/40 grid gap-2 rounded-md p-3 text-sm sm:grid-cols-[auto_1fr]">
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground">If the answer is</span>
        {q.type === "number" && (
          <NativeSelect aria-label="Comparison" className="h-8 w-20" value={rule.op} onChange={(e) => onChange({ op: e.target.value as Rule["op"] })}>
            <option value="eq">=</option>
            <option value="gt">&gt;</option>
            <option value="gte">≥</option>
            <option value="lt">&lt;</option>
            <option value="lte">≤</option>
          </NativeSelect>
        )}
        {q.type === "yes_no" ? (
          <NativeSelect aria-label="Answer" className="h-8 w-24" value={rule.value} onChange={(e) => onChange({ value: e.target.value })}>
            <option value="yes">Yes</option>
            <option value="no">No</option>
          </NativeSelect>
        ) : q.type === "single_choice" ? (
          <NativeSelect aria-label="Answer" className="h-8 w-40" value={rule.value} onChange={(e) => onChange({ value: e.target.value })}>
            <option value="">Choose</option>
            {q.options.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </NativeSelect>
        ) : (
          <Input aria-label="Answer" className="h-8 w-32" value={rule.value} onChange={(e) => onChange({ value: e.target.value })} />
        )}
      </div>
      <div className="space-y-2">
        {conditional.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            <span className="text-muted-foreground">add:</span>
            {conditional.map((r) => (
              <label key={r.key} className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={rule.add_requirements.includes(r.key)}
                  onChange={(e) => onChange({ add_requirements: e.target.checked ? [...rule.add_requirements, r.key] : rule.add_requirements.filter((k) => k !== r.key) })}
                />
                {r.name || r.key}
              </label>
            ))}
          </div>
        )}
        <Input aria-label="Not eligible reason" className="h-8" placeholder="Or stop here: why the person can't apply (optional)" value={rule.ineligible ?? ""} onChange={(e) => onChange({ ineligible: e.target.value })} />
        <button type="button" className="text-destructive text-xs" onClick={onRemove}>
          Remove rule
        </button>
      </div>
    </div>
  );
}

function QuestionsSection({ form, set }: SectionProps) {
  const conditional = form.requirements.filter((r) => r.required === "conditional");
  const update = (i: number, patch: Partial<Question>) => set({ questions: form.questions.map((q, j) => (j === i ? { ...q, ...patch } : q)) });
  return (
    <div className="space-y-4">
      <p className="text-muted-foreground text-sm">
        Ask what decides which documents apply, for example &quot;Are you renting the premises?&quot;. Each answer can add documents marked
        &quot;Only in some cases&quot; or tell people they can&apos;t apply. Skip this section if the list is the same for everyone.
      </p>
      <ol className="space-y-4">
        {form.questions.map((q, i) => (
          <li key={i} className="border-border space-y-3 rounded-md border p-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_180px]">
              <Field label={`Question ${i + 1}`} htmlFor={`q-${i}`} required>
                <Input id={`q-${i}`} value={q.prompt} onChange={(e) => update(i, { prompt: e.target.value })} />
              </Field>
              <Field label="ጥያቄ (Amharic)" htmlFor={`q-am-${i}`}>
                <Input id={`q-am-${i}`} value={q.prompt_am ?? ""} onChange={(e) => update(i, { prompt_am: e.target.value })} />
              </Field>
              <Field label="Answer type" htmlFor={`q-type-${i}`}>
                <NativeSelect id={`q-type-${i}`} className="h-9" value={q.type} onChange={(e) => update(i, { type: e.target.value as Question["type"], rules: [] })}>
                  <option value="yes_no">Yes / No</option>
                  <option value="single_choice">One of several</option>
                  <option value="number">Number</option>
                  <option value="text">Text</option>
                </NativeSelect>
              </Field>
            </div>
            {q.type === "single_choice" && (
              <Field label="Choices (one per line)" htmlFor={`q-opt-${i}`}>
                <Textarea id={`q-opt-${i}`} rows={3} value={q.options.join("\n")} onChange={(e) => update(i, { options: lines(e.target.value) })} />
              </Field>
            )}
            {q.rules.map((rule, ri) => (
              <RuleEditor
                key={ri}
                q={q}
                rule={rule}
                conditional={conditional}
                onChange={(patch) => update(i, { rules: q.rules.map((r, k) => (k === ri ? { ...r, ...patch } : r)) })}
                onRemove={() => update(i, { rules: q.rules.filter((_, k) => k !== ri) })}
              />
            ))}
            <div className="flex justify-between">
              <button
                type="button"
                className="text-primary text-xs font-medium"
                onClick={() => update(i, { rules: [...q.rules, { op: "eq", value: q.type === "yes_no" ? "yes" : (q.options[0] ?? ""), add_requirements: [], ineligible: "" }] })}
              >
                + Add a rule for an answer
              </button>
              <button type="button" className="text-destructive text-xs" onClick={() => set({ questions: form.questions.filter((_, j) => j !== i) })}>
                Remove question
              </button>
            </div>
          </li>
        ))}
      </ol>
      <Button
        type="button"
        variant="outline"
        onClick={() =>
          set({
            questions: [
              ...form.questions,
              { key: toKey(`q ${form.questions.length + 1}`, form.questions.map((q) => q.key)), prompt: "", prompt_am: "", type: "yes_no", options: [], rules: [] },
            ],
          })
        }
      >
        + Add a question
      </Button>
    </div>
  );
}

const EMPTY_FEE: FeeRow = { category: "everyone", speed: "regular", amount_min: 0, amount_max: null, currency: "ETB", covers: "", notes: "" };

function FeesSection({ form, set }: SectionProps) {
  const update = (i: number, patch: Partial<FeeRow>) => set({ fee_schedule: form.fee_schedule.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
  return (
    <div className="space-y-5">
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={form.is_free} onChange={(e) => set({ is_free: e.target.checked, fee_schedule: e.target.checked ? [] : form.fee_schedule })} />
        This service is free
      </label>
      {!form.is_free && (
        <div className="space-y-3">
          <p className="text-muted-foreground text-sm">
            One line per price. Different prices for foreign nationals, companies or urgent service go on their own line.
          </p>
          {form.fee_schedule.map((r, i) => (
            <div key={i} className="border-border grid gap-3 rounded-md border p-3 sm:grid-cols-[1fr_120px_110px_110px_90px_auto]">
              <Field label="Who pays this" htmlFor={`fee-cat-${i}`}>
                <NativeSelect id={`fee-cat-${i}`} className="h-9" value={r.category} onChange={(e) => update(i, { category: e.target.value as FeeCategory })}>
                  {(Object.entries(FEE_CATEGORY_LABEL) as [FeeCategory, string][]).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </NativeSelect>
              </Field>
              <Field label="Speed" htmlFor={`fee-speed-${i}`}>
                <NativeSelect id={`fee-speed-${i}`} className="h-9" value={r.speed} onChange={(e) => update(i, { speed: e.target.value as FeeRow["speed"] })}>
                  <option value="regular">Regular</option>
                  <option value="urgent">Urgent</option>
                </NativeSelect>
              </Field>
              <Field label="Amount" htmlFor={`fee-min-${i}`}>
                <Input id={`fee-min-${i}`} type="number" min={0} value={r.amount_min} onChange={(e) => update(i, { amount_min: Number(e.target.value || 0) })} />
              </Field>
              <Field label="Up to" htmlFor={`fee-max-${i}`} hint="If it varies">
                <Input id={`fee-max-${i}`} type="number" min={0} value={r.amount_max ?? ""} onChange={(e) => update(i, { amount_max: num(e.target.value) })} />
              </Field>
              <Field label="Currency" htmlFor={`fee-cur-${i}`}>
                <NativeSelect id={`fee-cur-${i}`} className="h-9" value={r.currency} onChange={(e) => update(i, { currency: e.target.value as FeeRow["currency"] })}>
                  <option value="ETB">ETB</option>
                  <option value="USD">USD</option>
                </NativeSelect>
              </Field>
              <div className="flex items-end">
                <Button type="button" variant="ghost" size="sm" aria-label="Remove fee line" onClick={() => set({ fee_schedule: form.fee_schedule.filter((_, j) => j !== i) })}>
                  ✕
                </Button>
              </div>
              <Field label="What it covers" htmlFor={`fee-covers-${i}`} className="sm:col-span-3">
                <Input id={`fee-covers-${i}`} value={r.covers ?? ""} onChange={(e) => update(i, { covers: e.target.value })} placeholder="e.g. Per copy" />
              </Field>
              <Field label="Notes" htmlFor={`fee-notes-${i}`} className="sm:col-span-3">
                <Input id={`fee-notes-${i}`} value={r.notes ?? ""} onChange={(e) => update(i, { notes: e.target.value })} placeholder="e.g. Plus 0.5% of the contract value" />
              </Field>
            </div>
          ))}
          <Button type="button" variant="outline" onClick={() => set({ fee_schedule: [...form.fee_schedule, { ...EMPTY_FEE }] })}>
            + Add a price line
          </Button>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Payment methods" htmlFor="f-pay" hint="Comma separated, e.g. Cash, Telebirr, CBE Birr">
          <Input id="f-pay" value={form.payment_methods.join(", ")} onChange={(e) => set({ payment_methods: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
        </Field>
        <Field label="Where to pay" htmlFor="f-where" hint="e.g. Cashier next to Window 1, or a CBE branch">
          <Input id="f-where" value={form.where_to_pay ?? ""} onChange={(e) => set({ where_to_pay: e.target.value })} />
        </Field>
        <Field label="Processing time, as people should read it" htmlFor="t-text" required>
          <Input id="t-text" value={form.processing_time_text ?? ""} onChange={(e) => set({ processing_time_text: e.target.value })} placeholder="Same day" />
        </Field>
        <Field label="Processing time in minutes" htmlFor="t-min" hint="Used to add up full paths across offices">
          <Input id="t-min" type="number" min={0} value={form.processing_minutes ?? ""} onChange={(e) => set({ processing_minutes: num(e.target.value) })} />
        </Field>
      </div>
    </div>
  );
}

function WhereSection({ form, set, branches, orgId }: SectionProps & { branches: Branch[]; orgId: string }) {
  const detail = (id: string): BranchDetail => form.branch_details.find((d) => d.branch_id === id) ?? { branch_id: id };
  const setDetail = (id: string, patch: Partial<BranchDetail>) =>
    set({ branch_details: [...form.branch_details.filter((d) => d.branch_id !== id), { ...detail(id), ...patch }] });
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-medium">Branches that offer it</p>
        {branches.length === 0 ? (
          <p className="text-muted-foreground mt-1 text-sm">
            No branches yet. Add them in{" "}
            <Link href={`/org/${orgId}`} className="text-primary underline">
              the dashboard
            </Link>{" "}
            or the registration step for branches.
          </p>
        ) : (
          <ul className="mt-2 space-y-3">
            {branches.map((b) => {
              const on = form.branch_ids.includes(b.id);
              const d = detail(b.id);
              return (
                <li key={b.id} className="border-border rounded-md border p-3">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input type="checkbox" checked={on} onChange={(e) => set({ branch_ids: e.target.checked ? [...form.branch_ids, b.id] : form.branch_ids.filter((x) => x !== b.id) })} />
                    {b.name}
                    <span className="text-muted-foreground text-xs font-normal">{b.hours}</span>
                  </label>
                  {on && (
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <Field label="Window or desk" htmlFor={`bd-w-${b.id}`}>
                        <Input id={`bd-w-${b.id}`} value={d.window ?? ""} onChange={(e) => setDetail(b.id, { window: e.target.value })} placeholder="Window 2" />
                      </Field>
                      <Field label="Phone for this service" htmlFor={`bd-p-${b.id}`}>
                        <Input id={`bd-p-${b.id}`} value={d.phone ?? ""} onChange={(e) => setDetail(b.id, { phone: e.target.value })} />
                      </Field>
                      <Field label="Hours differ for this service?" htmlFor={`bd-h-${b.id}`} hint="e.g. Applications only in the morning">
                        <Input id={`bd-h-${b.id}`} value={d.hours_note ?? ""} onChange={(e) => setDetail(b.id, { hours_note: e.target.value })} />
                      </Field>
                      <Field label="Notes for this branch" htmlFor={`bd-n-${b.id}`}>
                        <Input id={`bd-n-${b.id}`} value={d.notes ?? ""} onChange={(e) => setDetail(b.id, { notes: e.target.value })} />
                      </Field>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={form.appointment_required} onChange={(e) => set({ appointment_required: e.target.checked })} />
          An appointment is needed before coming
        </label>
        {form.appointment_required && (
          <>
            <Field label="How to book" htmlFor="ap-how" className="sm:col-span-2">
              <Input id="ap-how" value={form.appointment_how ?? ""} onChange={(e) => set({ appointment_how: e.target.value })} placeholder="Call the desk a day before" />
            </Field>
            <Field label="Booking link" htmlFor="ap-url">
              <Input id="ap-url" type="url" value={form.appointment_url ?? ""} onChange={(e) => set({ appointment_url: e.target.value })} />
            </Field>
            <Field label="Booking phone" htmlFor="ap-phone">
              <Input id="ap-phone" value={form.appointment_phone ?? ""} onChange={(e) => set({ appointment_phone: e.target.value })} />
            </Field>
          </>
        )}
        <Field label="Can someone apply on the applicant's behalf?" htmlFor="proxy">
          <NativeSelect id="proxy" className="h-9" value={form.proxy_allowed ?? ""} onChange={(e) => set({ proxy_allowed: (e.target.value || null) as ProxyAllowed | null })}>
            <option value="">Choose</option>
            {(Object.entries(PROXY_LABEL) as [ProxyAllowed, string][]).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </NativeSelect>
        </Field>
        <Field label="Notes on applying for someone" htmlFor="proxy-notes" hint="Agents on the platform read this before taking a job">
          <Input id="proxy-notes" value={form.proxy_notes ?? ""} onChange={(e) => set({ proxy_notes: e.target.value })} />
        </Field>
      </div>
    </div>
  );
}

function StepsSection({ form, set }: SectionProps) {
  const update = (i: number, patch: Partial<Step>) => set({ steps: form.steps.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  return (
    <div className="space-y-3">
      <p className="text-muted-foreground text-sm">What happens at the office, in order, so people know which window to go to next.</p>
      <ol className="space-y-3">
        {form.steps.map((s, i) => (
          <li key={i} className="border-border grid gap-3 rounded-md border p-4 sm:grid-cols-[1fr_200px_140px_auto]">
            <Field label={`Step ${i + 1}`} htmlFor={`st-${i}`} required>
              <Input id={`st-${i}`} value={s.title} onChange={(e) => update(i, { title: e.target.value })} placeholder="e.g. Pay the fee" />
            </Field>
            <Field label="Where" htmlFor={`st-loc-${i}`}>
              <Input id={`st-loc-${i}`} value={s.location ?? ""} onChange={(e) => update(i, { location: e.target.value })} placeholder="Window 2" />
            </Field>
            <Field label="Minutes" htmlFor={`st-min-${i}`}>
              <Input id={`st-min-${i}`} type="number" min={0} value={s.estimated_minutes ?? ""} onChange={(e) => update(i, { estimated_minutes: num(e.target.value) })} />
            </Field>
            <div className="flex items-end gap-1">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={i === 0}
                aria-label="Move up"
                onClick={() => {
                  const next = [...form.steps];
                  [next[i - 1], next[i]] = [next[i], next[i - 1]];
                  set({ steps: next });
                }}
              >
                ↑
              </Button>
              <Button type="button" size="sm" variant="ghost" aria-label="Remove step" onClick={() => set({ steps: form.steps.filter((_, j) => j !== i) })}>
                ✕
              </Button>
            </div>
            <Field label="Details" htmlFor={`st-desc-${i}`} className="sm:col-span-4">
              <Input id={`st-desc-${i}`} value={s.description ?? ""} onChange={(e) => update(i, { description: e.target.value })} />
            </Field>
          </li>
        ))}
      </ol>
      <Button type="button" variant="outline" onClick={() => set({ steps: [...form.steps, { title: "", location: "", description: "", estimated_minutes: null }] })}>
        + Add a step
      </Button>
    </div>
  );
}

function OutputsField({ form, set }: SectionProps) {
  const [name, setName] = useState("");
  const options = useRequirementOptions("");
  const docs = options.data?.payload.documents ?? [];
  return (
    <div className="sm:col-span-2">
      <p className="text-xs font-medium">What people receive</p>
      <p className="text-muted-foreground mb-2 text-[11px]">
        Link it to a known document so every path that needs it, and every organization that requires it, points people to you.
      </p>
      <ul className="mb-2 space-y-1">
        {form.outputs.map((o, i) => (
          <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{o.name}</span>
            <NativeSelect
              aria-label={`Known document for ${o.name}`}
              className="h-8 w-56"
              value={o.document_id ?? ""}
              onChange={(e) => set({ outputs: form.outputs.map((x, j) => (j === i ? { ...x, document_id: e.target.value || null } : x)) })}
            >
              <option value="">Not linked</option>
              {docs.map((d) => (
                <option key={d.document_id} value={d.document_id}>
                  {d.name ?? d.document_id}
                </option>
              ))}
            </NativeSelect>
            <button type="button" className="text-destructive text-xs" onClick={() => set({ outputs: form.outputs.filter((_, j) => j !== i) })}>
              Remove
            </button>
          </li>
        ))}
      </ul>
      <div className="flex gap-2">
        <Input placeholder="e.g. Trade license certificate" value={name} onChange={(e) => setName(e.target.value)} aria-label="Document this service issues" />
        <Button
          type="button"
          variant="outline"
          disabled={name.trim().length < 2}
          onClick={() => {
            set({ outputs: [...form.outputs, { name: name.trim(), document_id: null }] });
            setName("");
          }}
        >
          Add
        </Button>
      </div>
    </div>
  );
}

function ResultSection({ form, set, services }: SectionProps & { services: OrgServiceListItem[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <OutputsField form={form} set={set} />
      <Field label="Valid for (months)" htmlFor="r-valid" hint="Leave empty if it doesn't expire. Used for renewal reminders">
        <Input id="r-valid" type="number" min={1} value={form.output_validity_months ?? ""} onChange={(e) => set({ output_validity_months: num(e.target.value) })} />
      </Field>
      <Field label="Renewal service" htmlFor="r-renew" hint="If renewal is a separate service">
        <NativeSelect id="r-renew" className="h-9" value={form.renewal_service_id ?? ""} onChange={(e) => set({ renewal_service_id: e.target.value || null })}>
          <option value="">Same service / not applicable</option>
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Penalty for late renewal" htmlFor="r-penalty" className="sm:col-span-2">
        <Input id="r-penalty" value={form.late_renewal_penalty ?? ""} onChange={(e) => set({ late_renewal_penalty: e.target.value })} />
      </Field>
      <Field label="Legal basis" htmlFor="r-legal" hint="Proclamation, regulation or directive">
        <Input id="r-legal" value={form.legal_basis ?? ""} onChange={(e) => set({ legal_basis: e.target.value })} />
      </Field>
      <Field label="Its number" htmlFor="r-legal-no" hint="e.g. 1150/2019">
        <Input id="r-legal-no" value={form.legal_reference_number ?? ""} onChange={(e) => set({ legal_reference_number: e.target.value })} />
      </Field>
      <Field label="In force since" htmlFor="r-legal-date">
        <Input id="r-legal-date" type="date" value={form.legal_effective_date ?? ""} onChange={(e) => set({ legal_effective_date: e.target.value || null })} />
      </Field>
      <div />
      <Field label="Contact for questions: name or desk" htmlFor="r-cname">
        <Input id="r-cname" value={form.contact_name ?? ""} onChange={(e) => set({ contact_name: e.target.value })} />
      </Field>
      <Field label="Contact phone" htmlFor="r-cphone">
        <Input id="r-cphone" value={form.contact_phone ?? ""} onChange={(e) => set({ contact_phone: e.target.value })} />
      </Field>
      <Field label="Contact email" htmlFor="r-cemail">
        <Input id="r-cemail" type="email" value={form.contact_email ?? ""} onChange={(e) => set({ contact_email: e.target.value })} />
      </Field>
    </div>
  );
}

function HelpSection({ form, set, orgId }: SectionProps & { orgId: string }) {
  const upload = useOrgUpload();
  const [formError, setFormError] = useState<string | null>(null);
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div>
        <p className="text-xs font-medium">Application forms (PDF)</p>
        <ul className="my-2 space-y-1 text-sm">
          {form.forms.map((f, i) => (
            <li key={i} className="flex items-center gap-2">
              <span>{f.title}</span>
              <button type="button" className="text-destructive text-xs" onClick={() => set({ forms: form.forms.filter((_, j) => j !== i) })}>
                Remove
              </button>
            </li>
          ))}
        </ul>
        <Input
          type="file"
          accept="application/pdf"
          aria-label="Upload a PDF form"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setFormError(null);
            try {
              const res = await upload<{ url: string; title: string }>(apiPaths.org.forms(orgId), "form", file);
              set({ forms: [...form.forms, { title: res.title.replace(/\.pdf$/i, ""), url: res.url }] });
            } catch (err) {
              setFormError(getErrorMessage(err));
            }
          }}
        />
        {formError && <p className="text-destructive mt-1 text-xs">{formError}</p>}
        <Field label="Fee notes" htmlFor="x-feenotes" className="mt-4">
          <Input id="x-feenotes" value={form.fee_notes ?? ""} onChange={(e) => set({ fee_notes: e.target.value })} />
        </Field>
      </div>
      <Field label="Why applications get sent back (one per line)" htmlFor="x-rej">
        <Textarea id="x-rej" rows={5} value={form.common_rejection_reasons.join("\n")} onChange={(e) => set({ common_rejection_reasons: lines(e.target.value) })} />
      </Field>
      <div className="lg:col-span-2">
        <p className="text-xs font-medium">Questions people ask</p>
        {form.faq.map((f, i) => (
          <div key={i} className="mt-2 space-y-1">
            <Input aria-label="Question" value={f.q} onChange={(e) => set({ faq: form.faq.map((x, j) => (j === i ? { ...x, q: e.target.value } : x)) })} />
            <Textarea aria-label="Answer" rows={2} value={f.a} onChange={(e) => set({ faq: form.faq.map((x, j) => (j === i ? { ...x, a: e.target.value } : x)) })} />
            <button type="button" className="text-destructive text-xs" onClick={() => set({ faq: form.faq.filter((_, j) => j !== i) })}>
              Remove
            </button>
          </div>
        ))}
        <Button type="button" size="sm" variant="outline" className="mt-2" onClick={() => set({ faq: [...form.faq, { q: "", a: "" }] })}>
          + Add question and answer
        </Button>
      </div>
    </div>
  );
}

function ReviewSection({
  completeness,
  isLive,
  status,
  change,
  setChange,
  liveUrl,
}: {
  completeness: Completeness;
  isLive: boolean;
  status?: string;
  change: { change_summary: string; change_reason: string; effective_at: string };
  setChange: (c: { change_summary: string; change_reason: string; effective_at: string }) => void;
  liveUrl: string | null;
}) {
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div className="space-y-5">
      <CompletenessMeter completeness={completeness} />
      {completeness.core_missing.length > 0 && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900">
          You can save and submit now, but the platform team can only publish once the items marked ▲ are filled in.
        </p>
      )}
      {isLive ? (
        <div className="border-border space-y-3 rounded-md border p-4">
          <p className="text-sm font-semibold">This service is live. Tell us about the change · ለውጡን ይንገሩን</p>
          <p className="text-muted-foreground text-sm">
            People following this service on their paths get a notification. The current version stays public until the change takes effect.
          </p>
          <Field label="What changed" htmlFor="ch-summary" required hint="e.g. The fee rises from 302 to 350 ETB">
            <Input id="ch-summary" value={change.change_summary} onChange={(e) => setChange({ ...change, change_summary: e.target.value })} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Effective from" htmlFor="ch-date" hint="Leave empty for as soon as it's approved">
              <Input id="ch-date" type="date" min={today} value={change.effective_at} onChange={(e) => setChange({ ...change, effective_at: e.target.value })} />
            </Field>
            <Field label="Reason or legal reference" htmlFor="ch-reason">
              <Input id="ch-reason" value={change.change_reason} onChange={(e) => setChange({ ...change, change_reason: e.target.value })} placeholder="e.g. Directive 12/2026" />
            </Field>
          </div>
        </div>
      ) : (
        <p className="text-sm">
          When you submit, the platform team checks the service and publishes it. It then appears on every path that needs it.
        </p>
      )}
      {status === "scheduled" && <p className="text-sm text-sky-900">An approved change is waiting for its effective date.</p>}
      {liveUrl && (
        <Link href={liveUrl} className="text-primary text-sm hover:underline">
          View the live version ↗
        </Link>
      )}
    </div>
  );
}
