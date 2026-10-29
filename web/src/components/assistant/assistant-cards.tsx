"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import type { AssistantCard } from "@/types/assistant";

const SOURCE_BADGE: Record<string, { label: string; className: string }> = {
  organization: { label: "Published by the organization", className: "bg-primary text-primary-foreground" },
  path: { label: "Guided path", className: "bg-gov-yellow text-gov-ink" },
  mesob: { label: "MESOB catalog", className: "bg-secondary text-secondary-foreground" },
};

function Facts({ fee, time }: { fee?: string | null; time?: string | null }) {
  if (!fee && !time) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
      {fee && <span className="border-border rounded border px-1.5 py-0.5">{fee}</span>}
      {time && <span className="border-border rounded border px-1.5 py-0.5">{time}</span>}
    </div>
  );
}

function ServiceCard({ card }: { card: Extract<AssistantCard, { kind: "service" }> }) {
  const badge = SOURCE_BADGE[card.source];
  return (
    <div className="border-border bg-card rounded-md border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold">{card.title}</p>
        {badge && <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", badge.className)}>{badge.label}</span>}
      </div>
      {card.provider && <p className="text-muted-foreground text-xs">{card.provider}</p>}
      <Facts fee={card.fee} time={card.time} />
      {card.documents.length > 0 && (
        <ul className="mt-2 space-y-1 text-xs">
          {card.documents.map((d, i) => {
            const item = typeof d === "string" ? { label: d, done: false } : d;
            return (
              <li key={i} className="flex gap-2">
                <span className={item.done ? "text-primary" : "text-muted-foreground"} aria-hidden>
                  {item.done ? "✓" : "○"}
                </span>
                <span className={item.done ? "text-muted-foreground line-through" : undefined}>{item.label}</span>
              </li>
            );
          })}
        </ul>
      )}
      {card.href && (
        <Link href={card.href} className="text-primary mt-2 inline-block text-xs font-semibold hover:underline">
          Open service page →
        </Link>
      )}
    </div>
  );
}

function PathCard({ card }: { card: Extract<AssistantCard, { kind: "path" }> }) {
  return (
    <div className="border-border bg-card rounded-md border p-3">
      <p className="text-sm font-semibold">{card.title}</p>
      <ol className="mt-3 space-y-0">
        {card.steps.map((s, i) => (
          <li key={i} className="relative flex gap-3 pb-3 last:pb-0">
            {i < card.steps.length - 1 && <span className="bg-border absolute top-6 left-[11px] h-full w-px" aria-hidden />}
            <span
              className={cn(
                "relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                i === card.steps.length - 1 ? "bg-primary text-primary-foreground" : "bg-gov-yellow text-gov-ink",
              )}
            >
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{s.title}</p>
              {s.office && <p className="text-muted-foreground text-xs">{s.office}</p>}
              <Facts fee={s.fee} time={s.time} />
              {s.mesob?.fee && (
                <p className="text-primary mt-1 text-[11px]">
                  At MESOB centers: {s.mesob.fee}
                  {s.mesob.time ? ` · ${s.mesob.time}` : ""}
                </p>
              )}
              {s.documents.length > 0 && (
                <p className="text-muted-foreground mt-1 text-[11px]">Bring: {s.documents.join(", ")}</p>
              )}
            </div>
          </li>
        ))}
      </ol>
      {card.href && (
        <Link href={card.href} className="text-primary mt-2 inline-block text-xs font-semibold hover:underline">
          Open full path →
        </Link>
      )}
    </div>
  );
}

function ChecklistCard({ card }: { card: Extract<AssistantCard, { kind: "checklist" }> }) {
  return (
    <div className="border-border bg-card rounded-md border p-3">
      <p className="text-sm font-semibold">{card.title}</p>
      <ul className="mt-2 space-y-1.5 text-xs">
        {card.items.map((item, i) => (
          <li key={i} className="flex gap-2">
            {card.style === "list" ? (
              <span className="bg-primary mt-1.5 size-1.5 shrink-0 rounded-full" aria-hidden />
            ) : (
              <span className={item.done ? "text-primary" : "text-muted-foreground"} aria-hidden>
                {item.done ? "✓" : "○"}
              </span>
            )}
            <span>
              <span className={item.done && card.style !== "list" ? "text-muted-foreground line-through" : "font-medium"}>{item.label}</span>
              {item.detail && <span className="text-muted-foreground"> · {item.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BranchesCard({ card }: { card: Extract<AssistantCard, { kind: "branches" }> }) {
  return (
    <div className="grid gap-2">
      {card.items.map((b, i) => (
        <div key={i} className="border-border bg-card rounded-md border p-3 text-xs">
          <p className="text-sm font-semibold">{b.name}</p>
          {b.address && <p className="text-muted-foreground">{b.address}</p>}
          <p className="text-muted-foreground mt-1">
            {[b.window, b.hours, b.phone].filter(Boolean).join(" · ")}
          </p>
          {b.map_url && (
            <a href={b.map_url} target="_blank" rel="noreferrer" className="text-primary mt-1 inline-block font-semibold hover:underline">
              Show on map ↗
            </a>
          )}
        </div>
      ))}
    </div>
  );
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function ProvidersCard({ card }: { card: Extract<AssistantCard, { kind: "providers" }> }) {
  return (
    <div className="border-border bg-card divide-border divide-y rounded-md border">
      {card.items.map((p) => (
        <Link key={p.slug} href={`/providers/${p.slug}`} className="hover:bg-secondary/40 flex items-center gap-3 p-3">
          <span className="relative shrink-0">
            {p.photo ? (
              // eslint-disable-next-line @next/next/no-img-element -- uploaded provider photos
              <img src={p.photo} alt="" className="size-10 rounded-full object-cover" />
            ) : (
              <span className="bg-secondary text-primary flex size-10 items-center justify-center rounded-full text-xs font-bold">
                {initials(p.name)}
              </span>
            )}
            {p.verified && (
              <span className="bg-primary absolute -right-0.5 -bottom-0.5 flex size-4 items-center justify-center rounded-full text-[9px] text-white ring-2 ring-white" title="ID verified">
                ✓
              </span>
            )}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold">{p.name}</span>
            {p.headline && <span className="text-muted-foreground block truncate text-xs">{p.headline}</span>}
          </span>
          {p.score != null && (
            <span className="bg-primary text-primary-foreground shrink-0 rounded px-1.5 py-0.5 text-xs font-bold">{p.score}</span>
          )}
        </Link>
      ))}
      <Link href={card.href} className="text-primary block p-2 text-center text-xs font-semibold hover:underline">
        See all providers →
      </Link>
    </div>
  );
}

function SummaryCard({ card }: { card: Extract<AssistantCard, { kind: "summary" }> }) {
  return (
    <div className="border-primary/40 bg-card rounded-md border p-3">
      <p className="text-sm font-semibold">{card.title}</p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
        {card.rows.map((r, i) => (
          <div key={i} className="contents">
            <dt className="text-muted-foreground">{r.label}</dt>
            <dd className="min-w-0 break-words whitespace-pre-line">{r.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const TICKET_TONE: Record<string, string> = {
  new: "bg-gov-yellow text-gov-ink",
  open: "bg-gov-yellow text-gov-ink",
  waiting_customer: "bg-sky-100 text-sky-800",
  resolved: "bg-primary text-primary-foreground",
  closed: "bg-muted text-muted-foreground",
};

function TicketCard({ card }: { card: Extract<AssistantCard, { kind: "ticket" }> }) {
  const body = (
    <div className="border-gov-yellow bg-card rounded-md border-l-4 border-y border-r p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-xs font-semibold">{card.ref}</p>
        <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", TICKET_TONE[card.status] ?? "bg-muted")}>
          {card.status_label}
        </span>
      </div>
      <p className="mt-1 text-sm font-semibold">{card.subject}</p>
      <p className="text-muted-foreground mt-0.5 text-xs">
        {card.queue_label} team{card.expected ? ` · ${card.expected}` : ""}
      </p>
      {card.href && <p className="text-primary mt-1.5 text-xs font-semibold">Open request ›</p>}
    </div>
  );
  return card.href ? (
    <Link href={card.href} className="block hover:opacity-90">
      {body}
    </Link>
  ) : (
    body
  );
}

const STATUS_KIND: Record<string, string> = { ticket: "Support request", hire: "Hire", path: "Path" };

function StatusCard({ card }: { card: Extract<AssistantCard, { kind: "status" }> }) {
  if (!card.items.length) return null;
  return (
    <ul className="border-border bg-card divide-border divide-y rounded-md border text-xs">
      {card.items.map((item, i) => {
        const row = (
          <div className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="min-w-0">
              <span className="text-muted-foreground block text-[10px] tracking-wide uppercase">{STATUS_KIND[item.kind] ?? item.kind}</span>
              <span className="block truncate font-medium">{item.title}</span>
            </span>
            <span className="border-border shrink-0 rounded border px-1.5 py-0.5">{item.status_label}</span>
          </div>
        );
        return (
          <li key={i}>
            {item.href ? (
              <Link href={item.href} className="hover:bg-secondary/50 block">
                {row}
              </Link>
            ) : (
              row
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function AssistantCards({ cards }: { cards: AssistantCard[] }) {
  if (!cards.length) return null;
  return (
    <div className="mt-2 grid gap-2">
      {cards.map((card, i) => {
        switch (card.kind) {
          case "service":
            return <ServiceCard key={i} card={card} />;
          case "path":
            return <PathCard key={i} card={card} />;
          case "checklist":
            return <ChecklistCard key={i} card={card} />;
          case "branches":
            return <BranchesCard key={i} card={card} />;
          case "providers":
            return <ProvidersCard key={i} card={card} />;
          case "summary":
            return <SummaryCard key={i} card={card} />;
          case "ticket":
            return <TicketCard key={i} card={card} />;
          case "status":
            return <StatusCard key={i} card={card} />;
          default:
            return null;
        }
      })}
    </div>
  );
}
