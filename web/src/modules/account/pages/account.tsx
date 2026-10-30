"use client";

import Link from "next/link";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  SECURITY_PAGE_SIZE,
  useChangePassword,
  useLogout,
  useMyActivity,
  useMySessions,
  useRevokeSession,
  useUpdateProfile,
} from "@cn/core/api/auth";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Pager, useUrlPage } from "@cn/ui/pager";
import { useRequireAuth } from "@cn/core/hooks/use-require-auth";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { MTD } from "@cn/core/lib/constants/methods";
import { getErrorMessage } from "@cn/core/lib/errors";
import { PasswordInput, passwordIsValid } from "@cn/ui/auth/password-input";
import { Field, LoadingState, NativeSelect, PHONE_RE, SubCityOptions, formatDateTime } from "@cn/ui/guday/shared";
import { useUserStore } from "@cn/core/store/user-store";
import type { AuthEvent, AuthSession } from "@cn/core/types/user-types";
import { cleanTelegram, TELEGRAM_HINT, TELEGRAM_RE } from "@/lib/telegram";
import { cn } from "@cn/core/lib/utils";
import { useMyProvider } from "@cn/core/api/providers";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { MyAgreements } from "@/modules/legal/components/my-agreements";

const EVENT_LABEL: Record<string, string> = {
  register: "Account created",
  login_success: "Signed in",
  login_failed: "Failed sign-in attempt",
  login_blocked: "Sign-in blocked after repeated failures",
  logout: "Signed out",
  logout_all: "Signed out everywhere",
  password_changed: "Password changed",
  password_change_failed: "Wrong current password entered",
  password_reset_requested: "Password reset requested",
  password_reset: "Password reset",
  reset_link_issued: "Reset link issued by an administrator",
  session_revoked: "Signed out a device",
  sessions_revoked_by_admin: "Signed out by an administrator",
  refresh_reuse: "Suspicious session reuse, signed out for safety",
  admin_updated_user: "Account changed by an administrator",
  register_existing: "Someone tried to register with your email",
  email_verification_sent: "Verification email sent",
  email_verified: "Email address verified",
  legal_accepted: "Agreed to the terms",
};

/** "Chrome on Linux"-style label from a user agent string. */
function deviceLabel(ua: string | null): string {
  if (!ua) return "Unknown device";
  const browser = /Edg\//.test(ua) ? "Edge" : /Chrome\//.test(ua) ? "Chrome" : /Firefox\//.test(ua) ? "Firefox" : /Safari\//.test(ua) ? "Safari" : "Browser";
  const os = /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Windows/.test(ua) ? "Windows" : /Mac OS/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "";
  return os ? `${browser} on ${os}` : browser;
}

