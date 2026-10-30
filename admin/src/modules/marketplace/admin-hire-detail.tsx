"use client";

import { getErrorMessage } from "@cn/core/lib/errors";
import Link from "next/link";
import { useAdminHire } from "@cn/core/api/providers";
import { cn } from "@cn/core/lib/utils";
import { humanize } from "@cn/core/lib/format";
import { AdminPage } from "@/modules/components/admin-page";
import { useCan } from "@/modules/access/api";
import { EmptyState, LoadingState, formatDateTime } from "@cn/ui/guday/shared";
import { ErrorState } from "@/modules/shared/states";
import { PaymentBadge, PriceLine } from "@cn/ui/marketplace/payment-badge";
import { HireStatusBadge, Stars } from "@cn/ui/marketplace/trust";
import { HIRE_STATUS, areaLabel } from "@cn/ui/marketplace/constants";
import type { HireEvent } from "@cn/core/types/provider";
import { AssignProvider, DisputeDecision, StaffChange } from "./admin-hire-actions";

function Box({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border-border bg-card border p-3", className)}>
      <h2 className="text-muted-foreground mb-2 text-[11px] font-medium tracking-wider uppercase">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  if (children == null || children === "" || children === false) return null;
  return (
    <div className="grid grid-cols-[7rem_1fr] gap-2 py-0.5 text-xs">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

const EVENT_LABELS: Record<string, string> = {
  created: "Request sent",
  assigned: "Provider assigned by staff",
  reassigned: "Moved to another provider by staff",
  accept: "Provider accepted",
  decline: "Provider declined",
  start: "Work started",
  complete: "Marked as delivered",
  cancel: "Cancelled by the client",
  confirmed: "Client confirmed the work",
  auto_confirmed: "Closed automatically",
  complaint: "Client reported a problem",
  complaint_upheld: "Complaint upheld",
  complaint_dismissed: "Complaint dismissed",
  refund_needed: "Marked as needing a refund",
  staff_cancelled: "Cancelled by staff",
  reopened: "Reopened by staff",
  staff_note: "Staff note",
};

function who(e: HireEvent): string {
  if (e.actor_kind === "staff") return e.actor ?? "Staff";
  if (e.actor_kind === "provider") return e.actor ?? e.provider_name ?? "Provider";
  if (e.actor_kind === "client") return "Client";
  return "System";
}

function statusLabel(s: string | null) {
  return s ? (HIRE_STATUS[s as keyof typeof HIRE_STATUS]?.label ?? humanize(s)) : null;
}

export function AdminHireDetail({ id }: { id: string }) {
  const { data, isLoading, isError, error, refetch } = useAdminHire(id);
  const { can } = useCan();
  const detail = data?.payload;

  if (isLoading) return <AdminPage title="Hire · ቅጥር"><LoadingState /></AdminPage>;
  if (isError || !detail) {
    return (
      <AdminPage title="Hire · ቅጥር">
        <ErrorState error={error} message={getErrorMessage(error, "Could not load this hire")} onRetry={() => refetch()} />
      </AdminPage>
    );
  }
  const { hire: h, events, payments, tickets, actions } = detail;
  const manage = can("hires.manage");

  return (
    <AdminPage title={`${h.title} · ቅጥር`} description={`Hire ${h.id.slice(0, 8)} · sent ${formatDateTime(h.created_at)}`}>
      {h.refund_needed && (
        <p role="status" className="border-destructive/40 bg-destructive/5 text-destructive mb-4 border p-3 text-xs">
          <strong>Refund needed.</strong> A complaint about this paid job was upheld
          {h.refund_flagged_by ? ` by ${h.refund_flagged_by}` : ""}
          {h.refund_flagged_at ? ` on ${formatDateTime(h.refund_flagged_at)}` : ""}.{" "}
          <Link href={`/marketplace/payments?engagement=${h.id}`} className="font-semibold underline">
            Open its payment to refund the client
          </Link>
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Box title="The hire">
          <dl>
            <Row label="Status"><HireStatusBadge status={h.status} /></Row>
            <Row label="Client">
              {h.client_name} · {h.client_phone}
              {h.client_telegram ? ` · Telegram @${h.client_telegram}` : ""}
            </Row>
            <Row label="Provider">
              {h.provider_id ? (
                <Link href={`/marketplace/${h.provider_id}`} className="text-primary underline">{h.provider_name}</Link>
              ) : (
                "None yet"
              )}
              {h.provider_registration_no ? ` · ${h.provider_registration_no}` : ""}
            </Row>
            <Row label="Service">{h.service_name}</Row>
            <Row label="Area">{h.sub_city ? areaLabel(h.sub_city) : null}</Row>
            <Row label="Budget">{h.budget}</Row>
            <Row label="Details">{h.details}</Row>
            <Row label="Price">
              {h.agreed_price != null ? <PriceLine price={h.agreed_price} note={h.price_note} status={h.payment_status} /> : null}
            </Row>
            <Row label="Payment"><PaymentBadge status={h.payment_status} /></Row>
            <Row label="Delivered">{h.completed_at ? formatDateTime(h.completed_at) : null}</Row>
            <Row label="What was delivered">{h.completion_note}</Row>
            <Row label="Closed">{h.client_confirmed_at ? `${formatDateTime(h.client_confirmed_at)}${h.auto_confirmed ? " (automatically)" : ""}` : null}</Row>
            <Row label="Review">{h.review_rating ? <><Stars value={h.review_rating} /> {h.review_comment}</> : null}</Row>
            <Row label="Staff note">{h.admin_note}</Row>
          </dl>
        </Box>

        <div className="space-y-4">
          {h.disputed && (
            <Box title="Complaint">
              {h.dispute_status === "open" && manage ? (
                <DisputeDecision hire={h} />
              ) : (
                <dl>
                  <Row label="Reported">{h.dispute_reason}</Row>
                  <Row label="Decision">{h.dispute_status ? humanize(h.dispute_status) : null}</Row>
                  <Row label="Finding">{h.dispute_note}</Row>
                  <Row label="Decided by">
                    {h.dispute_resolved_by ? `${h.dispute_resolved_by}${h.dispute_resolved_at ? `, ${formatDateTime(h.dispute_resolved_at)}` : ""}` : null}
                  </Row>
                </dl>
              )}
            </Box>
          )}

          {manage && actions.length > 0 && (
            <Box title="Staff actions">
              {actions.includes("assign") && (
                <details className="mb-3" open={h.status === "open"}>
                  <summary className="cursor-pointer text-xs font-medium">
                    {h.provider_id ? "Move to another provider (before they accept)" : "Assign a provider"}
                  </summary>
                  <div className="mt-2"><AssignProvider hire={h} /></div>
                </details>
              )}
              <div className="flex flex-wrap gap-2">
                {actions.includes("cancel") && <StaffChange hire={h} action="cancel" />}
                {actions.includes("reopen") && <StaffChange hire={h} action="reopen" />}
                {actions.includes("note") && <StaffChange hire={h} action="note" />}
              </div>
              {(h.payment_status === "paid" || h.payment_status === "pending") && (
                <p className="text-muted-foreground mt-2 text-xs">
                  This job is paid or being paid, so it can&apos;t be cancelled or reopened. Money goes back through a refund.
                </p>
              )}
            </Box>
          )}
        </div>
      </div>

      <Box title="History" className="mt-4">
        <ol className="space-y-2">
          {events.map((e, i) => (
            <li key={e.id ?? `start-${i}`} className="border-border border-l-2 pl-3 text-xs">
              <p>
                <span className="font-medium">{EVENT_LABELS[e.action] ?? humanize(e.action)}</span>
                <span className="text-muted-foreground"> · {who(e)} · {formatDateTime(e.created_at)}</span>
              </p>
              {e.from_status && e.to_status && e.from_status !== e.to_status && (
                <p className="text-muted-foreground">{statusLabel(e.from_status)} → {statusLabel(e.to_status)}</p>
              )}
              {(e.action === "assigned" || e.action === "reassigned") && e.provider_name && (
                <p className="text-muted-foreground">To {e.provider_name}</p>
              )}
              {e.note && <p className="mt-0.5 whitespace-pre-line">{e.note}</p>}
            </li>
          ))}
        </ol>
      </Box>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {payments !== null && (
          <Box title="Payments">
            {!payments.length ? (
              <EmptyState title="No payments" />
            ) : (
              <ul className="space-y-2 text-xs">
                {payments.map((p) => (
                  <li key={p.tx_ref} className="border-border border-b pb-2 last:border-0">
                    <p className="font-medium">{p.amount.toLocaleString("en")} ETB · {humanize(p.status)}</p>
                    <p className="text-muted-foreground break-all">
                      {p.tx_ref} · {p.gateway}{p.payment_method ? ` · ${p.payment_method}` : ""} · {formatDateTime(p.created_at)}
                    </p>
                    {p.provider_amount != null && (
                      <p className="text-muted-foreground">
                        Provider share {p.provider_amount.toLocaleString("en")} ETB · commission {(p.commission_amount ?? 0).toLocaleString("en")} ETB
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Box>
        )}
        {tickets !== null && (
          <Box title="Messages to staff (support requests)">
            {!tickets.length ? (
              <EmptyState title="No support requests from these people" />
            ) : (
              <ul className="space-y-2 text-xs">
                {tickets.map((t) => (
                  <li key={t.id}>
                    <Link href={`/support/${t.id}`} className="text-primary font-medium underline">{t.ref}</Link>{" "}
                    {t.subject}
                    <span className="text-muted-foreground"> · from the {t.from_side} · {humanize(t.status)} · {formatDateTime(t.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Box>
        )}
      </div>
    </AdminPage>
  );
}
