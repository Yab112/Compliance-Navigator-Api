"use client";

import Link from "next/link";
import {
  ArrowRight01Icon,
  Certificate01Icon,
  IdIcon,
  Invoice01Icon,
  Location01Icon,
  PassportIcon,
  Store01Icon,
  Wallet01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useCatalogCenters, useCatalogInstitutions } from "@/api/catalog";
import { landingContent } from "@/content/landing";

const POPULAR = [
  { id: "passport", label: "Passport", am: "ፓስፖርት", hint: "New or renewal", icon: PassportIcon },
  { id: "kebele_id", label: "Kebele ID", am: "የቀበሌ መታወቂያ", hint: "Resident ID card", icon: IdIcon },
  { id: "tin", label: "TIN certificate", am: "የግብር ከፋይ መለያ ቁጥር", hint: "Tax registration", icon: Invoice01Icon },
  { id: "trade_license", label: "Trade license", am: "የንግድ ፈቃድ", hint: "Open a business", icon: Store01Icon },
  { id: "commercial_registration", label: "Commercial registration", am: "የንግድ ምዝገባ", hint: "Register a company", icon: Certificate01Icon },
  { id: "fintech_license", label: "Fintech license", am: "የፊንቴክ ፈቃድ", hint: "Payment & finance", icon: Wallet01Icon },
];

function SectionTitle({ title, am, action }: { title: string; am: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-gov-ink text-xl font-bold md:text-2xl">{title}</h2>
        <p className="text-muted-foreground text-sm">{am}</p>
      </div>
      {action}
    </div>
  );
}

const moreLink = (href: string, label: string) => (
  <Link href={href} className="text-primary inline-flex items-center gap-1 text-sm font-semibold hover:underline">
    {label} <HugeiconsIcon icon={ArrowRight01Icon} className="size-4" />
  </Link>
);

export function PopularServices() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-12">
      <SectionTitle title="Popular services" am="ተፈላጊ አገልግሎቶች" action={moreLink("/roadmap/new", "Other process")} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {POPULAR.map((s) => (
          <Link
            key={s.id}
            href={`/roadmap/new?goal=${s.id}`}
            className="group border-border bg-card hover:border-primary flex items-start gap-4 rounded-md border p-4 transition-colors"
          >
            <HugeiconsIcon icon={s.icon} className="text-primary mt-0.5 size-7 shrink-0" />
            <span className="min-w-0">
              <span className="block font-semibold">{s.label}</span>
              <span className="text-muted-foreground block text-sm">{s.am}</span>
              <span className="text-primary mt-1 block text-xs font-medium">{s.hint}. See the steps →</span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function InstitutionsStrip() {
  const { data, isLoading } = useCatalogInstitutions();
  const list = data?.payload.institutions ?? [];

  return (
    <section className="border-border bg-card border-y">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <SectionTitle
          title="Institutions already on the map"
          am="ቀድሞውኑ በካርታው ላይ ያሉ ተቋማት"
          action={moreLink("/services", "Browse all services")}
        />
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {isLoading &&
            Array.from({ length: 8 }).map((_, i) => (
              <li key={i} className="bg-muted h-[76px] animate-pulse rounded-md" />
            ))}
          {list.map((inst) => (
            <li key={inst.id}>
              <Link
                href={`/services?institution=${inst.id}`}
                className="border-border hover:border-primary hover:bg-secondary/40 flex h-full items-center gap-3 rounded-md border p-3 transition-colors"
                title={inst.name}
              >
                {inst.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- remote logos from the catalog
                  <img src={inst.logo_url} alt="" loading="lazy" className="size-12 shrink-0 object-contain" />
                ) : (
                  <span className="bg-secondary text-primary flex size-12 shrink-0 items-center justify-center rounded-md text-xs font-bold">
                    {inst.short_name?.slice(0, 4)}
                  </span>
                )}
                <span className="min-w-0">
                  <span className="line-clamp-2 text-xs leading-snug font-semibold">{inst.name}</span>
                  <span className="text-muted-foreground mt-0.5 block text-[11px]">
                    {inst.service_count ?? 0} services
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export function HowItWorks() {
  const { steps } = landingContent;
  return (
    <section className="mx-auto max-w-6xl px-4 py-12">
      <SectionTitle title="How it works" am="እንዴት ይሠራል?" />
      <ol className="grid gap-4 md:grid-cols-3">
        {steps.map((s) => (
          <li key={s.n} className="border-border bg-card flex gap-4 rounded-md border p-5">
            <span className="bg-gov-yellow text-gov-ink flex size-10 shrink-0 items-center justify-center rounded-full text-lg font-bold">
              {s.n}
            </span>
            <span>
              <span className="block font-semibold">{s.title}</span>
              <span className="text-muted-foreground mt-1 block text-sm">{s.desc}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function CentersList() {
  const { data } = useCatalogCenters();
  const centers = data?.payload.centers ?? [];
  if (!centers.length) return null;

  return (
    <section className="border-border bg-secondary/40 border-t">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <SectionTitle title="MESOB centers · our partner" am="የመሶብ ማዕከላት · አጋራችን" />
        <p className="text-muted-foreground -mt-3 mb-5 max-w-3xl text-sm">
          MESOB brings many institutions under one roof. Where a step on your path can be done at a MESOB
          center, we show it, so you can finish several steps in one visit.
        </p>
        <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {centers.map((c) => (
            <li key={c.id}>
              <a
                href={c.map_url ?? undefined}
                target="_blank"
                rel="noreferrer"
                className="border-border bg-card hover:border-primary flex items-center gap-3 rounded-md border px-3 py-2.5 text-sm"
              >
                <HugeiconsIcon icon={Location01Icon} className="text-gov-red size-5 shrink-0" />
                <span className="min-w-0 flex-1 truncate">{c.name.replace(/ Mesob Center$/i, "")}</span>
                {c.map_url && <span className="text-primary shrink-0 text-xs">Map ↗</span>}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