function Section({ title, am, children, aside }: { title: string; am: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="border-border bg-card rounded-md border">
      <header className="border-border flex flex-wrap items-center justify-between gap-2 border-b px-5 py-3">
        <h2 className="text-gov-ink font-semibold">
          {title} <span className="text-muted-foreground text-sm font-normal">· {am}</span>
        </h2>
        {aside}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

function ProfileForm() {
  const user = useUserStore((s) => s.user)!;
  const update = useUpdateProfile();
  const [fullname, setFullname] = useState(user.fullname);
  const [phone, setPhone] = useState(user.phone ?? "");
  const [telegram, setTelegram] = useState(user.telegramUsername ? `@${user.telegramUsername}` : "");
  const [subCity, setSubCity] = useState(user.preferredSubCity ?? "");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={async (e) => {
        e.preventDefault();
        setMessage(null);
        if (phone.trim() && !PHONE_RE.test(phone.replace(/\s/g, ""))) {
          setMessage({ ok: false, text: "Enter an Ethiopian mobile number like 0911234567, or leave it empty." });
          return;
        }
        if (telegram.trim() && !TELEGRAM_RE.test(cleanTelegram(telegram))) {
          setMessage({ ok: false, text: TELEGRAM_HINT });
          return;
        }
        try {
          await update.mutateAsync({
            url: apiPaths.auth.me,
            method: MTD.PATCH,
            body: {
              fullname: fullname.trim(),
              phone: phone.replace(/\s/g, "") || null,
              telegram_username: telegram.trim() ? cleanTelegram(telegram) : null,
              preferred_sub_city: subCity || null,
            },
          });
          setMessage({ ok: true, text: "Saved." });
        } catch (err) {
          setMessage({ ok: false, text: getErrorMessage(err) });
        }
      }}
    >
      <Field label="Full name" htmlFor="fullname" required>
        <Input id="fullname" value={fullname} onChange={(e) => setFullname(e.target.value)} required minLength={2} />
      </Field>
      <Field label="Email" htmlFor="email" hint="Contact an administrator to change your email.">
        <Input id="email" value={user.email} disabled />
      </Field>
      <Field label="Phone" htmlFor="phone">
        <Input id="phone" type="tel" placeholder="09XXXXXXXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </Field>
      <Field label="Telegram username" htmlFor="telegram" hint="Shared with a provider only after they accept your request.">
        <Input id="telegram" placeholder="@your_username" value={telegram} onChange={(e) => setTelegram(e.target.value)} />
      </Field>
      <Field label="My sub-city" htmlFor="sub-city" hint="Used to pre-fill your paths.">
        <NativeSelect id="sub-city" value={subCity} onChange={(e) => setSubCity(e.target.value)}>
          <SubCityOptions placeholder="Not set" />
        </NativeSelect>
      </Field>
      <div className="flex items-center gap-3 sm:col-span-2">
        <Button type="submit" loading={update.isPending}>
          Save profile
        </Button>
        {message && <p className={message.ok ? "text-primary text-sm" : "text-destructive text-sm"}>{message.text}</p>}
      </div>
    </form>
  );
}

function PasswordForm({ onChanged }: { onChanged: () => void }) {
  const change = useChangePassword();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  if (!open) {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={() => setOpen(true)}>Change password</Button>
        <p className="text-muted-foreground text-xs">You need your current password. Other devices are signed out after a change.</p>
        {message?.ok && <p className="text-primary text-sm">{message.text}</p>}
      </div>
    );
  }

  return (
    <form
      className="grid max-w-md gap-4"
      onSubmit={async (e) => {
        e.preventDefault();
        setMessage(null);
        if (!passwordIsValid(next)) return setMessage({ ok: false, text: "The new password doesn’t meet the rules." });
        try {
          const res = await change.mutateAsync({
            url: apiPaths.auth.changePassword,
            method: MTD.POST,
            body: { current_password: current, new_password: next },
          });
          const others = res.payload.otherSessionsSignedOut;
          setMessage({ ok: true, text: `Password changed.${others ? ` Signed out ${others} other device${others > 1 ? "s" : ""}.` : ""}` });
          setCurrent("");
          setNext("");
          setOpen(false);
          onChanged();
        } catch (err) {
          setMessage({ ok: false, text: getErrorMessage(err) });
        }
      }}
    >
      <Field label="Current password" htmlFor="current-password" required>
        <PasswordInput id="current-password" value={current} onChange={setCurrent} autoComplete="current-password" locked />
      </Field>
      <Field label="New password" htmlFor="new-password" required>
        <PasswordInput id="new-password" value={next} onChange={setNext} autoComplete="new-password" showRules locked />
      </Field>
      <div className="flex items-center gap-3">
        <Button type="submit" loading={change.isPending}>
          Save new password
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setCurrent("");
            setNext("");
            setMessage(null);
            setOpen(false);
          }}
        >
          Cancel
        </Button>
        {message && <p className={message.ok ? "text-primary text-sm" : "text-destructive text-sm"}>{message.text}</p>}
      </div>
    </form>
  );
}

function SessionsList({ sessions, onRevoked }: { sessions: AuthSession[]; onRevoked: () => void }) {
  const revoke = useRevokeSession();
  return (
    <ul className="divide-border divide-y">
      {sessions.map((s) => (
        <li key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div>
            <p className="text-sm font-medium">
              {deviceLabel(s.user_agent)}
              {s.current && <span className="bg-secondary text-primary ml-2 rounded px-1.5 py-0.5 text-xs font-semibold">This device</span>}
            </p>
            <p className="text-muted-foreground text-xs">
              Signed in {formatDateTime(s.created_at)} · last active {formatDateTime(s.last_used_at)}
              {s.ip ? ` · ${s.ip}` : ""}
            </p>
          </div>
          {!s.current && (
            <Button
              size="sm"
              variant="outline"
              onClick={async () => {
                await revoke.mutateAsync({ url: apiPaths.auth.session(s.id), method: MTD.DELETE });
                onRevoked();
              }}
            >
              Sign out
            </Button>
          )}
        </li>
      ))}
    </ul>
  );
}

function ActivityList({ events }: { events: AuthEvent[] }) {
  if (!events.length) return <p className="text-muted-foreground text-sm">No activity yet.</p>;
  return (
    <ul className="space-y-2 text-sm">
      {events.map((e) => (
        <li key={e.id} className="flex flex-wrap justify-between gap-2">
          <span className={/failed|blocked|reuse/.test(e.event) ? "text-destructive" : undefined}>
            {EVENT_LABEL[e.event] ?? e.event.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())}
            <span className="text-muted-foreground"> · {deviceLabel(e.user_agent)}</span>
          </span>
          <span className="text-muted-foreground text-xs">{formatDateTime(e.created_at)}</span>
        </li>
      ))}
    </ul>
  );
}

type SecurityView = "devices" | "activity";

/**
 * Devices and security activity both grow long, so they sit side by side as two tabs,
 * each paged on its own. The open tab and page live in the URL (?view=activity&page=2).
 */
