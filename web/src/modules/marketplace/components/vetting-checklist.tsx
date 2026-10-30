"use client";

import { useState } from "react";
import {
  VETTING_HISTORY_PAGE_SIZE,
  useMarketAction,
  useMyVettingDocuments,
  useUploadVettingDocument,
} from "@cn/core/api/providers";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import type {
  EducationLevel,
  GuarantorInput,
  Vetting,
  VettingDocKind,
  VettingGuarantor,
  VettingItem,
  VettingReference,
  VettingStatus,
  VettingUpload,
} from "@cn/core/types/provider";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager } from "@cn/ui/pager";
import { ErrorState, Field, LoadingState, NativeSelect, formatDate } from "@cn/ui/guday/shared";

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const DOC_TYPES = [...IMAGE_TYPES, "application/pdf"];

export const STATUS_META: Record<VettingStatus, { label: string; tone: string }> = {
  missing: { label: "Needed", tone: "bg-muted text-foreground" },
  pending: { label: "Waiting for staff", tone: "bg-amber-100 text-amber-900" },
  verified: { label: "Verified", tone: "bg-emerald-100 text-emerald-900" },
  expiring: { label: "Verified, expires soon", tone: "bg-amber-100 text-amber-900" },
  rejected: { label: "Not accepted", tone: "bg-red-100 text-red-900" },
  expired: { label: "Expired", tone: "bg-red-100 text-red-900" },
  below_minimum: { label: "Below the minimum", tone: "bg-red-100 text-red-900" },
};

export function VettingStatusBadge({ status }: { status: VettingStatus }) {
  const m = STATUS_META[status];
  return <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap", m.tone)}>{m.label}</span>;
}

const today = () => new Date().toISOString().slice(0, 10);

/** What the provider fills in for one document: the file, plus the dates and number printed on it. */
export type DocumentDraft = Omit<VettingUpload, "file" | "kind"> & { file: File | null };
export const EMPTY_DRAFT: DocumentDraft = { file: null };

/** Checks the browser can do before sending; the server checks the real file type again. */
export function draftError(item: VettingItem, d: DocumentDraft, maxMb: number): string | null {
  if (!d.file) return "Choose a file.";
  const types = item.needs?.images_only ? IMAGE_TYPES : DOC_TYPES;
  if (!types.includes(d.file.type)) return item.needs?.images_only ? "Choose a JPG, PNG or WEBP photo." : "Choose a JPG, PNG or WEBP photo, or a PDF.";
  if (d.file.size > maxMb * 1024 * 1024) return `The file must be ${maxMb} MB or smaller.`;
  if (item.needs?.issued_on && !d.issued_on) return "Enter the date printed on the certificate.";
  if (item.needs?.reference_no && !d.reference_no?.trim()) return `Enter the ${(item.reference_label ?? "reference number").toLowerCase()}.`;
  if (item.needs?.expires_on && !d.expires_on) return "Enter the date it is valid until.";
  if (item.needs?.level && !d.level) return "Choose the level of the certificate.";
  if (item.kind === "police_clearance" && !d.consent) return "Tick the box to agree that we keep and check your police clearance.";
  if (item.kind === "police_clearance" && d.issued_on && item.max_age_days) {
    const age = (Date.now() - new Date(d.issued_on).getTime()) / 86_400_000;
    if (age > item.max_age_days) return `This clearance is older than ${item.max_age_days} days. Get a new one from the police.`;
  }
  return null;
}

