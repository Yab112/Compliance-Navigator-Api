"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useFaydaActions } from "@/api/guday";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { getErrorMessage } from "@cn/core/lib/errors";
import { useUserStore } from "@/store";
import { Field, LoadingState } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { FAYDA_RETURN_KEY } from "@/modules/marketplace/components/fayda-step";

const DEFAULT_BACK = "/providers/join";

/** Where verification started (saved by the Verify step), so the user returns to the same step. */
function useBack(): string {
  return useSyncExternalStore(
    () => () => {},
    () => {
      try {
        const saved = sessionStorage.getItem(FAYDA_RETURN_KEY);
        return saved && saved.startsWith("/") && !saved.startsWith("//") ? saved : DEFAULT_BACK;
      } catch {
        return DEFAULT_BACK;
      }
    },
    () => DEFAULT_BACK,
  );
}

/**
 * Stand-in for the Fayda (eSignet) sign-in screen while FAYDA_MODE=sandbox.
 * Deliberately looks like a test page so nobody mistakes it for the real service.
 */
export function FaydaSandboxPage() {
  const router = useRouter();
  const params = useSearchParams();
  const gate = useAuthGate();
  const BACK = useBack();
  const user = useUserStore((s) => s.user);
  const { completeSandbox, isPending } = useFaydaActions();
  const state = params.get("state") ?? "";
  const [idNumber, setIdNumber] = useState("");
  const [name, setName] = useState("");
  const [otp, setOtp] = useState("");
  const [gender, setGender] = useState<"" | "Male" | "Female">("");
  const [error, setError] = useState<string | null>(null);

  if (gate === "loading") return <LoadingState />;
  const digits = idNumber.replace(/\D/g, "");

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <div className="mb-6 border-2 border-dashed border-amber-500 bg-amber-50 p-4 text-center text-amber-900">
        <p className="text-sm font-bold tracking-wide">TEST MODE: not the real Fayda service</p>
        <p className="mt-1 text-xs">
          Nothing here is checked against the National ID database. The one-time code is always{" "}
          <span className="font-mono font-bold">111111</span>.
        </p>
      </div>
      <div className="border-border bg-card rounded-md border p-6">
        <p className="text-muted-foreground text-xs font-semibold tracking-widest uppercase">Fayda · ፋይዳ (sandbox)</p>
        <h1 className="mt-1 text-xl font-bold">Share your identity with Compliance Navigator</h1>
        <p className="text-muted-foreground mt-2 text-sm">Signed in as {user?.email}</p>
        {!state ? (
          <p className="text-destructive mt-6 text-sm">
            This page needs a verification request. <Link href={BACK} className="underline">Start again</Link>.
          </p>
        ) : (
          <form
            className="mt-6 space-y-4"
            onSubmit={async (e) => {
              e.preventDefault();
              setError(null);
              if (digits.length !== 12 && digits.length !== 16) return setError("Enter a 12-digit FIN or 16-digit FCN");
              if (name.trim().length < 3) return setError("Enter the full name on your ID");
              try {
                await completeSandbox({
                  state,
                  id_number: digits,
                  full_name: name.trim(),
                  otp: otp.trim(),
                  gender: gender || undefined,
                });
                router.replace(BACK);
              } catch (err) {
                setError(getErrorMessage(err, "Verification failed"));
              }
            }}
          >
            <Field label="Fayda number (FIN or FCN)" htmlFor="fy-id" required>
              <Input id="fy-id" inputMode="numeric" value={idNumber} onChange={(e) => setIdNumber(e.target.value)} placeholder="12 or 16 digits" />
            </Field>
            <Field label="Full name as on the ID" htmlFor="fy-name" required>
              <Input id="fy-name" value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Gender" htmlFor="fy-gender">
              <select
                id="fy-gender"
                className="border-input bg-background h-8 w-full border px-2 text-sm"
                value={gender}
                onChange={(e) => setGender(e.target.value as typeof gender)}
              >
                <option value="">Not specified</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </Field>
            <Field label="One-time code (OTP)" htmlFor="fy-otp" required hint="Test mode code: 111111">
              <Input id="fy-otp" inputMode="numeric" value={otp} onChange={(e) => setOtp(e.target.value)} />
            </Field>
            {error && <p className="text-destructive text-sm">{error}</p>}
            <div className="flex gap-3 pt-2">
              <Button type="submit" size="lg" loading={isPending}>
                Verify & share
              </Button>
              <Link href={BACK}>
                <Button type="button" variant="outline" size="lg">
                  Cancel
                </Button>
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

/** Fayda redirects here with ?code&state (or ?error) after the user consents. */
export function FaydaCallbackPage() {
  const router = useRouter();
  const params = useSearchParams();
  const gate = useAuthGate();
  const BACK = useBack();
  const { complete } = useFaydaActions();
  const [error, setError] = useState<string | null>(null);
  const sent = useRef(false);

  const code = params.get("code");
  const state = params.get("state");
  const denied = params.get("error_description") ?? params.get("error");

  useEffect(() => {
    if (gate !== "ready" || sent.current || denied || !code || !state) return;
    sent.current = true;
    complete(code, state)
      .then(() => router.replace(BACK))
      .catch((err) => setError(getErrorMessage(err, "Fayda verification failed")));
  }, [gate, code, state, denied, complete, router, BACK]);

  const problem = denied ? `Fayda did not complete the sign-in: ${denied}` : !code || !state ? "Missing response from Fayda." : error;

  return (
    <div className="mx-auto max-w-md px-4 py-16 text-center">
      {problem ? (
        <>
          <h1 className="text-lg font-semibold">Verification not completed</h1>
          <p className="text-muted-foreground mt-2 text-sm">{problem}</p>
          <Link href={BACK} className="mt-6 inline-block">
            <Button>Try again</Button>
          </Link>
        </>
      ) : (
        <LoadingState label="Confirming your identity with Fayda…" />
      )}
    </div>
  );
}