function SecurityHistory({ onChanged }: { onChanged: () => void }) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const view: SecurityView = params.get("view") === "activity" ? "activity" : "devices";
  const [page, setPage] = useUrlPage();
  const sessions = useMySessions(view === "devices" ? page : 0);
  const activity = useMyActivity(view === "activity" ? page : 0);
  const { logout, isLoggingOut } = useLogout();

  const setView = (next: SecurityView) => {
    const sp = new URLSearchParams(window.location.search);
    sp.delete("page");
    if (next === "activity") sp.set("view", "activity");
    else sp.delete("view");
    router.replace(`${pathname}?${sp.toString()}`, { scroll: false });
  };
  const tabs = [
    { key: "devices" as const, label: "Where you’re signed in", am: "የገቡባቸው መሳሪያዎች", count: sessions.data?.payload.total },
    { key: "activity" as const, label: "Recent security activity", am: "የቅርብ ጊዜ እንቅስቃሴ", count: activity.data?.payload.total },
  ];
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const next = view === "devices" ? "activity" : "devices";
    setView(next);
    document.getElementById(`security-tab-${next}`)?.focus();
  };

  return (
    <section className="border-border bg-card rounded-md border">
      <div role="tablist" aria-label="Security history" className="border-border grid grid-cols-2 border-b">
        {tabs.map((t) => {
          const active = t.key === view;
          return (
            <button
              key={t.key}
              id={`security-tab-${t.key}`}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls="security-panel"
              tabIndex={active ? 0 : -1}
              onClick={() => setView(t.key)}
              onKeyDown={onKeyDown}
              className={cn(
                "-mb-px flex flex-col items-start gap-0.5 border-b-[3px] px-4 py-3 text-left text-sm sm:flex-row sm:items-center sm:gap-2",
                active ? "border-primary text-gov-ink font-semibold" : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              <span>{t.label}</span>
              <span className="text-muted-foreground text-xs font-normal">
                {t.am}
                {t.count != null && <span className="tabular-nums"> · {t.count}</span>}
              </span>
            </button>
          );
        })}
      </div>
      <div role="tabpanel" id="security-panel" aria-labelledby={`security-tab-${view}`} className="p-5">
        {view === "devices" ? (
          <>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-muted-foreground text-sm">Sign out any device you don&apos;t recognise.</p>
              <Button size="sm" variant="outline" loading={isLoggingOut} onClick={() => logout(true)}>
                Sign out everywhere
              </Button>
            </div>
            {sessions.data ? <SessionsList sessions={sessions.data.payload.sessions} onRevoked={onChanged} /> : <LoadingState />}
            <Pager className="mt-4" page={page} pageSize={SECURITY_PAGE_SIZE} total={sessions.data?.payload.total ?? 0} onPage={setPage} />
          </>
        ) : (
          <>
            {activity.data ? <ActivityList events={activity.data.payload.events} /> : <LoadingState />}
            <Pager className="mt-4" page={page} pageSize={SECURITY_PAGE_SIZE} total={activity.data?.payload.total ?? 0} onPage={setPage} />
          </>
        )}
      </div>
    </section>
  );
}

type AccountTab = "profile" | "security";

export function AccountPage() {
  const gate = useRequireAuth();
  const user = useUserStore((s) => s.user);
  const queryClient = useQueryClient();
  const isProvider = !!useMyProvider(gate === "ready").data?.payload.provider;
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: AccountTab = params.get("tab") === "security" ? "security" : "profile";
  const setTab = (t: AccountTab) => router.replace(t === "security" ? `${pathname}?tab=security` : pathname, { scroll: false });

  if (gate === "loading" || !user) {
    return (
      <PageShell title="My account · የእኔ መለያ" maxWidth="lg">
        <LoadingState />
      </PageShell>
    );
  }

  // A password change or a signed-out device shows up in both lists, on every page
  const refetchAll = () => void queryClient.invalidateQueries({ queryKey: ["auth"] });
  const link = "border-border hover:border-primary rounded-md border px-3 py-1.5";

  return (
    <PageShell title="My account · የእኔ መለያ" description={`Signed in as ${user.email}`} maxWidth="lg">
      <nav aria-label="My pages" className="mb-6 flex flex-wrap gap-2 text-sm">
        <Link href="/account/requests" className={link}>My hires</Link>
        <Link href="/account/paths" className={link}>My saved paths</Link>
        <Link href="/account/support" className={link}>My support requests</Link>
        <Link href="/org" className={link}>My organization</Link>
        {isProvider && (
          <>
            <Link href="/me/provider" className={link}>My provider profile</Link>
            <Link href="/me/provider?tab=earnings" className={link}>Earnings</Link>
          </>
        )}
      </nav>

      <div role="tablist" aria-label="Account" className="border-border mb-6 flex gap-1 border-b">
        {([
          ["profile", "Profile · መገለጫ"],
          ["security", "Security · ደህንነት"],
        ] as const).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cn(
              "-mb-px border-b-[3px] px-4 py-2.5 text-sm",
              tab === key ? "border-primary text-primary font-semibold" : "text-muted-foreground hover:text-foreground border-transparent",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "profile" ? (
        <div className="space-y-6">
          <Section title="Profile" am="መገለጫ">
            <ProfileForm />
          </Section>
          <Section title="Legal" am="ሕጋዊ ስምምነቶች">
            <MyAgreements />
          </Section>
        </div>
      ) : (
        <div className="space-y-6">
          <Section title="Password" am="የይለፍ ቃል">
            <PasswordForm onChanged={refetchAll} />
          </Section>

          <SecurityHistory onChanged={refetchAll} />
        </div>
      )}
    </PageShell>
  );
}

