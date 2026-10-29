"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAcceptLegal, useLegalStatus } from "@cn/core/api/legal";
import { useLogout } from "@cn/core/api/auth";
import { getErrorMessage } from "@cn/core/lib/errors";
import { useUserStore } from "@cn/core/store/user-store";
import { Button } from "@cn/ui/button";
import { FormError } from "@cn/ui/auth/auth-card";
import { formatLegalDate } from "@/content/legal";
import { LegalCheckbox } from "@/modules/legal/components/legal-checkbox";

/**
 * Blocks the site for a signed-in person who has not accepted the current version of a document
 * they must accept (new Terms, or the Provider Agreement for providers). They accept or sign out.
 * The legal pages themselves stay readable.
 */
export function LegalGate() {
  const pathname = usePathname();
  const signedIn = useUserStore((s) => s.status === "authenticated");
  const userId = useUserStore((s) => s.user?.id);
  const status = useLegalStatus(signedIn);
  const { accept, isAccepting } = useAcceptLegal();
  const { logout, isLoggingOut } = useLogout();
  const [checked, setChecked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);

  const data = status.data?.payload;
  const pending = data?.documents.filter((d) => !d.accepted) ?? [];
  // A different person signing in on this tab must not see the previous person's answer
  const fresh = !!data && !status.isPlaceholderData;
  const open = signedIn && !!userId && fresh && pending.length > 0 && !pathname.startsWith("/legal");

  useEffect(() => {
    if (!open) return;
    const root = dialog.current;
    root?.querySelector<HTMLElement>("input, button, a")?.focus();
    // Keep keyboard focus inside the dialog; there is nothing behind it to use until they answer
    const trap = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !root) return;
      const items = Array.from(root.querySelectorAll<HTMLElement>("a, button:not([disabled]), input"));
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      } else if (!root.contains(document.activeElement)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", trap);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", trap);
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;
  const isUpdate = pending.some((d) => d.key !== "provider_agreement");

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center bg-black/60 sm:items-center sm:p-4">
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="legal-gate-title"
        aria-describedby="legal-gate-desc"
        className="bg-background max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-xl p-5 shadow-xl sm:rounded-xl"
      >
        <p className="text-xs font-semibold tracking-wide text-amber-700 uppercase">
          {isUpdate ? "Updated terms · የተሻሻሉ ውሎች" : "One more step · አንድ ተጨማሪ ደረጃ"}
        </p>
        <h2 id="legal-gate-title" className="text-gov-ink mt-1 text-lg font-bold">
          {isUpdate ? "We have updated our terms" : "Please accept the agreement to continue"}
        </h2>
        <p id="legal-gate-desc" className="text-muted-foreground mt-1 text-sm">
          To keep using your account, read and accept the documents below. Each opens in a new tab. If you do not agree,
          you can sign out and ask us to close your account.
        </p>

        <ul className="border-border mt-4 divide-y rounded-md border">
          {pending.map((d) => (
            <li key={d.key} className="px-4 py-3 text-sm">
              <a href={d.path} target="_blank" rel="noopener noreferrer" className="text-primary font-medium underline">
                {d.title}
                <span className="sr-only"> (opens in a new tab)</span>
              </a>
              <p className="text-muted-foreground mt-0.5 text-xs">
                Version {d.version} · Effective {formatLegalDate(d.effective)}
              </p>
            </li>
          ))}
        </ul>

        <form
          className="mt-4 space-y-4"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!checked) return setError("Tick the box to accept, or sign out.");
            setError(null);
            try {
              await accept(Object.fromEntries(pending.map((d) => [d.key, d.version])));
              setChecked(false);
            } catch (err) {
              setError(getErrorMessage(err, "Could not save your answer. Try again."));
              void status.refetch();
            }
          }}
        >
          <LegalCheckbox id="legal-gate-accept" checked={checked} onChange={setChecked} invalid={!!error}>
            I have read and agree to {pending.length === 1 ? "this document" : "these documents"}.
          </LegalCheckbox>
          <FormError message={error} />
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button type="button" variant="ghost" loading={isLoggingOut} onClick={() => void logout()}>
              Sign out
            </Button>
            <Button type="submit" loading={isAccepting}>
              Accept and continue
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
