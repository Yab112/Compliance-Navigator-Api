"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Label } from "@cn/ui/label";
import { useRegister } from "@cn/core/api/auth";
import { getErrorMessage } from "@cn/core/lib/errors";
import { safeReturnTo } from "@cn/core/lib/safe-redirect";
import { useRedirectIfSignedIn } from "@cn/core/hooks/use-redirect-if-signed-in";
import { AuthCard, FormError } from "@cn/ui/auth/auth-card";
import { PasswordInput, passwordIsValid } from "@cn/ui/auth/password-input";
import { OFF_PLATFORM_SUMMARY, SIGNUP_DOCS, signupAcceptance, type LegalKey } from "@/content/legal";
import { LegalCheckbox, LegalLink } from "@/modules/legal/components/legal-checkbox";

const PHONE = /^(\+251|0)[79]\d{8}$/;

const AGREEMENT_LABELS: Record<string, React.ReactNode> = {
  terms: <>I agree to the <LegalLink doc="terms" />, including the <LegalLink doc="refund_policy" />.</>,
  privacy: <>I have read the <LegalLink doc="privacy" /> and agree to how my data is used.</>,
  marketplace_rules: <>I agree to the <LegalLink doc="marketplace_rules" />, including paying only through Compliance Navigator.</>,
};

const NO_AGREEMENTS = Object.fromEntries(SIGNUP_DOCS.map((k) => [k, false])) as Record<LegalKey, boolean>;

export function Register() {
  const returnTo = safeReturnTo(useSearchParams().get("returnTo"));
  const { register, isRegistering } = useRegister();
  const [submitted, setSubmitted] = useState(false);
  useRedirectIfSignedIn(submitted ? "" : returnTo);
  const [fullname, setFullname] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(NO_AGREEMENTS);
  const [agreementMissing, setAgreementMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checkEmail, setCheckEmail] = useState(false);
  const allAgreed = SIGNUP_DOCS.every((k) => agreed[k]);

  if (checkEmail) {
    return (
      <AuthCard
        title="Check your email"
        am="ኢሜይልዎን ይመልከቱ"
        footer={
          <p>
            <Link href={`/login?returnTo=${encodeURIComponent(returnTo)}`} className="text-primary font-medium underline">
              Go to sign in
            </Link>
          </p>
        }
      >
        <div className="space-y-3 text-sm" role="status">
          <p className="border-primary/30 bg-secondary text-primary rounded-md border px-3 py-2">
            Check your email to continue. We sent a message to <strong className="break-all">{email}</strong> with the next step.
          </p>
          <p className="text-muted-foreground">No email after a few minutes? Check your spam folder, or try signing in.</p>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create an account"
      am="መለያ ይክፈቱ"
      description="Free for everyone. Save your paths, request a Guday Geday agent, or put your organization on the map."
      footer={
        <p>
          Already have an account?{" "}
          <Link href={`/login?returnTo=${encodeURIComponent(returnTo)}`} className="text-primary font-medium underline">
            Sign in
          </Link>
        </p>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          if (!passwordIsValid(password)) {
            setError("Choose a password with at least 8 characters, including a letter and a number.");
            return;
          }
          if (phone.trim() && !PHONE.test(phone.trim())) {
            setError("Enter an Ethiopian mobile number like 0911234567, or leave it empty.");
            return;
          }
          if (!allAgreed) {
            setAgreementMissing(true);
            setError("Tick all three boxes to agree to our terms. We can only create your account once you agree.");
            return;
          }
          setSubmitted(true);
          try {
            const result = await register({ email: email.trim(), password, fullname: fullname.trim(), phone, accept: signupAcceptance() }, returnTo);
            if (result === "check-email") setCheckEmail(true);
          } catch (err) {
            setSubmitted(false);
            setError(getErrorMessage(err, "Could not create the account. Try again."));
          }
        }}
      >
        <div className="flex flex-col gap-2">
          <Label htmlFor="fullname">Full name · ሙሉ ስም</Label>
          <Input id="fullname" autoComplete="name" required minLength={2} value={fullname} onChange={(e) => setFullname(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="phone">
            Phone <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <Input id="phone" type="tel" autoComplete="tel" placeholder="09XXXXXXXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="password">Password · የይለፍ ቃል</Label>
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="new-password" showRules />
        </div>
        <fieldset className="border-border flex flex-col gap-3 rounded-md border p-4">
          <legend className="px-1 text-sm font-semibold">Agreements · ስምምነቶች</legend>
          <p className="bg-secondary/60 rounded-md px-3 py-2 text-xs leading-relaxed">{OFF_PLATFORM_SUMMARY}</p>
          {SIGNUP_DOCS.map((key) => (
            <LegalCheckbox
              key={key}
              id={`accept-${key}`}
              checked={agreed[key]}
              invalid={agreementMissing && !agreed[key]}
              onChange={(checked) => {
                setAgreed((a) => ({ ...a, [key]: checked }));
                setAgreementMissing(false);
              }}
            >
              {AGREEMENT_LABELS[key]}
            </LegalCheckbox>
          ))}
        </fieldset>
        <FormError message={error} />
        <Button type="submit" size="lg" loading={isRegistering}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
