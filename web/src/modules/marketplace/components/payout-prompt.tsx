"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { usePaymentsConfig } from "@cn/core/api/payments";
import { useMarketAction, useMyProvider } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { MTD } from "@cn/core/lib/constants/methods";
import { apiPaths } from "@cn/core/lib/constants/api-paths";
import { getErrorMessage } from "@cn/core/lib/errors";
import { cleanTelegram, TELEGRAM_HINT, TELEGRAM_RE } from "@/lib/telegram";
import { usePayoutPromptStore, useUserStore } from "@/store";
import { PayoutCard } from "@/modules/marketplace/components/payout-card";

const SEEN_KEY = "cn-payout-prompt:";
const QUIET_PAGES = ["/login", "/register", "/forgot-password", "/reset-password"];

function TelegramForm() {
  const { run, isPending } = useMarketAction<{ telegram_username: string }>();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  return (
    <form
      className="border-border bg-card rounded-md border p-4"
      onSubmit={async (e) => {
        e.preventDefault();
        const username = cleanTelegram(value);
        if (!TELEGRAM_RE.test(username)) return setError(TELEGRAM_HINT);
        setError(null);
        try {
          await run(apiPaths.providers.me, MTD.PATCH, { telegram_username: username });
        } catch (err) {
          setError(getErrorMessage(err));
        }
      }}
    >
      <label htmlFor="setup-telegram" className="text-sm font-semibold">Telegram username · ቴሌግራም</label>
      <p className="text-muted-foreground mt-0.5 text-xs">Clients message you here once you accept their request.</p>
      <div className="mt-2 flex gap-2">
        <Input id="setup-telegram" placeholder="@your_username" value={value} onChange={(e) => setValue(e.target.value)} />
        <Button type="submit" size="sm" loading={isPending} disabled={!value.trim()}>Save</Button>
      </div>
      {error && <p className="text-destructive mt-1 text-xs">{error}</p>}
    </form>
  );
}

/**
 * What a provider needs before clients can work with them: Telegram (to be messaged) and a payout
 * account (to be paid online). Asked once per browser session after sign-in; job cards reopen it.
 */
export function PayoutPrompt() {
  const pathname = usePathname();
  const user = useUserStore((s) => s.user);
  const signedIn = useUserStore((s) => s.status === "authenticated");
  const { open, show, hide } = usePayoutPromptStore();
  const config = usePaymentsConfig();
  const paymentsOn = config.data?.payload.enabled ?? false;
  const provider = useMyProvider(signedIn).data?.payload.provider ?? null;
  const approved = !!provider && provider.status === "approved";
  const needsPayout = approved && paymentsOn && !provider?.payout?.ready;
  const needsTelegram = approved && !provider?.telegram_username;
  const needsSetup = needsPayout || needsTelegram;
  const dialog = useRef<HTMLDivElement>(null);

  // Once per session: sessionStorage is cleared when the tab closes or the person signs out
  useEffect(() => {
    if (!needsSetup || !user || QUIET_PAGES.some((p) => pathname.startsWith(p))) return;
    try {
      if (sessionStorage.getItem(SEEN_KEY + user.id)) return;
      sessionStorage.setItem(SEEN_KEY + user.id, "1");
    } catch {
      return;
    }
    show();
  }, [needsSetup, user, pathname, show]);

  useEffect(() => {
    if (!open) return;
    const esc = (e: KeyboardEvent) => e.key === "Escape" && hide();
    document.addEventListener("keydown", esc);
    dialog.current?.querySelector<HTMLElement>("select, input, button")?.focus();
    return () => document.removeEventListener("keydown", esc);
  }, [open, hide]);

  if (!open || !provider) return null;
  const ready = !needsSetup;

  return (
    <div className="fixed inset-0 z-[70] flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-4" onClick={hide}>
      <div
        ref={dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby="payout-prompt-title"
        onClick={(e) => e.stopPropagation()}
        className="bg-background max-h-[92dvh] w-full max-w-xl overflow-y-auto rounded-t-xl p-5 shadow-xl sm:rounded-xl"
      >
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold tracking-wide text-amber-700 uppercase">
              {ready ? "You're all set" : "Finish your profile"}
            </p>
            <h2 id="payout-prompt-title" className="text-gov-ink mt-1 text-lg font-bold">
              {ready
                ? "Clients can message you, and you can withdraw your earnings"
                : `Finish setting up, ${provider.display_name.split(" ")[0]}`}
            </h2>
            {!ready && (
              <p className="text-muted-foreground mt-1 text-sm">
                {needsTelegram && "Clients message you on Telegram once you accept. "}
                {needsPayout && "Clients pay through Compliance Navigator and the money is added to your earnings. Add your bank account so you can withdraw it."}
              </p>
            )}
          </div>
          <button type="button" onClick={hide} aria-label="Close" className="text-muted-foreground hover:text-foreground text-xl leading-none">
            ×
          </button>
        </div>
        <div className="space-y-3">
          {needsTelegram && <TelegramForm />}
          {provider.telegram_username && (
            <p className="text-primary text-sm font-medium">✓ Telegram: @{provider.telegram_username}</p>
          )}
          <PayoutCard />
        </div>
        <div className="mt-4 flex justify-end">
          <Button variant={ready ? "default" : "ghost"} onClick={hide}>
            {ready ? "Done" : "Later"}
          </Button>
        </div>
      </div>
    </div>
  );
}