/** File and details for one document. Used in the join form and when uploading or replacing later. */
export function DocumentFields({
  item,
  value,
  onChange,
  levels,
  maxMb,
  idPrefix,
}: {
  item: VettingItem;
  value: DocumentDraft;
  onChange: (d: DocumentDraft) => void;
  levels: Vetting["education_levels"];
  maxMb: number;
  idPrefix: string;
}) {
  const id = (f: string) => `${idPrefix}-${item.key}-${f}`;
  const set = (patch: Partial<DocumentDraft>) => onChange({ ...value, ...patch });
  const minIndex = item.min_level ? levels.findIndex((l) => l.key === item.min_level) : 0;
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label="File" htmlFor={id("file")} required hint={`${item.needs?.images_only ? "JPG, PNG or WEBP" : "JPG, PNG, WEBP or PDF"}, up to ${maxMb} MB. Only staff can see it.`} className="sm:col-span-2">
        <Input id={id("file")} type="file" accept={(item.needs?.images_only ? IMAGE_TYPES : DOC_TYPES).join(",")}
          onChange={(e) => set({ file: e.target.files?.[0] ?? null })} />
      </Field>
      {item.needs?.level && (
        <Field label="Level" htmlFor={id("level")} required hint={item.min_level_label ? `At least ${item.min_level_label}.` : undefined}>
          <NativeSelect id={id("level")} value={value.level ?? ""} onChange={(e) => set({ level: (e.target.value || undefined) as EducationLevel | undefined })}>
            <option value="">Choose…</option>
            {levels.slice(Math.max(0, minIndex)).map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}
          </NativeSelect>
        </Field>
      )}
      <Field label="Issue date" htmlFor={id("issued")} required={!!item.needs?.issued_on}
        hint={item.kind === "police_clearance" && item.max_age_days ? `Accepted up to ${item.max_age_days} days after this date.` : undefined}>
        <Input id={id("issued")} type="date" max={today()} value={value.issued_on ?? ""} onChange={(e) => set({ issued_on: e.target.value || undefined })} />
      </Field>
      {(item.needs?.expires_on || item.kind === "trade_licence") && (
        <Field label="Valid until" htmlFor={id("expires")} required={!!item.needs?.expires_on}>
          <Input id={id("expires")} type="date" min={today()} value={value.expires_on ?? ""} onChange={(e) => set({ expires_on: e.target.value || undefined })} />
        </Field>
      )}
      <Field label={item.reference_label ?? "Reference number"} htmlFor={id("ref")} required={!!item.needs?.reference_no}>
        <Input id={id("ref")} maxLength={60} value={value.reference_no ?? ""} onChange={(e) => set({ reference_no: e.target.value })} />
      </Field>
      {item.kind === "police_clearance" && (
        <>
          <Field label="Issued by" htmlFor={id("issuer")} hint="For example: Federal Police Commission">
            <Input id={id("issuer")} maxLength={120} value={value.issuer ?? ""} onChange={(e) => set({ issuer: e.target.value })} />
          </Field>
          <label htmlFor={id("consent")} className="flex items-start gap-2 text-xs sm:col-span-2">
            <input id={id("consent")} type="checkbox" className="mt-0.5 size-4 shrink-0" checked={!!value.consent} aria-required="true"
              onChange={(e) => set({ consent: e.target.checked })} />
            <span>
              I agree that Compliance Navigator keeps and checks my police clearance to vet me as a provider. Only marketplace staff can
              open it, and every time they do is logged. <span className="text-destructive">*</span>
            </span>
          </label>
        </>
      )}
    </div>
  );
}

function UploadForm({ item, vetting, onDone }: { item: VettingItem; vetting: Vetting; onDone: () => void }) {
  const upload = useUploadVettingDocument();
  const [draft, setDraft] = useState<DocumentDraft>(EMPTY_DRAFT);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <form
      className="bg-secondary/40 mt-3 space-y-3 rounded-md p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        const problem = draftError(item, draft, vetting.max_upload_mb);
        if (problem) return setError(problem);
        setBusy(true);
        setError(null);
        try {
          await upload({ ...draft, file: draft.file!, kind: item.kind as VettingDocKind, reference_no: draft.reference_no?.trim() || undefined });
          onDone();
        } catch (err) {
          setError(getErrorMessage(err, "Could not upload the document"));
        } finally {
          setBusy(false);
        }
      }}
    >
      <DocumentFields item={item} value={draft} onChange={setDraft} levels={vetting.education_levels} maxMb={vetting.max_upload_mb} idPrefix="vet" />
      {error && <p className="text-destructive text-xs" role="alert">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={busy} disabled={busy}>Upload</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone} disabled={busy}>Cancel</Button>
      </div>
    </form>
  );
}

