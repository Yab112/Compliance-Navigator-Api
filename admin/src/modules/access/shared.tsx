"use client";

import { formatDateTime, timeAgo } from "@cn/core/lib/format";
import { cn } from "@cn/core/lib/utils";
import { LoadingState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import { APPROVAL_TONE, RISK_TONE, useCan, type Approval, type AuditEntry, type Risk } from "./api";

export function RiskBadge({ risk }: { risk: Risk }) {
  return <StatusBadge status={`${risk} risk`} tone={RISK_TONE[risk]} />;
}

export function ApprovalStatusBadge({ status }: { status: Approval["status"] }) {
  return <StatusBadge status={status === "executed" ? "approved and done" : status} tone={APPROVAL_TONE[status]} />;
}

/** Shows children only to staff with the permission; the server refuses the data anyway. */
export function Gate({ perm, children }: { perm: string; children: React.ReactNode }) {
  const { can, loaded } = useCan();
  if (!loaded) return <LoadingState />;
  if (!can(perm)) {
    return (
      <div className="border-border text-muted-foreground mx-4 my-10 border border-dashed px-4 py-10 text-center text-xs lg:mx-8">
        <p className="text-foreground font-medium">You don&apos;t have access to this page</p>
        <p className="mt-1">Ask a Super admin if you need it for your work.</p>
      </div>
    );
  }
  return <>{children}</>;
}

/** Result line after an action; announced to screen readers. */
export function Notice({ message, tone = "info" }: { message: string | null; tone?: "info" | "error" }) {
  return (
    <p
      role={tone === "error" ? "alert" : "status"}
      aria-live="polite"
      className={cn(
        "text-xs",
        !message && "sr-only",
        tone === "error" ? "text-destructive" : "text-foreground bg-secondary rounded px-2 py-1.5",
      )}
    >
      {message ?? ""}
    </p>
  );
}

export function When({ at }: { at: string | null | undefined }) {
  if (!at) return <span className="text-muted-foreground">-</span>;
  return (
    <time dateTime={at} title={formatDateTime(at)} className="whitespace-nowrap">
      {timeAgo(at)}
    </time>
  );
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === "") return "(empty)";
  if (typeof value === "boolean") return value ? "on" : "off";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** The exact change an approval would make: settings before and after, or the stored details. */
export function ApprovalChange({ approval }: { approval: Approval }) {
  const p = approval.payload as Record<string, unknown>;
  const values = p.values as Record<string, unknown> | undefined;
  const before = p.before as Record<string, unknown> | undefined;
  const rows: [string, string, string][] = values
    ? Object.keys(values).map((k) => [k, show(before?.[k]), show(values[k])])
    : [];
  const rest = Object.entries(p).filter(([k]) => !["values", "before", "beneficiaries", "kind"].includes(k));
  return (
    <div className="space-y-2 text-xs">
      <p>{approval.summary}</p>
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[320px] text-left">
            <thead className="text-muted-foreground text-[11px]">
              <tr>
                <th className="pr-3 font-medium">Setting</th>
                <th className="pr-3 font-medium">Now</th>
                <th className="font-medium">After approval</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([k, from, to]) => (
                <tr key={k} className="border-border border-t">
                  <td className="py-1 pr-3 font-mono">{k}</td>
                  <td className="py-1 pr-3">{from}</td>
                  <td className="py-1 font-semibold">{to}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!values && rest.length > 0 && (
        <dl className="bg-muted/40 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 p-2 text-[11px]">
          {rest.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k.replace(/_/g, " ")}</dt>
              <dd className="font-mono break-all">{show(v)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

export function AuditTable({ items, showActor = true }: { items: AuditEntry[]; showActor?: boolean }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-xs">
        <thead className="text-muted-foreground text-[11px]">
          <tr>
            <th className="py-1.5 pr-3 font-medium">When</th>
            {showActor && <th className="py-1.5 pr-3 font-medium">Who</th>}
            <th className="py-1.5 pr-3 font-medium">Action</th>
            <th className="py-1.5 pr-3 font-medium">Target</th>
            <th className="py-1.5 pr-3 font-medium">Network</th>
            <th className="py-1.5 font-medium">Details</th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => {
            const status = e.details?.status;
            const failed = e.action.includes("failed") || e.action.includes("denied") || (typeof status === "number" && status >= 400);
            return (
              <tr key={e.id} className="border-border border-t align-top">
                <td className="text-muted-foreground py-1.5 pr-3">
                  <When at={e.created_at} />
                </td>
                {showActor && <td className="py-1.5 pr-3 break-all">{e.actor_email ?? "-"}</td>}
                <td className={cn("py-1.5 pr-3 font-mono", failed && "text-destructive")}>{e.action}</td>
                <td className="text-muted-foreground py-1.5 pr-3 font-mono break-all">{e.target ?? ""}</td>
                <td className="text-muted-foreground py-1.5 pr-3 font-mono">{e.ip ?? "-"}</td>
                <td className="py-1.5">
                  {e.details && Object.keys(e.details).length > 0 && (
                    <details>
                      <summary className="text-primary cursor-pointer">
                        {status !== undefined ? `Result: ${String(status)}` : "Show"}
                      </summary>
                      <pre className="bg-muted/50 mt-1 max-w-md overflow-x-auto p-2 text-[10px] whitespace-pre-wrap">
                        {JSON.stringify(e.details, null, 2)}
                      </pre>
                    </details>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
