"use client";

import Link from "next/link";
import { useState } from "react";
import { ADMIN_ORGS_PAGE_SIZE, useReviewSubmission, useSubmission, useSubmissions } from "@cn/core/api/organizations";
import { Button } from "@cn/ui/button";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { Textarea } from "@cn/ui/textarea";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cn } from "@cn/core/lib/utils";
import { AdminPage } from "@/modules/components/admin-page";
import { timeAgo } from "@cn/core/lib/format";
import { EmptyState, ErrorState, LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import { CompletenessMeter, OrgStatusChip, formatFee } from "@cn/ui/organizations/shared";
import { FEE_CATEGORY_LABEL, PROXY_LABEL } from "@cn/core/types/organizations";
import type { ServiceSnapshot } from "@cn/core/types/organizations";

const TABS = [
  { value: "pending", label: "Waiting for review" },
  { value: "scheduled", label: "Scheduled" },
  { value: "changes_requested", label: "Changes requested" },
  { value: "published", label: "Published" },
  { value: "all", label: "All" },
];

export function AdminSubmissions() {
  const [status, setStatus] = useState("pending");
  const [page, setPage] = useUrlPage();
  const { payload, isLoading, error, refetch } = useSubmissions(status, page);
  const items = payload?.submissions ?? [];

  return (
    <AdminPage
      title="Service submissions"
      description="New services and changes submitted by organizations. Nothing reaches the public, the paths or the knowledge graph until you publish it."
    >
      <div className="mb-4 flex flex-wrap gap-1">
        {TABS.map((t) => (
          <button
            key={t.value}
            onClick={() => {
              setStatus(t.value);
              if (page) setPage(0);
            }}
            className={cn("rounded px-3 py-1.5 text-xs", status === t.value ? "bg-primary text-primary-foreground" : "bg-muted")}
          >
            {t.label}
          </button>
        ))}
      </div>
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={getErrorMessage(error)} onRetry={() => refetch()} />
      ) : !items.length ? (
        <EmptyState title="Nothing here" />
      ) : (
        <ul className="ring-foreground/10 bg-card divide-border divide-y text-sm ring-1">
          {items.map((s) => (
            <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 p-3">
              <div>
                <p className="font-medium">
                  {s.service_name}{" "}
                  <span className="text-muted-foreground text-xs font-normal">{s.is_update ? "· update to a live service" : "· new service"}</span>
                </p>
                <p className="text-muted-foreground text-xs">
                  {s.org_name} · submitted {timeAgo(s.created_at)} by {s.submitted_by}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={s.status.replace("_", " ")} tone={s.status === "pending" ? "warning" : s.status === "published" ? "good" : "neutral"} />
                <Link href={`/submissions/${s.id}`}>
                  <Button size="sm" variant="outline">
                    Open
                  </Button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Pager page={page} pageSize={ADMIN_ORGS_PAGE_SIZE} total={payload?.total ?? 0} onPage={setPage} />
    </AdminPage>
  );
}

/** One readable line per field so the published and submitted versions line up. */
function describe(snap: ServiceSnapshot | null): Record<string, string> {
  if (!snap) return {};
  const join = (xs: string[]) => (xs.length ? xs.join("\n") : "-");
  return {
    Name: [snap.name, snap.name_am].filter(Boolean).join(" · "),
    Summary: snap.summary || "-",
    "Who can apply": snap.who_can_apply || "-",
    "How to apply": snap.delivery + (snap.online_url ? ` (${snap.online_url})` : ""),
    Fee: snap.is_free
      ? "Free"
      : (snap.fee_schedule ?? []).length
        ? join(
            snap.fee_schedule.map(
              (r) => `${FEE_CATEGORY_LABEL[r.category]}${r.speed === "urgent" ? ", urgent" : ""}: ${formatFee(r.amount_min, r.amount_max, r.currency)}${r.covers ? ` (${r.covers})` : ""}`,
            ),
          )
        : formatFee(snap.fee_amount_min, snap.fee_amount_max, snap.fee_currency) + (snap.fee_notes ? ` · ${snap.fee_notes}` : ""),
    "Payment methods": join(snap.payment_methods) + (snap.where_to_pay ? ` · ${snap.where_to_pay}` : ""),
    Branches: join((snap.branch_details ?? []).map((d) => `${d.branch_id.slice(0, 8)}: ${d.window ?? "no window"}${d.phone ? ` · ${d.phone}` : ""}`)),
    Appointment: snap.appointment_required ? [snap.appointment_how, snap.appointment_url, snap.appointment_phone].filter(Boolean).join(" · ") || "Required" : "Not needed",
    "Applying for someone": snap.proxy_allowed ? PROXY_LABEL[snap.proxy_allowed] + (snap.proxy_notes ? ` · ${snap.proxy_notes}` : "") : "-",
    Validity: snap.output_validity_months ? `${snap.output_validity_months} months${snap.late_renewal_penalty ? ` · late: ${snap.late_renewal_penalty}` : ""}` : "-",
    Contact: [snap.contact_name, snap.contact_phone, snap.contact_email].filter(Boolean).join(" · ") || "-",
    Languages: join(snap.languages ?? []),
    "Processing time": [snap.processing_time_text, snap.processing_minutes != null && `${snap.processing_minutes} min`].filter(Boolean).join(" · ") || "-",
    "Legal basis": [snap.legal_basis, snap.legal_reference_number && `No. ${snap.legal_reference_number}`].filter(Boolean).join(" ") || "-",
    Issues: join(snap.outputs.map((o) => o.name + (o.document_id ? ` [${o.document_id}]` : ""))),
    Requirements: join(
      snap.requirements.map(
        (r) =>
          `${r.name}${r.required === "conditional" ? " (some cases)" : ""}${r.original_or_copy ? `, ${r.original_or_copy}` : ""}${r.copies ? ` x${r.copies}` : ""}${r.notarized ? ", notarized" : ""}${r.issuing_service_id ? " → linked service" : r.document_id ? ` [${r.document_id}]` : ""}`,
      ),
    ),
    Questions: join(
      snap.questions.map(
        (q) =>
          `${q.prompt} ${q.rules
            .map((r) => `[${r.op === "eq" ? "" : r.op + " "}${r.value}: ${[r.add_requirements.length && `adds ${r.add_requirements.join(", ")}`, r.ineligible && `stops: ${r.ineligible}`].filter(Boolean).join("; ")}]`)
            .join(" ")}`,
      ),
    ),
    Steps: join(snap.steps.map((s, i) => `${i + 1}. ${s.title}${s.location ? ` (${s.location})` : ""}`)),
    Forms: join(snap.forms.map((f) => f.title)),
    "Rejection reasons": join(snap.common_rejection_reasons),
    FAQ: join(snap.faq.map((f) => `${f.q}: ${f.a}`)),
  };
}

export function AdminSubmissionDetail({ id }: { id: string }) {
  const { payload, isLoading, error, refetch } = useSubmission(id);
  const { review, isPending } = useReviewSubmission();
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const sub = payload?.submission;

  if (isLoading) return <AdminPage title="Submission"><LoadingState /></AdminPage>;
  if (error || !sub) {
    return (
      <AdminPage title="Submission">
        <ErrorState message={getErrorMessage(error, "Not found")} onRetry={() => refetch()} />
      </AdminPage>
    );
  }

  const before = describe(sub.published_snapshot);
  const after = describe(sub.snapshot);
  const fields = Object.keys(after);
  const changed = fields.filter((f) => (before[f] ?? "-") !== after[f]);

  return (
    <AdminPage
      title={sub.snapshot.name}
      description={`${sub.org_name} · submitted ${timeAgo(sub.created_at)} by ${sub.submitted_by ?? "unknown"}`}
    >
      <Link href="/submissions" className="text-primary mb-4 inline-block text-xs hover:underline">
        ← All submissions
      </Link>
      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <StatusBadge status={sub.status.replace("_", " ")} tone={sub.status === "pending" ? "warning" : "neutral"} />
        {sub.org_status && <OrgStatusChip status={sub.org_status} />}
        <span className="text-muted-foreground">
          {sub.published_snapshot ? `${changed.length} field${changed.length === 1 ? "" : "s"} changed since version ${sub.version}` : "New service, never published"}
        </span>
      </div>

      {sub.change_summary && (
        <div className="mb-4 rounded-md border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
          <p className="font-semibold">What changed, according to the organization</p>
          <p>{sub.change_summary}</p>
          {sub.change_reason && <p className="text-xs">Reason: {sub.change_reason}</p>}
          <p className="text-xs">
            {sub.effective_at ? `Takes effect ${sub.effective_at}. Publishing schedules it for that date.` : "Takes effect as soon as it is published."}
          </p>
        </div>
      )}
      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="w-36 py-2 pr-3 font-medium">Field</th>
                {sub.published_snapshot && <th className="py-2 pr-3 font-medium">Live now</th>}
                <th className="py-2 font-medium">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f) => {
                const diff = changed.includes(f) && !!sub.published_snapshot;
                return (
                  <tr key={f} className={cn("border-border border-t align-top", diff && "bg-amber-50")}>
                    <td className="py-2 pr-3 font-medium">
                      {f}
                      {diff && <span className="ml-1 text-amber-700">●</span>}
                    </td>
                    {sub.published_snapshot && <td className="text-muted-foreground py-2 pr-3 whitespace-pre-wrap">{before[f] ?? "-"}</td>}
                    <td className="py-2 whitespace-pre-wrap">{after[f]}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <aside className="ring-foreground/10 bg-card h-fit space-y-3 p-4 ring-1">
          <h2 className="font-semibold">Path data</h2>
          <CompletenessMeter completeness={sub.completeness} />
          <h2 className="pt-2 font-semibold">Decision</h2>
          {sub.status !== "pending" ? (
            <p className="text-muted-foreground text-xs">
              Already {sub.status.replace("_", " ")}
              {sub.reviewed_by && ` by ${sub.reviewed_by}`}
              {sub.admin_note && `: ${sub.admin_note}`}
            </p>
          ) : (
            <>
              {sub.org_status !== "verified" && (
                <p className="text-xs text-amber-800">
                  Verify the organization before publishing.{" "}
                  <Link href={`/organizations/${sub.org_id}`} className="underline">
                    Open organization
                  </Link>
                </p>
              )}
              <Textarea rows={3} placeholder="Note to the organization (required to request changes)" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="flex flex-wrap gap-2">
                <Button
                  disabled={isPending || sub.org_status !== "verified" || sub.completeness.core_missing.length > 0}
                  onClick={async () => {
                    setErr(null);
                    try {
                      await review(sub.id, { action: "publish", note: note.trim() || undefined });
                    } catch (e) {
                      setErr(getErrorMessage(e));
                    }
                  }}
                >
                  {sub.effective_at ? "Approve and schedule" : "Publish"}
                </Button>
                <Button
                  variant="outline"
                  disabled={isPending || !note.trim()}
                  onClick={async () => {
                    setErr(null);
                    try {
                      await review(sub.id, { action: "request_changes", note: note.trim() });
                    } catch (e) {
                      setErr(getErrorMessage(e));
                    }
                  }}
                >
                  Request changes
                </Button>
              </div>
              {err && <p className="text-destructive text-xs">{err}</p>}
            </>
          )}
        </aside>
      </div>
    </AdminPage>
  );
}
