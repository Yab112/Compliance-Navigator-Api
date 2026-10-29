"use client";

import { useState } from "react";
import { VETTING_HISTORY_PAGE_SIZE, useAdminProviderDocuments, useMarketAction } from "@cn/core/api/providers";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import type { AdminProvider, EducationLevel, Vetting, VettingDocument, VettingItem, VettingReference, VettingStatus } from "@cn/core/types/provider";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager } from "@cn/ui/pager";
import { ErrorState, Field, LoadingState, NativeSelect, formatDate, formatDateTime } from "@cn/ui/guday/shared";
import { PrivateDocument } from "@/modules/marketplace/private-document";

const STATUS: Record<VettingStatus, { label: string; tone: string }> = {
  missing: { label: "Missing", tone: "bg-muted text-foreground" },
  pending: { label: "To check", tone: "bg-amber-100 text-amber-900" },
  verified: { label: "Verified", tone: "bg-emerald-100 text-emerald-900" },
  expiring: { label: "Verified, expires soon", tone: "bg-amber-100 text-amber-900" },
  rejected: { label: "Rejected", tone: "bg-red-100 text-red-900" },
  expired: { label: "Expired", tone: "bg-red-100 text-red-900" },
  below_minimum: { label: "Below minimum", tone: "bg-red-100 text-red-900" },
};

function Badge({ status }: { status: VettingStatus }) {
  return <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap", STATUS[status].tone)}>{STATUS[status].label}</span>;
}

const daysSince = (d?: string | null) => (d ? Math.floor((Date.now() - new Date(d).getTime()) / 86_400_000) : null);

function DocDetails({ doc }: { doc: VettingDocument }) {
  const age = daysSince(doc.issued_on);
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] sm:grid-cols-3">
      <div><dt className="text-muted-foreground">Issued</dt><dd>{formatDate(doc.issued_on)}{age !== null ? ` (${age} days ago)` : ""}</dd></div>
      <div><dt className="text-muted-foreground">Counts until</dt><dd>{formatDate(doc.valid_until)}{doc.days_left != null ? ` (${doc.days_left} days)` : ""}</dd></div>
      <div><dt className="text-muted-foreground">Number</dt><dd className="font-mono break-all">{doc.reference_no ?? "-"}</dd></div>
      {doc.level_label && <div><dt className="text-muted-foreground">Level</dt><dd>{doc.level_label}</dd></div>}
      {doc.issuer && <div><dt className="text-muted-foreground">Issued by</dt><dd>{doc.issuer}</dd></div>}
      <div><dt className="text-muted-foreground">Uploaded</dt><dd>{formatDateTime(doc.uploaded_at)}</dd></div>
      {doc.reviewed_by && <div><dt className="text-muted-foreground">Checked by</dt><dd className="break-all">{doc.reviewed_by}, {formatDate(doc.reviewed_at)}</dd></div>}
      {doc.review_note && <div className="col-span-full"><dt className="text-muted-foreground">Staff note</dt><dd>{doc.review_note}</dd></div>}
    </dl>
  );
}

type Decision = { decision: "verified" | "rejected"; note?: string; issued_on?: string; expires_on?: string; reference_no?: string; level?: EducationLevel };

