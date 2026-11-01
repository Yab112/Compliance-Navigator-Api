"use client";

import Link from "next/link";
import { useState } from "react";
import { useCreateHire } from "@cn/core/api/providers";
import { Button } from "@cn/ui/button";
import { Input } from "@cn/ui/input";
import { Textarea } from "@cn/ui/textarea";
import { getErrorMessage } from "@cn/core/lib/errors";
import { AxiosError } from "axios";
import { Field, PHONE_RE } from "@cn/ui/guday/shared";
import { useUserStore } from "@/store";
import type { DeliveryMode, Hire } from "@cn/core/types/provider";
import { DELIVERY_LABELS } from "@cn/ui/marketplace/constants";
import { cleanTelegram, TELEGRAM_HINT, TELEGRAM_RE } from "@/lib/telegram";

type HireFormProps = {
  /** Provider slug or id; empty sends the request to staff to assign */
  providerId?: string;
  providerName?: string;
  serviceId?: string;
  specialty?: string;
  defaultTitle?: string;
  defaultDetails?: string;
  subCity?: string;
  /** Where the provider works with clients (advisors); the client picks one */
  deliveryModes?: DeliveryMode[];
  visitFee?: number | null;
  returnTo: string;
  submitLabel?: string;
  onCreated?: (hire: Hire) => void;
};

/** Plain wording for the hire_create rate limit (10 an hour, 30 a day, see core/ratelimit.py). */
function hireLimitMessage(err: AxiosError): string {
  const raw = Number(err.response?.headers?.["retry-after"]);
  const wait = Number.isFinite(raw) && raw > 0 ? raw : 3600;
  const minutes = Math.max(1, Math.ceil(wait / 60));
  if (minutes > 60) {
    const hours = Math.ceil(minutes / 60);
    return `You can send up to 30 requests a day. Try again in ${hours} ${hours === 1 ? "hour" : "hours"}.`;
  }
  return `You can send up to 10 requests an hour. Try again in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`;
}

/** Request form for hiring a provider. Sign-in is required so the client can track and review. */
/**
 * The form takes the signed-in person's name, phone and Telegram as starting values. The session can
 * arrive after the page renders, so the form starts over once it does (keyed by the user).
 */
export function HireForm(props: HireFormProps) {
  const userId = useUserStore((s) => s.user?.id);
  return <HireFormFields key={userId ?? "anonymous"} {...props} />;
}

