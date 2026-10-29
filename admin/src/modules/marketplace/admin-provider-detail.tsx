"use client";

import { siteUrl } from "@cn/core/config/env";
import Link from "next/link";
import { useState } from "react";
import { useAdminProvider, useMarketAction } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { EventLog } from "@cn/ui/guday/event-log";
import {
  AgentStatusBadge,
  ErrorState,
  IdVerifiedBadge,
  InfoRow,
  LoadingState,
  formatDate,
  languageLabel,
} from "@cn/ui/guday/shared";
import { HireStatusBadge, ScoreBreakdown, SpecialtyChips, Stars } from "@cn/ui/marketplace/trust";
import { TYPE_META, areaLabel, formatFee } from "@cn/ui/marketplace/constants";
import type { AdminProvider, ProviderAdminAction, Review } from "@cn/core/types/provider";
import { PrivateDocument } from "@/modules/marketplace/private-document";
import { PendingChangePanel, ReadinessPanel, VettingPanel } from "@/modules/marketplace/admin-vetting-panel";
import { ProviderAvatar, verifiedLevel } from "@cn/ui/marketplace/provider-avatar";

type ActionDef = {
  action: ProviderAdminAction;
  label: string;
  tone?: "destructive";
  /** What staff must write, and how much */
  prompt: string;
  minNote: number;
};

// Approving and renewing are only as good as the checks behind them, so both ask what was checked;
// the note goes into the audit log as the proof.
const CHECKED = "What did you check? For example: met in person, clearance number confirmed with the police, references called. Kept in the audit log.";
const REASON = "Reason. The provider sees this.";
const ACTIONS: Record<string, ActionDef[]> = {
  pending: [
    { action: "approve", label: "Approve and list", prompt: CHECKED, minNote: 10 },
    { action: "reject", label: "Reject", tone: "destructive", prompt: REASON, minNote: 3 },
  ],
  rejected: [{ action: "approve", label: "Approve after all", prompt: CHECKED, minNote: 10 }],
  approved: [
    { action: "renew", label: "Renew listing", prompt: CHECKED, minNote: 10 },
    { action: "suspend", label: "Suspend", tone: "destructive", prompt: REASON, minNote: 3 },
  ],
  suspended: [
    { action: "reinstate", label: "Reinstate", prompt: "Why is it safe to reinstate? Optional, kept in the audit log.", minNote: 0 },
    { action: "renew", label: "Renew listing", prompt: CHECKED, minNote: 10 },
  ],
};

