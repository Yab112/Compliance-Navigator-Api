"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { postAuth } from "@cn/core/lib/auth-session";
import { getErrorMessage } from "@cn/core/lib/errors";
import { useUserStore } from "@cn/core/store/user-store";
import type { User } from "@cn/core/types/user-types";
import { AuthCard, FormError } from "@cn/ui/auth/auth-card";

type State = { kind: "working" } | { kind: "done" } | { kind: "failed"; message: string };

/** Opened from the link in the sign-up email. The link works once, so it is sent to the server exactly once. */
export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const [state, setState] = useState<State>(token ? { kind: "working" } : { kind: "failed", message: "This page needs the link from your email." });
  const sent = useRef(false);
  const signedIn = useUserStore((s) => s.status === "authenticated");

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    postAuth<{ user: User }>(apiPaths.auth.verifyEmail, { token })
      .then(({ user }) => {
        // Update the banner straight away when this browser is signed in to the same account
        const { user: current, setUser } = useUserStore.getState();
        if (current && current.id === user.id) setUser({ ...current, emailVerified: true });
        setState({ kind: "done" });
      })
      .catch((err) => setState({ kind: "failed", message: getErrorMessage(err, "This link is invalid or has expired.") }));
  }, [token]);

  return (
    <AuthCard
      title="Confirm your email"
      am="ኢሜይልዎን ያረጋግጡ"
      footer={
        <p>
          <Link href={signedIn ? "/account" : "/login"} className="text-primary font-medium underline">
            {signedIn ? "Go to my account" : "Sign in"}
          </Link>
        </p>
      }
    >
      <div className="space-y-3 text-sm" role="status" aria-live="polite">
        {state.kind === "working" && <p className="text-muted-foreground">Confirming your email…</p>}
        {state.kind === "done" && (
          <p className="border-primary/30 bg-secondary text-primary rounded-md border px-3 py-2">
            Thank you, your email is confirmed. You can now offer services as a provider, create or join an organization, and
            receive payouts.
          </p>
        )}
        {state.kind === "failed" && (
          <>
            <FormError message={state.message} />
            <p className="text-muted-foreground">
              Sign in and use <strong>Send a new link</strong> in the notice at the top of the page.
            </p>
          </>
        )}
      </div>
    </AuthCard>
  );
}
