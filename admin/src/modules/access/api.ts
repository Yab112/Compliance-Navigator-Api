"use client";

import { useAdminMutation, useAdminQuery } from "@cn/core/api/admin/use-admin-query";
import { MTD } from "@cn/core/lib/constants/methods";
import { staffPaths, type StaffMe } from "@cn/core/lib/staff-session";
import { useUserStore } from "@cn/core/store/user-store";

/** Staff access API: staff, roles, permissions, approvals, audit log and the signed-in staff member. */
const base = "admin/access";
export const accessPaths = {
  permissions: `${base}/permissions`,
  roles: `${base}/roles`,
  role: (id: string) => `${base}/roles/${id}`,
  staff: `${base}/staff`,
  staffMember: (id: string) => `${base}/staff/${id}`,
  staffSessions: (id: string) => `${base}/staff/${id}/sessions`,
  staffRoles: (id: string) => `${base}/staff/${id}/roles`,
  staffAction: (id: string, action: string) => `${base}/staff/${id}/${action}`,
  approvals: `${base}/approvals`,
  approval: (id: string) => `${base}/approvals/${id}`,
  decide: (id: string, how: "approve" | "reject" | "cancel") => `${base}/approvals/${id}/${how}`,
  audit: `${base}/audit`,
};

export type Risk = "low" | "medium" | "high" | "critical";
export type PermissionInfo = { key: string; label: string; description: string; risk: Risk; roles: string[] };
export type PermissionArea = { key: string; title: string; permissions: PermissionInfo[] };

export type Role = {
  id: string;
  name: string;
  description: string;
  builtin_key: string | null;
  built_in: boolean;
  permissions: string[];
  members: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  staff?: { id: string; email: string; fullname: string; status: string }[];
};

export type StaffStatus = "invited" | "active" | "disabled";
export type StaffMember = {
  id: string;
  email: string;
  fullname: string;
  status: StaffStatus;
  must_change_password: boolean;
  last_login_at: string | null;
  created_by: string | null;
  created_at: string;
  roles: { id: string; name: string; built_in: boolean }[];
  super_admin: boolean;
  active_sessions: number;
  invite: { created_at: string; expires_at: string; expired: boolean } | null;
  permissions?: string[];
  recent_actions?: AuditEntry[] | null;
};

export type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled" | "expired" | "executed" | "failed";
export type Approval = {
  id: string;
  action: string;
  title: string;
  payload: Record<string, unknown>;
  summary: string;
  target: string | null;
  requested_by: string | null;
  requested_by_email: string;
  approver_permission: string;
  status: ApprovalStatus;
  decided_by: string | null;
  decided_by_email: string | null;
  decision_note: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  decided_at: string | null;
  executed_at: string | null;
  expires_at: string;
};

export type AuditEntry = {
  id: number;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  target: string | null;
  details: Record<string, unknown>;
  ip: string | null;
  user_agent: string | null;
  created_at: string;
};

export type Session = {
  id: string;
  user_agent: string | null;
  ip: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current?: boolean;
};

export type Paged<T> = { items: T[]; total: number };
/** What a gated action answers: done at once, or waiting for a second person. */
export type Outcome = { approval?: Approval; waived?: boolean; unchanged?: boolean };

export const PAGE_SIZE = 25;

function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  return sp.toString();
}

// ---------------------------------------------------------------- me and permissions

export const useStaffMe = () => {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  return useAdminQuery<StaffMe>(["staff-me"], staffPaths.me, { enabled: signedIn });
};

/** `can("roles.manage")`. The server checks every request; this only hides what would be refused. */
export function useCan() {
  const { payload } = useStaffMe();
  const perms = new Set(payload?.permissions ?? []);
  return { can: (perm: string) => perms.has(perm), loaded: !!payload, me: payload };
}

export const usePermissionCatalogue = () =>
  useAdminQuery<{ areas: PermissionArea[]; risk_levels: Risk[] }>(["access", "permissions"], accessPaths.permissions);

// ---------------------------------------------------------------- roles

export const useRoles = (page = 0, pageSize = 50) =>
  useAdminQuery<Paged<Role>>(["access", "roles", page, pageSize], `${accessPaths.roles}?${qs({ limit: pageSize, offset: page * pageSize })}`);

export const useRole = (id: string | null) =>
  useAdminQuery<{ role: Role }>(["access", "role", id], accessPaths.role(id ?? ""), { enabled: !!id });

export type RoleInput = { name: string; description: string; permissions: string[] };

export const useRoleMutations = () => {
  const { run, isPending } = useAdminMutation<unknown, RoleInput | undefined>();
  return {
    isPending,
    create: (body: RoleInput) => run(accessPaths.roles, MTD.POST, body) as Promise<{ role: Role }>,
    update: (id: string, body: RoleInput) => run(accessPaths.role(id), MTD.PUT, body) as Promise<{ role: Role } & Outcome>,
    remove: (id: string) => run(accessPaths.role(id), MTD.DELETE) as Promise<{ deleted?: boolean } & Outcome>,
  };
};

// ---------------------------------------------------------------- staff

export type StaffFilters = { q?: string; status?: string; role_id?: string; page?: number };

