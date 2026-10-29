"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiPaths } from "@/lib/constants/api-paths";
import { postAuth } from "@/lib/auth-session";
import { getErrorMessage } from "@/lib/errors";
import { AuthCard, FormError } from "../components/auth-card";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <AuthCard
      title="Forgot your password?"
      am="የይለፍ ቃል ረስተዋል?"
      footer={
        <p>
          <Link href="/login" className="text-primary font-medium underline">
            Back to sign in
          </Link>
        </p>
      }
    >
      {sent ? (
        <div className="space-y-3 text-sm">
          <p className="border-primary/30 bg-secondary text-primary rounded-md border px-3 py-2">
            If an account exists for <strong>{email}</strong>, we sent a link to reset the password. It works for one hour.
          </p>
          <p className="text-muted-foreground">
            No email? Check spam, or ask a portal administrator to issue a reset link for you.
          </p>
        </div>
      ) : (
        <form
          className="flex flex-col gap-4"
          onSubmit={async (e) => {
            e.preventDefault();
            setError(null);
            setPending(true);
            try {
              await postAuth(apiPaths.auth.forgotPassword, { email: email.trim() });
              setSent(true);
            } catch (err) {
              setError(getErrorMessage(err));
            } finally {
              setPending(false);
            }
          }}
        >
          <p className="text-muted-foreground text-sm">Enter your account email and we’ll send you a reset link.</p>
          <div className="flex flex-col gap-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
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
