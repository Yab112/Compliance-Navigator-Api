"use client";

import Link from "next/link";
import type { AssistantController } from "@/api/assistant";
import { useMyTickets, useSupportMeta } from "@/api/support";
import { cn } from "@/lib/utils";
import { ContactForm } from "@/modules/support/components/contact-form";
import { TicketStatusBadge } from "@/modules/support/components/ticket-badges";
import { useUserStore } from "@/store/user-store";
import type { AssistantAction } from "@/types/assistant";

type AskItem = { en: string; am: string; hint: string; send: { message: string; messageAm: string } | { action: AssistantAction } };

/** What the assistant can do; each item starts that conversation. */
const ASK: AskItem[] = [
  { en: "Requirements and documents", am: "መስፈርቶችና ሰነዶች", hint: "What to bring, for any service", send: { message: "What documents do I need?", messageAm: "ምን ሰነዶች ያስፈልጉኛል?" } },
  { en: "Fees", am: "ክፍያዎች", hint: "What it costs and who sets it", send: { message: "How much does it cost?", messageAm: "ስንት ያስከፍላል?" } },
  { en: "Offices and hours", am: "ቢሮዎችና የሥራ ሰዓት", hint: "Where to go and when they're open", send: { message: "Where do I go and when are they open?", messageAm: "የት ልሂድ? መቼ ክፍት ናቸው?" } },
  { en: "Hire a provider", am: "አገልግሎት ሰጪ ይቅጠሩ", hint: "A verified agent does it for you", send: { message: "I want to hire an agent", messageAm: "ወኪል መቅጠር እፈልጋለሁ" } },
  { en: "Report wrong information", am: "የተሳሳተ መረጃ ያሳውቁ", hint: "Tell us what changed at the office", send: { message: "I want to report wrong information", messageAm: "የተሳሳተ መረጃ ማሳወቅ እፈልጋለሁ" } },
  { en: "Check my requests", am: "ጥያቄዎቼን ይመልከቱ", hint: "Hires, paths and support requests", send: { message: "What is the status of my requests?", messageAm: "የጥያቄዎቼ ሁኔታ ምንድን ነው?" } },
  { en: "Talk to a person", am: "ሰው ያነጋግሩ", hint: "Our support team takes over", send: { action: { type: "handoff", label: "Talk to a person" } } },
];

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border-border border-b px-4 py-4", className)}>
      <h2 className="text-gov-ink mb-2.5 text-xs font-semibold tracking-wide uppercase">{title}</h2>
      {children}
    </section>
  );
}

function ContactDetails({ am }: { am: boolean }) {
  const { data, isLoading } = useSupportMeta();
  const c = data?.payload.contact;
  if (isLoading) return <p className="text-muted-foreground text-xs">Loading contact details…</p>;
  if (!c) return null;
  const hours = (am && c.hours_am) || c.hours;
  const address = (am && c.address_am) || c.address;
  return (
    <dl className="mb-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
      {c.phone && (
        <>
          <dt className="text-muted-foreground text-xs leading-5">Phone</dt>
          <dd>
            <a href={`tel:${c.phone.replace(/\s/g, "")}`} className="text-primary font-semibold hover:underline">
              {c.phone}
            </a>
          </dd>
        </>
      )}
      {c.email && (
        <>
          <dt className="text-muted-foreground text-xs leading-5">Email</dt>
          <dd className="min-w-0 break-all">
            <a href={`mailto:${c.email}`} className="text-primary hover:underline">
              {c.email}
            </a>
          </dd>
        </>
      )}
      {hours && (
        <>
          <dt className="text-muted-foreground text-xs leading-5">Hours</dt>
          <dd>{hours}</dd>
        </>
      )}
      {address && (
        <>
          <dt className="text-muted-foreground text-xs leading-5">Office</dt>
          <dd>{address}</dd>
        </>
      )}
    </dl>
  );
}

function MyRequests() {
  const signedIn = useUserStore((s) => s.status === "authenticated");
  const { data, isLoading } = useMyTickets(0, 5);
  if (!signedIn) {
    return (
      <p className="text-muted-foreground text-xs">
        <Link href="/login?returnTo=%2Fchat" className="text-primary font-medium hover:underline">
          Sign in
        </Link>{" "}
        to follow your requests and get replies in one place.
      </p>
    );
  }
  if (isLoading) return <p className="text-muted-foreground text-xs">Loading…</p>;
  const items = data?.payload.items ?? [];
  if (!items.length) return <p className="text-muted-foreground text-xs">No support requests yet.</p>;
  return (
    <>
      <ul className="space-y-1.5">
        {items.map((t) => (
          <li key={t.id}>
            <Link href={`/account/support/${t.id}`} className="border-border hover:border-primary block rounded-md border p-2.5">
              <span className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground font-mono text-[11px]">{t.ref}</span>
                <TicketStatusBadge status={t.status} label={t.status_label} />
              </span>
              <span className="mt-1 block truncate text-sm font-medium">{t.subject}</span>
            </Link>
          </li>
        ))}
      </ul>
      {(data?.payload.total ?? 0) > items.length && (
        <Link href="/account/support" className="text-primary mt-2 inline-block text-xs font-semibold hover:underline">
          All requests ›
        </Link>
      )}
    </>
  );
}

/** The chat page's companion column: what to ask, how to reach a person, and open requests. */
export function ChatSidePanel({ assistant, onPicked }: { assistant: AssistantController; onPicked?: () => void }) {
  const am = assistant.language === "am";
  const pick = (item: AskItem) => {
    if ("action" in item.send) void assistant.send({ action: { ...item.send.action, label: am ? item.am : item.en } });
    else void assistant.send({ message: am ? item.send.messageAm : item.send.message });
    onPicked?.();
  };
  return (
    <div className="bg-card">
      <Section title="Ask whatever you need · የፈለጉትን ይጠይቁ">
        <ul className="grid gap-1">
          {ASK.map((item) => (
            <li key={item.en}>
              <button
                type="button"
                disabled={assistant.pending}
                onClick={() => pick(item)}
                className="hover:bg-secondary/70 group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left disabled:opacity-50"
              >
                <span className="text-primary mt-0.5 text-xs" aria-hidden>
                  ›
                </span>
                <span>
                  <span className="block text-sm font-medium group-hover:underline">
                    {item.en} <span className="text-muted-foreground text-xs font-normal">· {item.am}</span>
                  </span>
                  <span className="text-muted-foreground block text-xs">{item.hint}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Contact us · ያግኙን">
        <ContactDetails am={am} />
        <details className="group">
          <summary className="text-primary cursor-pointer text-sm font-semibold hover:underline">Write to our team ›</summary>
          <div className="mt-3">
            <ContactForm conversationId={assistant.getConversationId()} />
          </div>
        </details>
      </Section>
      <Section title="My requests · ጥያቄዎቼ" className="border-b-0">
        <MyRequests />
      </Section>
    </div>
  );
}
