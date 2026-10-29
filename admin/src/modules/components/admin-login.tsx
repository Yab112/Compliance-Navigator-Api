"use client";

import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useLogin } from "@cn/core/api/auth";
import { useRedirectIfSignedIn } from "@cn/core/hooks/use-redirect-if-signed-in";
import { getErrorMessage } from "@cn/core/lib/errors";
import { safeReturnTo } from "@cn/core/lib/safe-redirect";
import { AuthCard, FormError } from "@cn/ui/auth/auth-card";
import { PasswordInput } from "@cn/ui/auth/password-input";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";

/** Staff sign-in. Accounts are the same as on the public site; only admins get past the guard. */
export function AdminLogin() {
  const searchParams = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get("returnTo"), "/");
  const { login, isLoggingIn } = useLogin();
  const [submitted, setSubmitted] = useState(false);
  useRedirectIfSignedIn(submitted ? "" : returnTo);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthCard
      title="Staff sign in"
      am="የሰራተኛ መግቢያ"
      description="For Compliance Navigator staff. Use your usual account; it needs the admin role."
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          setSubmitted(true);
          try {
            await login({ email: email.trim(), password }, returnTo);
          } catch (err) {
            setSubmitted(false);
            setError(getErrorMessage(err, "Could not sign in. Try again."));
          }
        }}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </div>
        <FormError message={error} />
        <Button type="submit" size="lg" loading={isLoggingIn}>
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