function ReviewForm({ p, item, doc, levels }: { p: AdminProvider; item: VettingItem; doc: VettingDocument; levels: Vetting["education_levels"] }) {
  const { run, isPending } = useMarketAction<Decision>();
  const [issued, setIssued] = useState(doc.issued_on ?? "");
  const [expires, setExpires] = useState(doc.expires_on ?? "");
  const [ref, setRef] = useState(doc.reference_no ?? "");
  const [level, setLevel] = useState<string>(doc.level ?? "");
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const id = (f: string) => `rv-${doc.id}-${f}`;
  const send = async (body: Decision) => {
    setError(null);
    try {
      await run(apiPaths.admin.marketProviderDocumentReview(p.id, doc.id), MTD.POST, body);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  const canVerify = doc.status === "pending";
  return (
    <div className="bg-secondary/40 mt-2 space-y-2 rounded-md p-3">
      {canVerify && (
        <>
          <p className="text-[11px]">Correct these to what is printed on the document, then verify.</p>
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="Issue date" htmlFor={id("issued")} required={!!item.needs?.issued_on}>
              <Input id={id("issued")} type="date" value={issued} onChange={(e) => setIssued(e.target.value)} />
            </Field>
            {(item.needs?.expires_on || item.kind === "trade_licence") && (
              <Field label="Valid until" htmlFor={id("expires")} required={!!item.needs?.expires_on}>
                <Input id={id("expires")} type="date" value={expires} onChange={(e) => setExpires(e.target.value)} />
              </Field>
            )}
            <Field label={item.reference_label ?? "Number"} htmlFor={id("ref")} required={!!item.needs?.reference_no}>
              <Input id={id("ref")} value={ref} maxLength={60} onChange={(e) => setRef(e.target.value)} />
            </Field>
            {item.needs?.level && (
              <Field label="Level on the certificate" htmlFor={id("level")} required hint={item.min_level_label ? `Minimum: ${item.min_level_label}` : undefined}>
                <NativeSelect id={id("level")} value={level} onChange={(e) => setLevel(e.target.value)}>
                  <option value="">Choose…</option>
                  {levels.map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}
                </NativeSelect>
              </Field>
            )}
          </div>
        </>
      )}
      {rejecting ? (
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); void send({ decision: "rejected", note: reason.trim() }); }}>
          <Field label="Why is it rejected? The provider sees this." htmlFor={id("reason")} required>
            <Input id={id("reason")} value={reason} maxLength={500} onChange={(e) => setReason(e.target.value)} autoFocus />
          </Field>
          <div className="flex gap-2">
            <Button type="submit" size="sm" variant="destructive" loading={isPending} disabled={isPending || reason.trim().length < 5}>Reject</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setRejecting(false)}>Cancel</Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-wrap gap-2">
          {canVerify && (
            <Button size="sm" loading={isPending} disabled={isPending}
              onClick={() => send({ decision: "verified", issued_on: issued || undefined, expires_on: expires || undefined, reference_no: ref.trim() || undefined, level: (level || undefined) as EducationLevel | undefined })}>
              Verify
            </Button>
          )}
          <Button size="sm" variant={canVerify ? "ghost" : "outline"} onClick={() => setRejecting(true)}>
            {canVerify ? "Reject" : "Withdraw verification"}
          </Button>
        </div>
      )}
      {error && <p className="text-destructive text-xs" role="alert">{error}</p>}
    </div>
  );
}

function DocBlock({ p, item, doc, title, levels }: { p: AdminProvider; item: VettingItem; doc: VettingDocument; title: string; levels: Vetting["education_levels"] }) {
  const [reviewing, setReviewing] = useState(doc.status === "pending");
  return (
    <div className="border-border mt-2 border-l-2 pl-3">
      <p className="text-xs font-medium">{title}</p>
      <div className="mt-1">
        <PrivateDocument src={apiPaths.admin.marketProviderDocumentFile(p.id, doc.id)} label={item.label} revealOnClick={!!item.sensitive} />
      </div>
      <div className="mt-2"><DocDetails doc={doc} /></div>
      {reviewing ? (
        <ReviewForm p={p} item={item} doc={doc} levels={levels} />
      ) : (
        doc.status === "verified" && (
          <button type="button" className="text-muted-foreground mt-1 text-[11px] underline" onClick={() => setReviewing(true)}>
            Found a problem with this document?
          </button>
        )
      )}
    </div>
  );
}

