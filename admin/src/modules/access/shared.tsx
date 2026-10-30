"use client";

import { formatDateTime, timeAgo } from "@cn/core/lib/format";
import { cn } from "@cn/core/lib/utils";
import { LoadingState, NoAccessState } from "@/modules/shared/states";
import { StatusBadge } from "@/modules/shared/status-badge";
import { APPROVAL_TONE, RISK_TONE, useCan, usePermissionCatalogue, useRoles, type Approval, type AuditEntry, type Risk } from "./api";

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
  if (!can(perm)) return <NoAccessState className="mx-4 my-10 lg:mx-8" />;
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
  if (Array.isArray(value)) return value.map(show).join(", ");
  if (typeof value === "object") {
    // Never show stored secrets (encrypted account numbers and the like)
    return Object.entries(value as Record<string, unknown>)
      .filter(([k]) => !k.endsWith("_enc"))
      .map(([k, v]) => `${k.replace(/_/g, " ")}: ${show(v)}`)
      .join("; ");
  }
  return String(value);
}

/** "users.view" to "Users: view" when the permission list can't be loaded. */
const humanKey = (key: string) => {
  const [area, ...rest] = key.split(".");
  const text = rest.length ? `${area}: ${rest.join(" ")}` : area;
  return (text.charAt(0).toUpperCase() + text.slice(1)).replace(/_/g, " ");
};

/** Role names and permission labels, loaded only for staff who may see them. */
export function useAccessNames() {
  const { can } = useCan();
  const allowed = can("roles.view");
  const roles = useRoles(0, 200, allowed).payload?.items ?? [];
  const areas = usePermissionCatalogue(allowed).payload?.areas ?? [];
  const perms = new Map(areas.flatMap((a) => a.permissions.map((p) => [p.key, p.label] as const)));
  const roleNames = new Map(roles.map((r) => [r.id, r.name] as const));
  return {
    permission: (key: string) => perms.get(key) ?? humanKey(key),
    roles: (ids: unknown) => {
      const list = Array.isArray(ids) ? ids.map(String) : [];
      if (!list.length) return "none";
      const names = list.map((id) => roleNames.get(id));
      return names.every(Boolean) ? names.join(", ") : `${list.length} role${list.length === 1 ? "" : "s"}`;
    },
  };
}

type Names = ReturnType<typeof useAccessNames>;

const etb = (v: unknown) => {
  const n = Number(v);
  return Number.isFinite(n) ? `${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ETB` : show(v);
};

/** Readable details per kind of request. Ids and encrypted values stay out; the summary already names people. */
function approvalDetails(action: string, p: Record<string, unknown>, names: Names): [string, string][] {
  const rows: [string, unknown][] = [];
  const perms = (v: unknown) => (Array.isArray(v) && v.length ? v.map((k) => names.permission(String(k))).join(", ") : null);
  switch (action) {
    case "payment.refund": {
      const bank = (p.client_bank ?? null) as Record<string, unknown> | null;
      rows.push(["Payment", p.tx_ref], ["Amount", etb(p.amount)],
        ["How", p.method === "manual" ? "Bank transfer from us" : "Back through the payment gateway"], ["Reason", p.reason]);
      if (bank) {
        rows.push(["Bank", bank.bank_name], ["Account holder", bank.account_name],
          ["Account", bank.last4 ? `ending ${String(bank.last4)}` : null]);
      }
      break;
    }
    case "payout.large":
      rows.push(["Amount", etb(p.amount)], ["Note", p.note]);
      break;
    case "data_source.delete":
      rows.push(["Data source", p.name]);
      break;
    case "settings.money_reset":
      rows.push(["Setting", p.key], ["Now", show(p.before)], ["After approval", show(p.after)]);
      break;
    case "staff.create":
    case "staff.super_admin":
    case "staff.set_roles":
      if (p.kind === "create") {
        rows.push(["Email", p.email], ["Name", p.fullname || "No name"], ["Roles", names.roles(p.role_ids)], ["Invited by", p.invited_by]);
      } else {
        rows.push(["Roles after approval", names.roles(p.role_ids)]);
      }
      break;
    case "staff.disable":
    case "staff.enable":
      break;
    case "role.create":
      rows.push(["Name", p.name], ["Permissions", perms(p.permissions) ?? "none"]);
      break;
    case "role.update":
      rows.push(["Role", p.name], ["Add", perms(p.add)], ["Remove", perms(p.remove)]);
      break;
    case "role.delete":
      rows.push(["Role", p.name]);
      break;
    default:
      for (const [k, v] of Object.entries(p)) {
        if (["values", "before", "beneficiaries", "kind"].includes(k) || k.endsWith("_enc") || k.endsWith("_id") || k.endsWith("_ids")) continue;
        rows.push([k.charAt(0).toUpperCase() + k.slice(1).replace(/_/g, " "), v]);
      }
  }
  return rows.filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => [k, typeof v === "string" ? v : show(v)]);
}