function Panel({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border-border bg-card border p-4", className)}>
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function ReviewModeration({ review }: { review: Review }) {
  const { run, isPending } = useMarketAction<{ hidden: boolean; reason?: string }>();
  const [reason, setReason] = useState("");
  const [open, setOpen] = useState(false);
  return (
    <li className={cn("border-border border-t py-3 text-xs", review.hidden && "opacity-70")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2"><Stars value={review.rating} /> {review.job_title} · {review.client_name}</span>
        <span className="text-muted-foreground">{formatDate(review.created_at)}</span>
      </div>
      {review.comment && <p className="mt-1">{review.comment}</p>}
      {review.hidden ? (
        <p className="mt-1 text-amber-800">
          Hidden by {review.hidden_by}: {review.hidden_reason}{" "}
          <button type="button" className="text-primary underline" disabled={isPending}
            onClick={() => run(apiPaths.admin.marketModerate(review.id), MTD.POST, { hidden: false })}>
            Restore
          </button>
        </p>
      ) : open ? (
        <div className="mt-2 flex gap-2">
          <Input placeholder="Reason (abuse, personal data, not about the job...)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <Button size="sm" variant="destructive" disabled={reason.trim().length < 3} loading={isPending}
            onClick={() => run(apiPaths.admin.marketModerate(review.id), MTD.POST, { hidden: true, reason: reason.trim() })}>
            Hide
          </Button>
        </div>
      ) : (
        <button type="button" className="text-muted-foreground mt-1 underline" onClick={() => setOpen(true)}>Hide this review</button>
      )}
    </li>
  );
}

function Actions({ p }: { p: AdminProvider }) {
  const { run, isPending } = useMarketAction<{ action?: string; decision?: string; note?: string }>();
  const [open, setOpen] = useState<ActionDef | "license_rejected" | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const call = async (url: string, body: { action?: string; decision?: string }, success: string) => {
    setError(null);
    try {
      await run(url, MTD.POST, { ...body, note: note.trim() || undefined });
      setNote("");
      setOpen(null);
      setDone(success);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  const renewBlocked = p.renewal?.blocker;
  // The server refuses these too; hiding them saves staff a pointless round trip
  const vettingBlocked = p.vetting && !p.vetting.complete ? p.vetting.blocker : null;
  const actions = (ACTIONS[p.status] ?? []).filter(
    (a) => !(a.action === "renew" && renewBlocked) && !(a.action === "approve" && vettingBlocked),
  );

  return (
    <Panel title="Decision">
      {/* The blocker already names the expiry date when renewal is not open yet */}
      <p className="text-muted-foreground text-xs">
        {renewBlocked ?? (
          <>
            Listing valid until <strong className="text-foreground">{formatDate(p.license_expires_at)}</strong>
            {p.renewal?.opens_on ? ". Renewal is open." : "."}
          </>
        )}
      </p>
      {vettingBlocked && (p.status === "pending" || p.status === "rejected") && (
        <p className="mt-2 text-xs text-amber-800">Approval opens once every vetting requirement is verified (see Vetting).</p>
      )}
      {!open && (
        <div className="mt-3 flex flex-wrap gap-2">
          {actions.map((a) => (
            <Button key={a.action} size="sm" variant={a.tone ?? "default"} onClick={() => { setOpen(a); setDone(null); setError(null); }}>
              {a.label}
            </Button>
          ))}
        </div>
      )}
      {open && open !== "license_rejected" && (
        <form
          className="bg-secondary/50 mt-3 space-y-2 rounded-md p-3"
          onSubmit={(e) => {
            e.preventDefault();
            void call(apiPaths.admin.marketProviderReview(p.id), { action: open.action }, `${open.label}: done.`);
          }}
        >
          <label htmlFor="decision-note" className="block text-xs font-medium">{open.prompt}</label>
          <textarea id="decision-note" rows={3} className="border-input bg-background w-full rounded-md border p-2 text-sm"
            value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
          <div className="flex gap-2">
            {/* Disabled while saving, so a double click can't apply the action twice */}
            <Button type="submit" size="sm" variant={open.tone ?? "default"} loading={isPending} disabled={isPending || note.trim().length < open.minNote}>
              {open.label}
            </Button>
            <Button type="button" size="sm" variant="ghost" disabled={isPending} onClick={() => { setOpen(null); setNote(""); }}>Cancel</Button>
          </div>
        </form>
      )}
      {done && <p className="text-primary mt-2 text-xs" role="status">{done}</p>}
      {p.external_license_no && (
        <div className="border-border mt-4 border-t pt-3">
          <p className="text-xs">
            Sector licence: <strong>{p.external_license_type ?? "Licence"}</strong> no. <span className="font-mono">{p.external_license_no}</span>{" "}
            <span className="text-muted-foreground">({p.external_license_status}{p.external_license_verified_by ? ` by ${p.external_license_verified_by}` : ""})</span>
          </p>
          <p className="text-muted-foreground mt-1 text-[11px]">Confirm the number with the issuing office before verifying. A verified licence adds 4 points to the trust score.</p>
          {open === "license_rejected" ? (
            <form className="mt-2 space-y-2" onSubmit={(e) => { e.preventDefault(); void call(apiPaths.admin.marketProviderLicense(p.id), { decision: "rejected" }, "Licence marked not valid."); }}>
              <label htmlFor="license-note" className="block text-xs font-medium">{REASON}</label>
              <Input id="license-note" value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
              <div className="flex gap-2">
                <Button type="submit" size="sm" variant="destructive" loading={isPending} disabled={isPending || note.trim().length < 3}>Licence not valid</Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => { setOpen(null); setNote(""); }}>Cancel</Button>
              </div>
            </form>
          ) : (
            <div className="mt-2 flex gap-2">
              <Button size="sm" variant="outline" loading={isPending} disabled={isPending || p.external_license_status === "verified"}
                onClick={() => call(apiPaths.admin.marketProviderLicense(p.id), { decision: "verified" }, "Licence verified.")}>
                Mark licence verified
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setOpen("license_rejected"); setDone(null); }}>Licence not valid</Button>
            </div>
          )}
        </div>
      )}
      {error && <p className="text-destructive mt-2 text-xs" role="alert">{error}</p>}
    </Panel>
  );
}

/** Proof of identity: what Fayda returned, not a photo of a card. */
function IdentityPanel({ p }: { p: AdminProvider }) {
  const id = p.identity;
  if (!id) {
    return (
      <Panel title="National ID (Fayda)">
        <p className="text-destructive text-xs font-medium">Not verified with Fayda.</p>
        <p className="text-muted-foreground mt-1 text-xs">
          Ask the provider to verify from their account. Fayda confirms the name, birth date and phone straight from the national ID
          system, so no photo of the card is needed.
        </p>
        {p.national_id && <p className="mt-2 text-xs">ID number they typed: <span className="font-mono">{p.national_id}</span> (not confirmed)</p>}
        {p.id_document_url && (
          <div className="mt-2">
            <p className="text-muted-foreground mb-1 text-[11px]">Uploaded copy from an older sign-up:</p>
            <PrivateDocument fileKey={p.id_document_url} label="ID copy" />
          </div>
        )}
      </Panel>
    );
  }
  return (
    <Panel title="National ID (Fayda)">
      <p className="text-primary text-xs font-medium">
        Verified {formatDate(id.verified_at)} through {id.method === "fayda_sandbox" ? "the Fayda sandbox (test system, not a real ID)" : "Fayda"}
      </p>
      <dl className="mt-3 grid gap-3 sm:grid-cols-2">
        <InfoRow label="Name on the ID">{id.verified_name}</InfoRow>
        <InfoRow label="ID number">{id.id_last4 ? `•••• ${id.id_last4}` : "-"}{id.id_type ? ` (${id.id_type})` : ""}</InfoRow>
        <InfoRow label="Birth date">{id.birthdate}</InfoRow>
        <InfoRow label="Gender">{id.gender}</InfoRow>
        <InfoRow label="Phone on the ID">{id.phone}</InfoRow>
        <InfoRow label="Phone on the profile">{p.phone}</InfoRow>
      </dl>
      <p className="text-muted-foreground mt-3 text-[11px]">
        These details come from the national ID system. The full ID number is never stored, only the last four digits.
      </p>
    </Panel>
  );
}

export function AdminProviderDetail({ id }: { id: string }) {
  const { data, isLoading, isError, error, refetch } = useAdminProvider(id);
  const p = data?.payload.provider;
  if (isLoading) return <AdminPage title="Provider"><LoadingState /></AdminPage>;
  if (isError || !p) return <AdminPage title="Provider"><ErrorState message={error?.message ?? "Not found"} onRetry={() => refetch()} /></AdminPage>;

  return (
    <AdminPage
      title={p.display_name}
      description={`${TYPE_META[p.provider_type].label} · ${p.entity_type === "company" ? "Company" : "Individual"}${p.registration_no ? ` · ${p.registration_no}` : ""}`}
      actions={
        <>
          <Link href="/marketplace"><Button size="sm" variant="outline">All providers</Button></Link>
          {p.status === "approved" && <a href={siteUrl(`/providers/${p.slug}`)} target="_blank" rel="noreferrer"><Button size="sm" variant="outline">Public profile</Button></a>}
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Panel title="Summary">
            <div className="flex gap-4">
              <ProviderAvatar name={p.display_name} photoUrl={p.photo_url} entity={p.entity_type} verified={p.status === "approved" ? verifiedLevel(p) : null} size="lg" />
              <div className="space-y-2 text-xs">
                <div className="flex flex-wrap gap-2">
                  <AgentStatusBadge status={p.status} />
                  <IdVerifiedBadge verified={p.id_verified} method={p.id_verification_method} />
                  {p.is_sample && <span className="rounded bg-amber-100 px-1.5 text-amber-900">sample data</span>}
                </div>
                {p.headline && <p className="text-sm">{p.headline}</p>}
                {p.review_note && <p className="text-muted-foreground">Last staff note: {p.review_note}</p>}
              </div>
            </div>
            {p.name_mismatch && (
              <p className="mt-3 border border-amber-400 bg-amber-50 p-2 text-xs text-amber-900">
                The name on the profile ({p.display_name}) differs from the Fayda name ({p.verified_name}). Check before approving.
              </p>
            )}
            <dl className="mt-4 grid gap-3 sm:grid-cols-3">
              <InfoRow label="Phone">{p.phone}</InfoRow>
              <InfoRow label="Email">{p.email}</InfoRow>
              <InfoRow label="TIN">{p.tin}</InfoRow>
              {p.entity_type === "company" && (
                <>
                  <InfoRow label="Legal name">{p.legal_name}</InfoRow>
                  <InfoRow label="Trade licence">{p.trade_license_no}</InfoRow>
                  <InfoRow label="Representative">{p.representative_title}</InfoRow>
                </>
              )}
              <InfoRow label="Areas">{p.service_areas.map(areaLabel).join(", ")}</InfoRow>
              <InfoRow label="Languages">{p.languages.map(languageLabel).join(", ")}</InfoRow>
              <InfoRow label="Pricing">{formatFee(p)}</InfoRow>
              <InfoRow label="Experience">{p.experience_years} years</InfoRow>
              <InfoRow label="Listing valid until">{formatDate(p.license_expires_at)}</InfoRow>
              <InfoRow label="Accepting work">{p.accepting_work ? "Yes" : "Paused"}</InfoRow>
            </dl>
            <div className="mt-3"><SpecialtyChips keys={p.specialties} /></div>
            {p.services && p.services.length > 0 && (
              <p className="mt-2 text-xs">Services: {p.services.map((s) => s.name).join(", ")}</p>
            )}
            {p.bio && <p className="text-muted-foreground mt-3 text-xs whitespace-pre-line">{p.bio}</p>}
          </Panel>

          <ReadinessPanel p={p} />
          <PendingChangePanel p={p} />
          <VettingPanel p={p} />
          <div className="grid gap-4 md:grid-cols-2">
            <IdentityPanel p={p} />
            {p.license_document_url && (
              <Panel title="Trade licence copy (older sign-up)"><PrivateDocument fileKey={p.license_document_url} label="Licence copy" /></Panel>
            )}
          </div>

          <Panel title={`Reviews (${p.reviews?.total ?? 0}, including hidden)`}>
            {p.reviews?.items.length ? <ul>{p.reviews.items.map((r) => <ReviewModeration key={r.id} review={r} />)}</ul> : <p className="text-muted-foreground text-xs">No reviews.</p>}
          </Panel>

          <Panel title="Recent hires">
            {p.engagements?.length ? (
              <ul className="divide-border divide-y text-xs">
                {p.engagements.map((e) => (
                  <li key={e.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <span>{e.title} · {e.client_name} · {formatDate(e.created_at)}</span>
                    <span className="flex items-center gap-2">
                      {e.disputed && <span className="text-destructive">complaint {e.dispute_status}</span>}
                      <HireStatusBadge status={e.status} />
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-xs">No hires yet.</p>
            )}
          </Panel>

          {(p.team?.length || p.agency) && (
            <Panel title={p.provider_type === "agency" ? "Team" : "Agency"}>
              {p.agency && <p className="text-xs">Member of <Link className="text-primary underline" href={`/marketplace/${p.agency.id}`}>{p.agency.display_name}</Link> ({p.agency.status})</p>}
              <ul className="space-y-1 text-xs">
                {p.team?.map((m) => (
                  <li key={m.membership_id}><Link className="text-primary underline" href={`/marketplace/${m.id}`}>{m.display_name}</Link> ({m.status})</li>
                ))}
              </ul>
            </Panel>
          )}
        </div>

        <aside className="space-y-4">
          <Actions p={p} />
          <Panel title={`Trust score ${p.trust_score}/100`}><ScoreBreakdown parts={p.score_breakdown} compact /></Panel>
          <Panel title="Audit log"><EventLog events={p.events ?? []} showActor /></Panel>
        </aside>
      </div>
    </AdminPage>
  );
}
