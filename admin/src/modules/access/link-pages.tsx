"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getErrorMessage } from "@cn/core/lib/errors";
import { checkStaffLink, redeemStaffLink, requestStaffReset } from "@cn/core/lib/staff-session";
import { AuthCard, FormError } from "@cn/ui/auth/auth-card";
import { PasswordInput, passwordIsValid } from "@cn/ui/auth/password-input";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";

/** Invitation (choose your first password) and password reset: both use a one-time link. */
export function SetPasswordPage({ kind }: { kind: "invite" | "reset" }) {
  const token = useSearchParams().get("token") ?? "";
  const [email, setEmail] = useState<string | null>(null);
  const [linkError, setLinkError] = useState<string | null>(token ? null : "This link is missing its code.");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) return;
    checkStaffLink(token, kind)
      .then((r) => setEmail(r.email))
      .catch((e) => setLinkError(getErrorMessage(e, "This link is invalid, already used or has expired.")));
  }, [token, kind]);

  const title = kind === "invite" ? "Set up your staff account" : "Choose a new password";
  const am = kind === "invite" ? "የሰራተኛ መለያዎን ያዘጋጁ" : "አዲስ የይለፍ ቃል ይምረጡ";

  if (done) {
    return (
      <AuthCard title="Password saved" am="የይለፍ ቃል ተቀምጧል" description={`You can now sign in as ${email ?? "staff"}.`}>
        <Link href="/login">
          <Button size="lg" className="w-full">
            Go to sign in
          </Button>
        </Link>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title={title}
      am={am}
      description={
        linkError
          ? undefined
          : kind === "invite"
            ? "Choose the password you will use to sign in to the staff workspace."
            : "Choose a new password. Every device signed in to your staff account will be signed out."
      }
      footer={
        <Link href="/login" className="text-primary hover:underline">
          Back to sign in
        </Link>
      }
    >
      {linkError ? (
        <FormError message={`${linkError} Ask a Super admin to send a new link.`} />
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setError(null);
            if (!passwordIsValid(password)) return setError("The password doesn't meet the rules below.");
            if (password !== confirm) return setError("The two passwords don't match.");
            setPending(true);
            try {
              await redeemStaffLink(kind, token, password);
              setDone(true);
            } catch (err) {
              setError(getErrorMessage(err, "Could not save the password."));
            } finally {
              setPending(false);
            }
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Sign-in email</Label>
            <Input id="email" value={email ?? ""} readOnly autoComplete="username" />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="new-password">New password</Label>
            <PasswordInput id="new-password" value={password} onChange={setPassword} autoComplete="new-password" showRules />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm-password">Type it again</Label>
            <PasswordInput id="confirm-password" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          </div>
          <FormError message={error} />
          <Button type="submit" size="lg" loading={pending} disabled={!email}>
            Save password
          </Button>
        </form>
      )}
    </AuthCard>
  );
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <AuthCard
      title="Forgot your password?"
      am="የይለፍ ቃልዎን ረስተዋል?"
      description={
        sent
          ? "If that email belongs to an active staff account, a reset link is on its way. It works once, for 60 minutes."
          : "Enter your staff email and we will send you a link to choose a new password."
      }
      footer={
        <Link href="/login" className="text-primary hover:underline">
          Back to sign in
        </Link>
      }
    >
      {!sent && (
        <form
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setError(null);
            setPending(true);
            try {
              await requestStaffReset(email.trim());
              setSent(true);
            } catch (err) {
              setError(getErrorMessage(err, "Could not send the link. Try again."));
            } finally {
              setPending(false);
            }
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Staff email</Label>
            <Input id="email" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <FormError message={error} />
          <Button type="submit" size="lg" loading={pending}>
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
