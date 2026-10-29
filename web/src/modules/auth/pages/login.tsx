"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/api/auth";
import { getErrorMessage } from "@/lib/errors";
import { safeReturnTo } from "@/lib/safe-redirect";
import { useRedirectIfSignedIn } from "@/hooks/use-redirect-if-signed-in";
import { AuthCard, FormError } from "../components/auth-card";
import { PasswordInput } from "../components/password-input";

export function Login() {
  const searchParams = useSearchParams();
  const returnTo = safeReturnTo(searchParams.get("returnTo"));
  const resetDone = searchParams.get("reset") === "1";
  const { login, isLoggingIn } = useLogin();
  const [submitted, setSubmitted] = useState(false);
  // useLogin navigates itself after a submit; this covers arriving here already signed in
  useRedirectIfSignedIn(submitted ? "" : returnTo);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthCard
      title="Sign in"
      am="ይግቡ"
      description="Save your paths, follow your requests and manage your organization or provider profile."
      footer={
        <>
          <p>
            New here?{" "}
            <Link href={`/register?returnTo=${encodeURIComponent(returnTo)}`} className="text-primary font-medium underline">
              Create a free account
            </Link>
          </p>
          <p>
            <Link href="/" className="hover:underline">
              Continue without signing in
            </Link>
          </p>
        </>
      }
    >
      {resetDone && (
        <p className="border-primary/30 bg-secondary text-primary mb-4 rounded-md border px-3 py-2 text-sm">
          Your password was changed. Sign in with the new one.
        </p>
      )}
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
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-primary text-xs hover:underline">
              Forgot password?
            </Link>
          </div>
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