function HireFormFields({
  providerId,
  providerName,
  serviceId,
  specialty,
  defaultTitle = "",
  defaultDetails = "",
  subCity,
  deliveryModes = [],
  visitFee,
  returnTo,
  submitLabel,
  onCreated,
}: HireFormProps) {
  const user = useUserStore((s) => s.user);
  const { createHire, isCreating } = useCreateHire();
  const [title, setTitle] = useState(defaultTitle);
  const [name, setName] = useState(user?.fullname ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [telegram, setTelegram] = useState(user?.telegramUsername ? `@${user.telegramUsername}` : "");
  const [details, setDetails] = useState(defaultDetails);
  const [budget, setBudget] = useState("");
  const [mode, setMode] = useState<DeliveryMode | null>(deliveryModes.length === 1 ? deliveryModes[0] : null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [created, setCreated] = useState<Hire | null>(null);

  if (!user) {
    return (
      <div className="border-border bg-card rounded-md border p-5 text-sm">
        <p>Sign in to send a request. You can follow it, and review the provider once the job is done.</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <Link href={`/login?returnTo=${encodeURIComponent(returnTo)}`}>
            <Button>Sign in</Button>
          </Link>
          <Link href={`/register?returnTo=${encodeURIComponent(returnTo)}`}>
            <Button variant="outline">Create a free account</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (created) {
    return (
      <div className="border-primary/40 bg-secondary/60 space-y-3 rounded-md border p-5">
        <p className="text-primary font-semibold">Request sent ✓ · ጥያቄዎ ተልኳል</p>
        <p className="text-sm">
          {created.provider_name
            ? `${created.provider_name} will accept or decline. Once they accept you'll both see each other's phone and Telegram to agree on the details.`
            : "Our staff will match you with a verified provider who will call you."}
        </p>
        <Link href="/account/requests">
          <Button>Track my hires</Button>
        </Link>
      </div>
    );
  }

  const submit = async () => {
    const next: Record<string, string> = {};
    if (!serviceId && title.trim().length < 3) next.title = "Say what you need";
    if (name.trim().length < 2) next.name = "Enter your name";
    if (!PHONE_RE.test(phone.replace(/\s/g, ""))) next.phone = "Use an Ethiopian mobile number, for example 0911223344";
    // Both sides talk on Telegram once the provider accepts, so it is required like the phone
    if (!telegram.trim()) next.telegram = "Add your Telegram username so the provider can message you";
    else if (!TELEGRAM_RE.test(cleanTelegram(telegram))) next.telegram = TELEGRAM_HINT;
    if (deliveryModes.length && !mode) next.mode = "Choose where you want to meet";
    setErrors(next);
    if (Object.keys(next).length) return;
    setSubmitError(null);
    try {
      const res = await createHire({
        provider_id: providerId,
        service_id: serviceId,
        specialty,
        title: title.trim() || undefined,
        client_name: name.trim(),
        client_phone: phone.replace(/\s/g, ""),
        client_telegram: cleanTelegram(telegram),
        sub_city: subCity,
        details: details.trim() || undefined,
        budget: budget.trim() || undefined,
        delivery_mode: mode ?? undefined,
      });
      setCreated(res.hire);
      onCreated?.(res.hire);
    } catch (err) {
      setSubmitError(
        err instanceof AxiosError && err.response?.status === 429 ? hireLimitMessage(err) : getErrorMessage(err, "Could not send your request"),
      );
    }
  };

  return (
    <div className="border-border bg-card space-y-4 rounded-md border p-5">
      <Field label="What do you need?" htmlFor="hire-title" required={!serviceId} error={errors.title}>
        <Input
          id="hire-title"
          placeholder="For example: Renew my trade license"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Your name" htmlFor="hire-name" required error={errors.name}>
          <Input id="hire-name" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Phone to call you on" htmlFor="hire-phone" required error={errors.phone}>
          <Input id="hire-phone" type="tel" placeholder="09XXXXXXXX" value={phone} onChange={(e) => setPhone(e.target.value)} />
        </Field>
        <Field label="Telegram username" htmlFor="hire-telegram" required error={errors.telegram}
          hint="The provider messages you here once they accept. We save it for your next request.">
          <Input id="hire-telegram" placeholder="@your_username" value={telegram} onChange={(e) => setTelegram(e.target.value)} />
        </Field>
      </div>
      {deliveryModes.length > 0 && (
        <fieldset>
          <legend className="mb-1.5 text-xs font-medium">Where do you want to meet? <span className="text-destructive">*</span></legend>
          <div className="space-y-1.5">
            {deliveryModes.map((m) => (
              <label key={m} className="flex items-center gap-2 text-sm">
                <input type="radio" name="hire-mode" className="accent-primary size-4" checked={mode === m} onChange={() => setMode(m)} />
                {m === "client_office" ? "At my office" : m === "provider_office" ? "At their office" : DELIVERY_LABELS[m].short}
                {m === "client_office" && visitFee ? <span className="text-muted-foreground text-xs">· visit fee {visitFee.toLocaleString("en")} ETB</span> : null}
              </label>
            ))}
          </div>
          {mode === "client_office" && (
            <p className="text-muted-foreground mt-1 text-[11px]">Share your exact address on Telegram once they accept.</p>
          )}
          {errors.mode && <p className="text-destructive mt-1 text-[11px]">{errors.mode}</p>}
        </fieldset>
      )}
      <Field label="Details" htmlFor="hire-details" hint="Dates, documents you already have, anything the provider should know.">
        <Textarea id="hire-details" rows={3} value={details} onChange={(e) => setDetails(e.target.value)} />
      </Field>
      <Field label="Budget (optional)" htmlFor="hire-budget">
        <Input id="hire-budget" placeholder="For example: up to 2,000 ETB" value={budget} onChange={(e) => setBudget(e.target.value)} />
      </Field>
      {submitError && <p className="text-destructive text-sm">{submitError}</p>}
      <Button size="lg" className="h-auto min-h-11 w-full py-2 text-base whitespace-normal sm:w-auto" loading={isCreating} onClick={submit}>
        {submitLabel ?? (providerName ? `Send request to ${providerName}` : "Send request")}
      </Button>
    </div>
  );
}
