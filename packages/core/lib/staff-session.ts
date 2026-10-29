import axios from "axios";
import { env } from "../config/env";
import { applySession, broadcastAuth, configureAuthRealm, endSession, postAuth } from "./auth-session";
import type { SessionPayload } from "../types/user-types";

/**
 * Staff realm for the admin app. Staff accounts, sessions and the refresh cookie
 * (cn_staff_refresh, scoped to /api/v1/staff/auth) are separate from the public site's,
 * so a public account never signs in here and a staff session never works on the public site.
 */
export const staffPaths = {
  login: "staff/auth/login",
  refresh: "staff/auth/refresh",
  logout: "staff/auth/logout",
  logoutAll: "staff/auth/logout-all",
  forgotPassword: "staff/auth/forgot-password",
  link: "staff/auth/link",
  acceptInvite: "staff/auth/accept-invite",
  resetPassword: "staff/auth/reset-password",
  me: "staff/me",
  changePassword: "staff/me/change-password",
  sessions: "staff/me/sessions",
  session: (id: string) => `staff/me/sessions/${id}`,
  activity: "staff/me/activity",
};

let configured = false;

/** Call once, at module load, before the auth provider makes its first refresh. */
export function enableStaffRealm(): void {
  if (configured) return;
  configured = true;
  configureAuthRealm({ refreshPath: staffPaths.refresh, channel: "cn-staff-auth" });
}

export async function staffLogin(email: string, password: string): Promise<SessionPayload> {
  const session = await postAuth<SessionPayload>(staffPaths.login, { email, password });
  applySession(session);
  broadcastAuth({ type: "signed-in" });
  return session;
}

export async function staffLogout(everywhere = false): Promise<void> {
  try {
    await postAuth(everywhere ? staffPaths.logoutAll : staffPaths.logout);
  } catch {
    // Sign out locally even if the server can't be reached
  } finally {
    endSession();
    broadcastAuth({ type: "signed-out" });
  }
}

export type StaffMe = {
  user: { id: string; email: string; fullname: string; status: string; mustChangePassword: boolean };
  roles: { id: string; name: string; builtIn: boolean }[];
  permissions: string[];
  superAdmin: boolean;
  approvalsWaiting: number;
};

// Invitation and password pages are used before signing in, so these calls carry no session
const anon = axios.create({ baseURL: env.NEXT_PUBLIC_API_BASE_URL, withCredentials: true });

/** Who a one-time link is for; rejects when it is invalid, used or expired. */
export async function checkStaffLink(token: string, kind: "invite" | "reset"): Promise<{ email: string; fullname: string }> {
  const res = await anon.get<{ payload: { email: string; fullname: string } }>(staffPaths.link, { params: { token, kind } });
  return res.data.payload;
}

export async function redeemStaffLink(kind: "invite" | "reset", token: string, newPassword: string): Promise<void> {
  await anon.post(kind === "invite" ? staffPaths.acceptInvite : staffPaths.resetPassword, { token, new_password: newPassword });
}

export async function requestStaffReset(email: string): Promise<void> {
  await anon.post(staffPaths.forgotPassword, { email });
}