function ReferencesForm({ refs, onDone }: { refs: VettingReference[]; onDone: () => void }) {
  const { run, isPending } = useMarketAction<{ references: { name: string; phone: string; relationship: string }[] }>();
  const blank = { name: "", phone: "", relationship: "" };
  // Always room for two: staff need two references, even when one is already saved
  const saved = refs.map((r) => ({ name: r.name, phone: r.phone, relationship: r.relationship }));
  const [rows, setRows] = useState([...saved, ...Array(Math.max(0, 2 - saved.length)).fill(blank)]);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  return (
    <form
      className="bg-secondary/40 mt-3 space-y-3 rounded-md p-3"
      onSubmit={async (e) => {
        e.preventDefault();
        const filled = rows.filter((r) => r.name.trim() || r.phone.trim());
        if (filled.some((r) => !r.name.trim() || !/^(\+251|0)[79]\d{8}$/.test(r.phone.trim()) || !r.relationship.trim())) {
          return setError("Each reference needs a name, an Ethiopian mobile number (09… or 07…) and how they know you.");
        }
        setError(null);
        setNote(null);
        try {
          await run(apiPaths.providers.myReferences, MTD.PUT, { references: filled.map((r) => ({ name: r.name.trim(), phone: r.phone.trim(), relationship: r.relationship.trim() })) });
          // Keep the form open until both are in, so the second one is not forgotten
          if (filled.length < 2) setNote("Saved. Add a second reference too: we need two.");
          else onDone();
        } catch (err) {
          setError(getErrorMessage(err, "Could not save the references"));
        }
      }}
    >
      <p className="text-muted-foreground text-xs">People who know your work, not family. Staff will phone them.</p>
      {rows.map((r, i) => (
        <fieldset key={i} className="grid gap-2 sm:grid-cols-3">
          <legend className="mb-1 text-xs font-medium">Reference {i + 1}</legend>
          <Field label="Name" htmlFor={`ref-${i}-name`}>
            <Input id={`ref-${i}-name`} value={r.name} maxLength={120} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} />
          </Field>
          <Field label="Phone" htmlFor={`ref-${i}-phone`}>
            <Input id={`ref-${i}-phone`} inputMode="tel" value={r.phone} onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, phone: e.target.value } : x)))} />
          </Field>
          <Field label="How they know you" htmlFor={`ref-${i}-rel`}>
            <Input id={`ref-${i}-rel`} value={r.relationship} maxLength={80} placeholder="Former employer" onChange={(e) => setRows(rows.map((x, j) => (j === i ? { ...x, relationship: e.target.value } : x)))} />
          </Field>
        </fieldset>
      ))}
      {rows.length < 3 && (
        <button type="button" className="text-primary text-xs underline" onClick={() => setRows([...rows, blank])}>Add another</button>
      )}
      {error && <p className="text-destructive text-xs" role="alert">{error}</p>}
      {note && <p className="text-primary text-xs" role="status">{note}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={isPending} disabled={isPending}>Save references</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone} disabled={isPending}>{note ? "Close" : "Cancel"}</Button>
      </div>
    </form>
  );
}

const PHONE_RE = /^(\+251|0)[79]\d{8}$/;
const EMPTY_GUARANTOR: GuarantorInput = {
  full_name: "", phone: "", relationship: "", sub_city: "", woreda: "", address: "", occupation: "", employer: "", id_number: "", consent: false,
};

function guarantorError(g: GuarantorInput): string | null {
  if (g.full_name.trim().length < 3) return "Enter your guarantor's full name.";
  if (!PHONE_RE.test(g.phone.replace(/\s/g, ""))) return "Enter your guarantor's Ethiopian mobile number (09… or 07…).";
  if (g.relationship.trim().length < 3) return "Say how the guarantor knows you.";
  if (g.sub_city.trim().length < 2) return "Enter the sub-city or town where the guarantor lives.";
  if (g.occupation.trim().length < 2) return "Enter the guarantor's occupation.";
  if (g.id_number.replace(/[^0-9A-Za-z]/g, "").length < 6) return "Enter the guarantor's national ID or Fayda number.";
  if (!g.consent) return "Tick the box to confirm your guarantor agreed to share their details.";
  return null;
}