/** The exact change an approval would make: settings before and after, or the stored details. */
export function ApprovalChange({ approval }: { approval: Approval }) {
  const names = useAccessNames();
  const p = approval.payload as Record<string, unknown>;
  const values = p.values as Record<string, unknown> | undefined;
  const before = p.before as Record<string, unknown> | undefined;
  const rows: [string, string, string][] = values
    ? Object.keys(values).map((k) => [k, show(before?.[k]), show(values[k])])
    : [];
  const details = values ? [] : approvalDetails(approval.action, p, names);
  return (
    <div className="space-y-2 text-xs">
      <p>{approval.summary}</p>
      {rows.length > 0 && (
        <div className="relative overflow-x-auto">
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
      {details.length > 0 && (
        <dl className="bg-muted/40 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 p-2 text-[11px]">
          {details.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="break-words">{v}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

const ACTION_LABELS: Record<string, string> = {
  "access.denied": "Refused (no permission)",
  "approval.approved": "Approved a request",
  "approval.cancelled": "Cancelled a request",
  "approval.executed": "Approved change carried out",
  "approval.expired": "Request expired",
  "approval.failed": "Approved change failed",
  "approval.rejected": "Rejected a request",
  "approval.requested": "Asked for approval",
  "approval.waived": "Ran without a second approver",
  "auth.invite_accepted": "Accepted the invitation",
  "auth.login": "Signed in",
  "auth.login_blocked": "Sign-in blocked",
  "auth.login_failed": "Sign-in failed",
  "auth.logout": "Signed out",
  "auth.logout_all": "Signed out everywhere",
  "auth.password_changed": "Changed the password",
  "auth.password_change_failed": "Password change failed",
  "auth.password_reset_requested": "Asked for a password reset",
  "auth.refresh_reuse": "Old session reused, signed out",
  "auth.session_revoked": "Signed out a session",
  "hires.export": "Exported hires",
  "role.created": "Created a role",
  "role.deleted": "Deleted a role",
  "role.renamed": "Renamed a role",
  "staff.created_from_shell": "Staff added from the server",
  "staff.invited": "Invited a staff member",
  "staff.invite_resent": "Sent an invitation again",
  "staff.invite_revoked": "Cancelled an invitation",
  "staff.renamed": "Changed a staff name",
  "staff.signed_out": "Signed a staff member out",
};

/** Short "Chrome on Windows" from a full user-agent string. */
export function describeUserAgent(ua: string | null | undefined): string {
  if (!ua) return "Unknown browser";
  const browser = /Edg\//.test(ua)
    ? "Edge"
    : /OPR\//.test(ua)
      ? "Opera"
      : /Firefox\//.test(ua)
        ? "Firefox"
        : /HeadlessChrome\//.test(ua)
          ? "Headless Chrome"
          : /Chrome\//.test(ua)
            ? "Chrome"
            : /Version\/.*Safari\//.test(ua)
              ? "Safari"
              : (ua.split(/[\s/]/)[0] || "Unknown browser");
  const os = /Android/.test(ua)
    ? "Android"
    : /iPhone|iPad|iPod/.test(ua)
      ? "iOS"
      : /Windows/.test(ua)
        ? "Windows"
        : /Mac OS X|Macintosh/.test(ua)
          ? "macOS"
          : /CrOS/.test(ua)
            ? "ChromeOS"
            : /Linux/.test(ua)
              ? "Linux"
              : null;
  return os ? `${browser} on ${os}` : browser;
}

export function AuditTable({ items, showActor = true }: { items: AuditEntry[]; showActor?: boolean }) {
  const names = useAccessNames();
  const label = (action: string) => ACTION_LABELS[action] ?? names.permission(action);
  return (
    <div className="relative overflow-x-auto">
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
                <td className={cn("py-1.5 pr-3", failed && "text-destructive")} title={e.action}>
                  {label(e.action)}
                </td>
                <td className="text-muted-foreground py-1.5 pr-3 font-mono break-all">{e.target ?? ""}</td>
                <td className="text-muted-foreground py-1.5 pr-3">
                  <span className="font-mono">{e.ip ?? "-"}</span>
                  {e.user_agent && <span className="block" title={e.user_agent}>{describeUserAgent(e.user_agent)}</span>}
                </td>
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