export const useStaffList = ({ q = "", status = "", role_id = "", page = 0 }: StaffFilters) =>
  useAdminQuery<Paged<StaffMember>>(
    ["access", "staff", q, status, role_id, page],
    `${accessPaths.staff}?${qs({ q, status, role_id, limit: PAGE_SIZE, offset: page * PAGE_SIZE })}`,
  );

export const useStaffMember = (id: string) =>
  useAdminQuery<{ staff: StaffMember }>(["access", "staff-member", id], accessPaths.staffMember(id));

export const useStaffSessions = (id: string, page: number, pageSize = 10) =>
  useAdminQuery<Paged<Session>>(
    ["access", "staff-sessions", id, page],
    `${accessPaths.staffSessions(id)}?${qs({ limit: pageSize, offset: page * pageSize })}`,
  );

export type LinkResult = { email_sent: boolean; link: string | null; expires_in_minutes: number };

export const useStaffMutations = () => {
  const { run, isPending } = useAdminMutation<unknown, unknown>();
  return {
    isPending,
    invite: (body: { email: string; fullname: string; role_ids: string[] }) =>
      run(accessPaths.staff, MTD.POST, body) as Promise<Outcome>,
    rename: (id: string, fullname: string) => run(accessPaths.staffMember(id), MTD.PATCH, { fullname }),
    setRoles: (id: string, role_ids: string[]) => run(accessPaths.staffRoles(id), MTD.PUT, { role_ids }) as Promise<Outcome>,
    action: (id: string, action: "disable" | "enable" | "revoke-invite" | "sign-out") =>
      run(accessPaths.staffAction(id, action), MTD.POST) as Promise<Outcome>,
    sendLink: (id: string, kind: "resend-invite" | "reset-password") =>
      run(accessPaths.staffAction(id, kind), MTD.POST) as Promise<LinkResult>,
  };
};

// ---------------------------------------------------------------- approvals

export type ApprovalBox = "waiting" | "mine" | "all";

export const useApprovals = (box: ApprovalBox, page: number, status = "") =>
  useAdminQuery<Paged<Approval>>(
    ["access", "approvals", box, status, page],
    `${accessPaths.approvals}?${qs({ box, status, limit: PAGE_SIZE, offset: page * PAGE_SIZE })}`,
  );

export const useApprovalCount = (box: ApprovalBox) =>
  useAdminQuery<Paged<Approval>>(["access", "approvals", box, "count"], `${accessPaths.approvals}?${qs({ box, limit: 1 })}`)
    .payload?.total;

export const useDecide = () => {
  const { run, isPending } = useAdminMutation<{ approval: Approval }, { note?: string } | undefined>();
  return {
    isPending,
    decide: (id: string, how: "approve" | "reject" | "cancel", note?: string) =>
      run(accessPaths.decide(id, how), MTD.POST, how === "cancel" ? undefined : { note }),
  };
};

// ---------------------------------------------------------------- audit

export type AuditFilters = { actor?: string; action?: string; target?: string; since?: string; until?: string };

export const useAudit = (filters: AuditFilters, page: number) =>
  useAdminQuery<Paged<AuditEntry>>(
    ["access", "audit", filters, page],
    `${accessPaths.audit}?${qs({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE })}`,
  );

// ---------------------------------------------------------------- my account

export const useMySessions = (page: number, pageSize = 10) =>
  useAdminQuery<Paged<Session>>(["my-sessions", page], `${staffPaths.sessions}?${qs({ limit: pageSize, offset: page * pageSize })}`);

export const useMyActivity = (page: number, pageSize = 10) =>
  useAdminQuery<Paged<AuditEntry>>(["my-activity", page], `${staffPaths.activity}?${qs({ limit: pageSize, offset: page * pageSize })}`);

export const useMyAccountMutations = () => {
  const { run, isPending } = useAdminMutation<unknown, unknown>();
  return {
    isPending,
    changePassword: (current_password: string, new_password: string) =>
      run(staffPaths.changePassword, MTD.POST, { current_password, new_password }) as Promise<{ otherSessionsSignedOut: number }>,
    endSession: (id: string) => run(staffPaths.session(id), MTD.DELETE),
  };
};

// ---------------------------------------------------------------- shared labels

export const RISK_TONE: Record<Risk, "neutral" | "info" | "warning" | "critical"> = {
  low: "neutral",
  medium: "info",
  high: "warning",
  critical: "critical",
};

export const APPROVAL_TONE: Record<ApprovalStatus, "good" | "warning" | "critical" | "neutral" | "info"> = {
  pending: "warning",
  approved: "info",
  executed: "good",
  rejected: "critical",
  failed: "critical",
  cancelled: "neutral",
  expired: "neutral",
};

/** One line for a gated action's answer, for the status message next to the button. */
export function outcomeMessage(outcome: Outcome, done: string): string {
  if (outcome.approval) return "Sent for approval. Another staff member has to approve it in Approvals before it happens.";
  if (outcome.waived) return `${done} No other staff member could approve it, so it ran at once and was logged.`;
  if (outcome.unchanged) return "Nothing changed.";
  return done;
}