/** Add or change the guarantor. Entering a different ID number replaces the guarantor and their papers. */
function GuarantorForm({ current, onDone }: { current: VettingGuarantor | null | undefined; onDone: () => void }) {
  const { run, isPending } = useMarketAction<GuarantorInput>();
  const [g, setG] = useState<GuarantorInput>(current ? {
    ...EMPTY_GUARANTOR, full_name: current.full_name, phone: current.phone, relationship: current.relationship,
    sub_city: current.sub_city ?? "", woreda: current.woreda ?? "", address: current.address ?? "",
    occupation: current.occupation, employer: current.employer ?? "",
  } : EMPTY_GUARANTOR);
  const [error, setError] = useState<string | null>(null);
  const set = (patch: Partial<GuarantorInput>) => setG({ ...g, ...patch });
  const field = (key: keyof GuarantorInput, label: string, opts: { required?: boolean; hint?: string; placeholder?: string; max?: number; tel?: boolean } = {}) => (
    <Field label={label} htmlFor={`g-${key}`} required={opts.required} hint={opts.hint}>
      <Input id={`g-${key}`} value={String(g[key] ?? "")} maxLength={opts.max ?? 120} placeholder={opts.placeholder}
        inputMode={opts.tel ? "tel" : undefined} aria-required={opts.required || undefined}
        onChange={(e) => set({ [key]: e.target.value } as Partial<GuarantorInput>)} />
    </Field>
  );
  return (
    <form
      className="bg-secondary/40 mt-3 space-y-3 rounded-md p-3"
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        const problem = guarantorError(g);
        if (problem) return setError(problem);
        setError(null);
        const trim = (v?: string) => v?.trim() || undefined;
        try {
          await run(apiPaths.providers.myGuarantor, MTD.PUT, {
            full_name: g.full_name.trim(), phone: g.phone.replace(/\s/g, ""), relationship: g.relationship.trim(),
            sub_city: g.sub_city.trim(), woreda: trim(g.woreda), address: trim(g.address), occupation: g.occupation.trim(),
            employer: trim(g.employer), id_number: g.id_number.trim(), consent: g.consent,
          });
          onDone();
        } catch (err) {
          setError(getErrorMessage(err, "Could not save your guarantor"));
        }
      }}
    >
      {current && (
        <p className="text-muted-foreground text-xs">
          To correct the details of the same person, enter their ID number again. A different ID number replaces your guarantor:
          the old one stays on file, and you upload the new guarantor&apos;s letter and ID.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        {field("full_name", "Full name · ሙሉ ስም", { required: true })}
        {field("phone", "Mobile phone · ስልክ", { required: true, placeholder: "09XXXXXXXX", tel: true, max: 20 })}
        {field("relationship", "How they know you · ዝምድና", { required: true, placeholder: "Former employer, uncle, neighbour", max: 80 })}
        {field("id_number", "National ID or Fayda number", { required: true, max: 40, hint: "Kept encrypted. Only the last 4 digits are shown." })}
        {field("sub_city", "Sub-city or town · ክፍለ ከተማ", { required: true, max: 80 })}
        {field("woreda", "Woreda · ወረዳ", { max: 40 })}
        {field("address", "House number or landmark", { max: 200 })}
        {field("occupation", "Occupation · ሥራ", { required: true, placeholder: "Teacher, accountant, business owner" })}
        {field("employer", "Employer", { max: 160, hint: "Where they work, if employed." })}
      </div>
      <label htmlFor="g-consent" className="flex items-start gap-2 text-xs">
        <input id="g-consent" type="checkbox" className="mt-0.5 size-4 shrink-0" checked={g.consent} aria-required="true"
          onChange={(e) => set({ consent: e.target.checked })} />
        <span>
          My guarantor agreed to be my guarantor and that I share their name, phone, address and ID number with Compliance Navigator,
          and that staff will phone them. <span className="text-destructive">*</span>
        </span>
      </label>
      {error && <p className="text-destructive text-xs" role="alert">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={isPending} disabled={isPending}>Save guarantor</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone} disabled={isPending}>Cancel</Button>
      </div>
    </form>
  );
}

