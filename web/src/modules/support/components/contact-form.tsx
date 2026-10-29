"use client";

import Link from "next/link";
import { useState } from "react";
import { useSupportMeta, useSupportWrite } from "@/api/support";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getErrorMessage } from "@/lib/errors";
import { Field, NativeSelect, PHONE_RE } from "@/modules/guday/components/shared";
import { useUserStore } from "@/store/user-store";
import { QUEUE_LABELS, type SupportQueue, type SupportTicket } from "@/types/support";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** "Write to our team": becomes a support ticket. Works signed out with a way to call back. */
export function ContactForm({ conversationId, onSent }: { conversationId?: string | null; onSent?: (t: SupportTicket) => void }) {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  const meta = useSupportMeta();
  const { createTicket, isPending } = useSupportWrite();
  const queues = meta.data?.payload.queues?.length
    ? meta.data.payload.queues
    : (Object.keys(QUEUE_LABELS) as SupportQueue[]).map((key) => ({ key, label: QUEUE_LABELS[key], description: null }));
  const [v, setV] = useState({ queue: "customer_support", subject: "", body: "", name: "", phone: "", email: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [sent, setSent] = useState<SupportTicket | null>(null);
  const set = (k: keyof typeof v, value: string) => setV((x) => ({ ...x, [k]: value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (v.subject.trim().length < 3) next.subject = "Say in a few words what this is about";
    if (v.body.trim().length < 10) next.body = "Tell us a little more (at least 10 characters)";
    if (!signedIn) {
      if (!v.name.trim()) next.name = "Your name, so we know who to ask for";
      const phone = v.phone.replace(/\s/g, "");
      if (!phone && !v.email.trim()) next.phone = "Give a phone number or an email so we can answer";
      if (phone && !PHONE_RE.test(phone)) next.phone = "Use an Ethiopian mobile number, for example 0911223344";
      if (v.email.trim() && !EMAIL_RE.test(v.email.trim())) next.email = "This email doesn't look right";
    }
    setErrors(next);
    if (Object.keys(next).length) return;
    setFailure(null);
    try {
      const res = await createTicket({
        queue: v.queue as SupportQueue,
        subject: v.subject.trim(),
        body: v.body.trim(),
        conversation_id: conversationId ?? undefined,
        ...(!signedIn && {
          name: v.name.trim(),
          phone: v.phone.replace(/\s/g, "") || undefined,
          email: v.email.trim() || undefined,
        }),
      });
      setSent(res.ticket);
      onSent?.(res.ticket);
    } catch (err) {
      setFailure(getErrorMessage(err, "We couldn't send your message. Please try again."));
    }
  };

  if (sent) {
    return (
      <div className="border-primary/40 bg-secondary/60 space-y-2 rounded-md border p-3 text-sm" role="status">
        <p className="text-primary font-semibold">Sent ✓ · ተልኳል</p>
        <p>
          Your reference is <span className="font-mono font-semibold">{sent.ref}</span>. The {sent.queue_label} team will answer
          {signedIn ? " here and in your account." : " on the phone number or email you gave."}
        </p>
        <div className="flex flex-wrap gap-2">
          {signedIn && (
            <Link href={`/account/support/${sent.id}`} className="text-primary text-xs font-semibold hover:underline">
              Open request ›
            </Link>
          )}
          <button
            type="button"
            className="text-muted-foreground text-xs hover:underline"
            onClick={() => {
              setSent(null);
              setV((x) => ({ ...x, subject: "", body: "" }));
            }}
          >
            Write another
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-2.5" noValidate>
      <Field label="Topic · ርዕስ" htmlFor="cf-queue">
        <NativeSelect id="cf-queue" className="h-9 text-sm" value={v.queue} onChange={(e) => set("queue", e.target.value)}>
          {queues.map((q) => (
            <option key={q.key} value={q.key}>
              {q.label}
            </option>
          ))}
        </NativeSelect>
      </Field>
      <Field label="Subject" htmlFor="cf-subject" required error={errors.subject}>
        <Input id="cf-subject" value={v.subject} maxLength={160} onChange={(e) => set("subject", e.target.value)} />
      </Field>
      <Field label="Message · መልእክት" htmlFor="cf-body" required error={errors.body}>
        <Textarea id="cf-body" rows={4} value={v.body} maxLength={4000} onChange={(e) => set("body", e.target.value)} />
      </Field>
      {!signedIn && (
        <>
          <Field label="Your name" htmlFor="cf-name" required error={errors.name}>
            <Input id="cf-name" autoComplete="name" value={v.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="Phone" htmlFor="cf-phone" hint="Phone or email, so we can answer" error={errors.phone}>
            <Input id="cf-phone" type="tel" inputMode="tel" autoComplete="tel" placeholder="09XXXXXXXX" value={v.phone} onChange={(e) => set("phone", e.target.value)} />
          </Field>
          <Field label="Email" htmlFor="cf-email" error={errors.email}>
            <Input id="cf-email" type="email" autoComplete="email" value={v.email} onChange={(e) => set("email", e.target.value)} />
          </Field>
        </>
      )}
      {failure && (
        <p className="text-destructive text-xs" role="alert">
          {failure}
        </p>
      )}
      <Button type="submit" className="w-full" loading={isPending}>
        Send to our team
      </Button>
    </form>
  );
}
