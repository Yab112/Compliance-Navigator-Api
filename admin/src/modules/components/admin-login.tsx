"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRedirectIfSignedIn } from "@cn/core/hooks/use-redirect-if-signed-in";
import { getErrorMessage } from "@cn/core/lib/errors";
import { safeReturnTo } from "@cn/core/lib/safe-redirect";
import { staffLogin } from "@cn/core/lib/staff-session";
import { AuthCard, FormError } from "@cn/ui/auth/auth-card";
import { PasswordInput } from "@cn/ui/auth/password-input";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";

/** Staff sign-in. Staff accounts are separate from public accounts and are created by invitation. */
export function AdminLogin() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const returnTo = safeReturnTo(searchParams.get("returnTo"), "/");
  const [submitted, setSubmitted] = useState(false);
  useRedirectIfSignedIn(submitted ? "" : returnTo);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  return (
    <AuthCard
      title="Staff sign in"
      am="የሰራተኛ መግቢያ"
      description="For Compliance Navigator staff only. Use the staff account you were invited to; public site accounts don't work here."
      footer={
        <Link href="/forgot-password" className="text-primary hover:underline">
          Forgot your password?
        </Link>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          setSubmitted(true);
          setPending(true);
          try {
            await staffLogin(email.trim(), password);
            await queryClient.invalidateQueries();
            router.push(returnTo);
          } catch (err) {
            setSubmitted(false);
            setError(getErrorMessage(err, "Could not sign in. Try again."));
          } finally {
            setPending(false);
          }
        }}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </div>
        <FormError message={error} />
        <Button type="submit" size="lg" loading={pending}>
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
