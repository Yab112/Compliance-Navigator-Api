"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { apiPaths } from "@/lib/constants/api-paths";
import { broadcastAuth, endSession, postAuth } from "@/lib/auth-session";
import { getErrorMessage } from "@/lib/errors";
import { AuthCard, FormError } from "../components/auth-card";
import { PasswordInput, passwordIsValid } from "../components/password-input";

export function ResetPassword() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthCard
      title="Choose a new password"
      am="አዲስ የይለፍ ቃል"
      description="After the change you’ll be signed out everywhere and can sign in with the new password."
      footer={
        <p>
          <Link href="/forgot-password" className="text-primary underline">
            Request a new link
          </Link>
        </p>
      }
    >
      {!token ? (
        <FormError message="This page needs the link from your email. Request a new one." />
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setError(null);
            if (!passwordIsValid(password)) return setError("The password doesn’t meet the rules below.");
            if (password !== confirm) return setError("The two passwords don’t match.");
            setPending(true);
            try {
              await postAuth(apiPaths.auth.resetPassword, { token, new_password: password });
              endSession();
              broadcastAuth({ type: "signed-out" });
              router.replace("/login?reset=1");
            } catch (err) {
              setError(getErrorMessage(err));
            } finally {
              setPending(false);
            }
          }}
        >
          <div className="flex flex-col gap-2">
            <Label htmlFor="password">New password</Label>
            <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="new-password" showRules />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="confirm">Repeat new password</Label>
            <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" />
          </div>
          <FormError message={error} />
          <Button type="submit" size="lg" loading={pending}>
            Save new password
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
