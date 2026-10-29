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
  Vetting,
  VettingDocKind,
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
  const [rows, setRows] = useState(
    refs.length ? refs.map((r) => ({ name: r.name, phone: r.phone, relationship: r.relationship })) : [blank, blank],
  );
  const [error, setError] = useState<string | null>(null);
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
        try {
          await run(apiPaths.providers.myReferences, MTD.PUT, { references: filled.map((r) => ({ name: r.name.trim(), phone: r.phone.trim(), relationship: r.relationship.trim() })) });
          onDone();
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
      <div className="flex gap-2">
        <Button type="submit" size="sm" loading={isPending} disabled={isPending}>Save references</Button>
        <Button type="button" size="sm" variant="ghost" onClick={onDone} disabled={isPending}>Cancel</Button>
      </div>
    </form>
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
      {saved && <p className="text-primary mt-2 text-xs" role="status">{saved}</p>}
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
        private: only marketplace staff can open them, and every look at a police clearance is recorded.
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
