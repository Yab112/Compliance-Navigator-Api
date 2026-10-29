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

const PHONE = /^(\+251|0)[79]\d{8}$/;

export function Register() {
  const returnTo = safeReturnTo(useSearchParams().get("returnTo"));
  const { register, isRegistering } = useRegister();
  const [submitted, setSubmitted] = useState(false);
  useRedirectIfSignedIn(submitted ? "" : returnTo);
  const [fullname, setFullname] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

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
          setSubmitted(true);
          try {
            await register({ email: email.trim(), password, fullname: fullname.trim(), phone }, returnTo);
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
        <FormError message={error} />
        <Button type="submit" size="lg" loading={isRegistering}>
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
