"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";
import { useResendVerification } from "@cn/core/api/auth";
import { MTD } from "@cn/core/lib/constants/methods";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { useUserStore } from "@cn/core/store/user-store";

const QUIET_PAGES = ["/verify-email", "/login", "/register", "/forgot-password", "/reset-password"];

/** Shown to signed-in people until they open the confirmation link we emailed after sign-up. */
export function VerifyEmailBanner() {
  const pathname = usePathname();
  const user = useUserStore((s) => s.user);
  const signedIn = useUserStore((s) => s.status === "authenticated");
  const resend = useResendVerification();
  const [note, setNote] = useState<string | null>(null);

  if (!signedIn || !user || user.emailVerified !== false || QUIET_PAGES.includes(pathname)) return null;

  return (
    <div className="border-gov-yellow bg-secondary/70 border-b-4 px-4 py-2.5 text-sm" role="region" aria-label="Confirm your email">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-3 gap-y-1.5">
        <p className="min-w-0 flex-1">
          <strong>Confirm your email · ኢሜይልዎን ያረጋግጡ.</strong> We sent a link to <span className="break-all">{user.email}</span>.
          Until you open it, you can&apos;t offer services, create or join an organization, or receive payouts.
        </p>
        <button
          type="button"
          className="text-primary shrink-0 font-semibold underline disabled:opacity-60"
          disabled={resend.isPending}
          onClick={async () => {
            setNote(null);
            try {
              const res = await resend.mutateAsync({ url: apiPaths.auth.resendVerification, method: MTD.POST });
              if (res.payload.alreadyVerified) {
                useUserStore.getState().setUser({ ...user, emailVerified: true });
              } else {
                setNote("A new link is on its way. It works for 48 hours.");
              }
            } catch (err) {
              setNote(getErrorMessage(err, "Could not send a new link. Try again later."));
            }
          }}
        >
          {resend.isPending ? "Sending…" : "Send a new link"}
        </button>
        <p className="w-full text-xs" aria-live="polite">{note}</p>
      </div>
    </div>
  );
}