const GUARANTOR_STATUS: Record<VettingGuarantor["status"], string> = {
  pending: "staff will phone them",
  confirmed: "confirmed by staff on the phone",
  failed: "could not confirm",
  superseded: "replaced",
};

function GuarantorBlock({ item, vetting }: { item: VettingItem; vetting: Vetting }) {
  const [editing, setEditing] = useState(false);
  const g = item.guarantor;
  return (
    <div className="mt-2 space-y-2">
      {item.help && <p className="text-muted-foreground text-xs">{item.help}</p>}
      {g && (
        <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
          <div><dt className="text-muted-foreground inline">Name: </dt><dd className="inline">{g.full_name}</dd></div>
          <div><dt className="text-muted-foreground inline">Phone: </dt><dd className="inline">{g.phone}</dd></div>
          <div><dt className="text-muted-foreground inline">Relationship: </dt><dd className="inline">{g.relationship}</dd></div>
          <div><dt className="text-muted-foreground inline">ID: </dt><dd className="inline">ending {g.id_last4}</dd></div>
          <div className="sm:col-span-2">
            <dt className="text-muted-foreground inline">Status: </dt>
            <dd className={cn("inline", g.status === "failed" && "text-destructive")}>{GUARANTOR_STATUS[g.status]}{g.status === "failed" && g.note ? `: ${g.note}` : ""}</dd>
          </div>
        </dl>
      )}
      {editing ? (
        <GuarantorForm current={g} onDone={() => setEditing(false)} />
      ) : (
        <Button size="sm" variant={g ? "outline" : "default"} onClick={() => setEditing(true)}>
          {g ? "Change guarantor details" : "Add your guarantor"}
        </Button>
      )}
      {g && !!item.documents?.length && (
        <div>
          <p className="mt-2 text-xs font-medium">Your guarantor&apos;s papers</p>
          <ul className="border-border mt-1 rounded-md border px-3">
            {item.documents.map((d) => <ItemRow key={d.key} item={d} vetting={vetting} />)}
          </ul>
        </div>
      )}
    </div>
  );
}

function ItemRow({ item, vetting }: { item: VettingItem; vetting: Vetting }) {
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const doc = item.waiting ?? item.current;
  return (
    <li className="border-border border-t py-3 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {item.label} <span className="text-muted-foreground font-normal">· {item.label_am}</span>
            {!item.required && <span className="text-muted-foreground text-xs font-normal"> (optional)</span>}
          </p>
          {item.message && (
            <p className={cn("mt-0.5 text-xs", ["rejected", "expired", "below_minimum"].includes(item.status) ? "text-destructive" : "text-muted-foreground")}>
              {item.message}
            </p>
          )}
          {item.current && (
            <p className="text-muted-foreground mt-0.5 text-xs">
              Verified {formatDate(item.current.reviewed_at)}
              {item.current.valid_until && <> · counts until {formatDate(item.current.valid_until)}</>}
              {item.current.level_label && <> · {item.current.level_label}</>}
            </p>
          )}
          {item.waiting && item.current && item.waiting.status === "pending" && (
            <p className="text-muted-foreground mt-0.5 text-xs">A newer copy is waiting for staff.</p>
          )}
        </div>
        <VettingStatusBadge status={item.status} />
      </div>
      {item.type === "document" && !open && (
        <div className="mt-2">
          <Button size="sm" variant={["missing", "rejected", "expired", "below_minimum"].includes(item.status) ? "default" : "outline"} onClick={() => { setOpen(true); setSaved(null); }}>
            {doc ? "Upload a new copy" : "Upload"}
          </Button>
        </div>
      )}
      {item.type === "document" && open && (
        <>
          {item.help && <p className="text-muted-foreground mt-2 text-xs">{item.help}</p>}
          <UploadForm item={item} vetting={vetting} onDone={() => { setOpen(false); setSaved("Uploaded. Staff will check it."); }} />
        </>
      )}
      {item.type === "references" && (
        <>
          {!!item.references?.length && (
            <ul className="mt-2 space-y-1 text-xs">
              {item.references.map((r) => (
                <li key={r.id} className="flex flex-wrap gap-2">
                  <span>{r.name} · {r.relationship} · {r.phone}</span>
                  <span className="text-muted-foreground">({r.status === "confirmed" ? "confirmed by staff" : r.status === "failed" ? "could not confirm" : "not called yet"})</span>
                </li>
              ))}
            </ul>
          )}
          {open ? (
            <ReferencesForm refs={item.references ?? []} onDone={() => setOpen(false)} />
          ) : (
            <Button className="mt-2" size="sm" variant="outline" onClick={() => setOpen(true)}>
              {item.references?.length ? "Change references" : "Add references"}
            </Button>
          )}
        </>
      )}
      {item.type === "guarantor" && <GuarantorBlock item={item} vetting={vetting} />}
      {/* Once the list reloads, the item's own message says the same thing */}
      {saved && saved !== item.message && <p className="text-primary mt-2 text-xs" role="status">{saved}</p>}
    </li>
  );
}

