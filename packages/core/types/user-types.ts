export type User = {
  id?: string;
  email: string;
  fullname: string;
  phone?: string | null;
  telegramUsername?: string | null;
  role?: UserRole;
  preferredSubCity?: string | null;
  /** False until they open the link we emailed after sign-up */
  emailVerified?: boolean;
};

export type UserRole = "user" | "agent" | "admin";

/** "loading" until the first silent refresh on page load has answered. */
export type AuthStatus = "loading" | "authenticated" | "anonymous";

export type SessionPayload = {
  user: User;
  accessToken: string;
  expiresIn: number;
};

export type AuthSession = {
  id: string;
  user_agent: string | null;
  ip: string | null;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
};

export type AuthEvent = {
  id: number;
  user_id: string | null;
  email: string | null;
  event: string;
  ip: string | null;
  user_agent: string | null;
  detail: string | null;
  created_at: string;
};