function ReferenceRow({ p, r }: { p: AdminProvider; r: VettingReference }) {
  const { run, isPending } = useMarketAction<{ decision: "confirmed" | "failed"; note?: string }>();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const decide = async (decision: "confirmed" | "failed") => {
    setError(null);
    try {
      await run(apiPaths.admin.marketProviderReference(p.id, r.id), MTD.POST, { decision, note: note.trim() || undefined });
      setNote("");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  return (
    <li className="border-border border-t py-2 text-xs">
      <p>
        <strong>{r.name}</strong> · {r.relationship} · <a className="text-primary underline" href={`tel:${r.phone}`}>{r.phone}</a>{" "}
        <span className="text-muted-foreground">({r.status}{r.checked_by ? ` by ${r.checked_by}` : ""})</span>
      </p>
      {r.note && <p className="text-muted-foreground">Call note: {r.note}</p>}
      {r.status === "pending" && (
        <div className="mt-1 flex flex-wrap items-end gap-2">
          <Input aria-label={`Call note for ${r.name}`} className="max-w-xs" placeholder="What did they say?" value={note} onChange={(e) => setNote(e.target.value)} />
          <Button size="sm" variant="outline" loading={isPending} disabled={isPending} onClick={() => decide("confirmed")}>Confirmed</Button>
          <Button size="sm" variant="ghost" disabled={isPending || !note.trim()} onClick={() => decide("failed")}>Could not confirm</Button>
        </div>
      )}
      {error && <p className="text-destructive" role="alert">{error}</p>}
    </li>
  );
}

function History({ p }: { p: AdminProvider }) {
  const [page, setPage] = useState(0);
  const [size, setSize] = useState(VETTING_HISTORY_PAGE_SIZE);
  const { data, isLoading, isError, error, refetch } = useAdminProviderDocuments(p.id, page, true, size);
  const result = data?.payload;
  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={error?.message ?? "Could not load"} onRetry={() => refetch()} />;
  if (!result?.items.length) return <p className="text-muted-foreground text-xs">Nothing uploaded.</p>;
  return (
    <>
      <ul className="divide-border divide-y text-xs">
        {result.items.map((d) => (
          <li key={d.id} className="flex flex-wrap justify-between gap-2 py-1.5">
            <span className="min-w-0">{d.label}{d.reference_no ? ` · ${d.reference_no}` : ""} · {formatDate(d.uploaded_at)}{d.review_note ? ` · ${d.review_note}` : ""}</span>
            <span className="text-muted-foreground">{d.status}</span>
          </li>
        ))}
      </ul>
      <Pager
        className="mt-2"
        page={page}
        pageSize={size}
        total={result.total}
        onPage={setPage}
        onPageSize={(n) => { setSize(n); setPage(0); }}
      />
    </>
  );
}

/** Every requirement with its proof, and per-document Verify / Reject. Approve and Renew stay blocked until it is complete. */
export function VettingPanel({ p }: { p: AdminProvider }) {
  const [history, setHistory] = useState(false);
  const v = p.vetting;
  if (!v) return null;
  return (
    <section className="border-border bg-card border p-4" aria-labelledby="vetting-title">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="vetting-title" className="text-sm font-semibold">Vetting · ማጣሪያ</h2>
        <span className={cn("rounded px-2 py-0.5 text-xs font-medium", v.complete ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900")}>
          {v.complete ? "Complete" : "Not complete"}
        </span>
      </div>
      {v.blocker && <p className="text-muted-foreground mb-3 text-xs">{v.blocker} Approve and Renew are blocked until then.</p>}
      <ul className="space-y-1">
        {v.items.map((item) => (
          <li key={item.key} className="border-border border-t pt-3 pb-1 first:border-t-0 first:pt-0">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm font-medium">
                {item.label} <span className="text-muted-foreground font-normal">· {item.label_am}</span>
                {!item.required && <span className="text-muted-foreground text-xs font-normal"> (optional)</span>}
              </p>
              <Badge status={item.status} />
            </div>
            {item.message && <p className="text-muted-foreground text-xs">{item.message}</p>}
            {item.how_to_verify && (
              <details className="mt-1 text-xs">
                <summary className="text-primary cursor-pointer">How to verify</summary>
                <p className="text-muted-foreground mt-1">{item.how_to_verify}</p>
              </details>
            )}
            {item.sensitive && (
              <p className="mt-1 text-[11px] text-amber-800">Criminal record data. Each time you open it, your name and the time go into the audit log.</p>
            )}
            {item.waiting && <DocBlock p={p} item={item} doc={item.waiting} title={item.waiting.status === "pending" ? "Waiting for your check" : "Rejected copy"} levels={v.education_levels} />}
            {item.current && <DocBlock p={p} item={item} doc={item.current} title="Verified copy in force" levels={v.education_levels} />}
            {item.type === "references" && (
              item.references?.length ? <ul className="mt-1">{item.references.map((r) => <ReferenceRow key={r.id} p={p} r={r} />)}</ul>
                : <p className="text-muted-foreground text-xs">No references given.</p>
            )}
          </li>
        ))}
      </ul>
      <div className="border-border mt-3 border-t pt-3">
        <button type="button" className="text-primary text-xs underline" aria-expanded={history} onClick={() => setHistory(!history)}>
          {history ? "Hide" : "Show"} every upload, including replaced copies
        </button>
        {history && <div className="mt-2"><History p={p} /></div>}
      </div>
    </section>
  );
}

const FIELD_LABELS: Record<string, string> = {
  display_name: "Display name",
  legal_name: "Legal name",
  tin: "TIN",
  trade_license_no: "Trade licence number",
  vat_registered: "VAT registered",
  vat_number: "VAT number",
};
const show = (v: unknown) => (v === true ? "Yes" : v === false ? "No" : v == null || v === "" ? "(empty)" : String(v));

/** An approved provider's change to their name, registration or VAT, held until staff check it. */
export function PendingChangePanel({ p }: { p: AdminProvider }) {
  const { run, isPending } = useMarketAction<{ decision: "approve" | "reject"; note: string }>();
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const c = p.pending_change;
  if (!c) return null;
  const decide = async (decision: "approve" | "reject") => {
    setError(null);
    try {
      await run(apiPaths.admin.marketProviderChange(p.id, c.id), MTD.POST, { decision, note: note.trim() });
      setNote("");
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  return (
    <section className="border border-amber-400 bg-amber-50 p-4 text-amber-950" aria-labelledby="change-title">
      <h2 id="change-title" className="text-sm font-semibold">Change waiting for approval</h2>
      <p className="mt-1 text-xs">Requested by {c.requested_by} on {formatDateTime(c.requested_at)}. The old values stay live until you approve.</p>
      <table className="mt-2 w-full text-xs">
        <thead><tr className="text-left"><th className="py-1 pr-2 font-medium">Field</th><th className="pr-2 font-medium">Now</th><th className="font-medium">Asked for</th></tr></thead>
        <tbody>
          {Object.entries(c.changes).map(([k, v]) => (
            <tr key={k} className="border-t border-amber-200 align-top">
              <td className="py-1 pr-2">{FIELD_LABELS[k] ?? k}</td>
              <td className="pr-2 break-all">{show(c.old_values[k])}</td>
              <td className="font-medium break-all">{show(v)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px]">
        Check the proof before approving: Fayda name for a name change, the TIN or VAT registration certificate from the Ministry of Revenues for tax
        details. VAT registration adds 15% to what clients pay.
      </p>
      <label htmlFor="change-note" className="mt-2 block text-xs font-medium">What you checked, or why you refuse (the provider sees a refusal)</label>
      <textarea id="change-note" rows={2} className="border-input bg-background mt-1 w-full rounded-md border p-2 text-sm" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="mt-2 flex gap-2">
        <Button size="sm" loading={isPending} disabled={isPending || note.trim().length < 10} onClick={() => decide("approve")}>Approve change</Button>
        <Button size="sm" variant="destructive" disabled={isPending || note.trim().length < 5} onClick={() => decide("reject")}>Refuse</Button>
      </div>
      {error && <p className="text-destructive mt-2 text-xs" role="alert">{error}</p>}
    </section>
  );
}