function History() {
  const [page, setPage] = useState(0);
  const { data, isLoading, isError, error, refetch } = useMyVettingDocuments(page);
  const result = data?.payload;
  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={error?.message ?? "Could not load"} onRetry={() => refetch()} />;
  if (!result?.items.length) return <p className="text-muted-foreground text-xs">Nothing uploaded yet.</p>;
  return (
    <>
      <ul className="divide-border divide-y text-xs">
        {result.items.map((d) => (
          <li key={d.id} className="flex flex-wrap justify-between gap-2 py-2">
            <span className="min-w-0">
              {d.label}{d.reference_no ? ` · ${d.reference_no}` : ""} · uploaded {formatDate(d.uploaded_at)}
              {d.review_note && d.status === "rejected" && <span className="text-destructive block">Reason: {d.review_note}</span>}
            </span>
            <span className="text-muted-foreground">{d.status === "superseded" ? "replaced" : d.status}</span>
          </li>
        ))}
      </ul>
      <Pager className="mt-3" page={page} pageSize={VETTING_HISTORY_PAGE_SIZE} total={result.total} onPage={setPage} />
    </>
  );
}

/** The provider's own requirements, with a status per item and upload or replace for each document. */
export function VettingChecklist({ vetting }: { vetting: Vetting }) {
  const [showHistory, setShowHistory] = useState(false);
  const done = vetting.items.filter((i) => i.required && (i.status === "verified" || i.status === "expiring")).length;
  const required = vetting.items.filter((i) => i.required).length;
  return (
    <div className="space-y-4">
      <div className={cn("rounded-md border p-3 text-sm", vetting.complete ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-amber-300 bg-amber-50 text-amber-900")} role="status">
        {vetting.complete
          ? "Everything we need is verified. Keep your police clearance current to stay listed."
          : `${done} of ${required} requirements verified. Staff approve your listing once every required item is verified.`}
      </div>
      <p className="text-muted-foreground text-xs">
        Clients trust a Guday Geday with their papers and money, so every agent is checked by a person. Your documents are
        private: only marketplace staff can open them, and every look at a police clearance or your guarantor&apos;s papers is
        recorded. Everything must stay verified and in date: if something runs out, you are hidden from clients until it is fixed.
      </p>
      <ul>
        {vetting.items.map((item) => <ItemRow key={item.key} item={item} vetting={vetting} />)}
      </ul>
      <div>
        <button type="button" className="text-primary text-xs underline" aria-expanded={showHistory} onClick={() => setShowHistory(!showHistory)}>
          {showHistory ? "Hide" : "Show"} everything you uploaded
        </button>
        {showHistory && <div className="mt-2"><History /></div>}
      </div>
    </div>
  );
}
