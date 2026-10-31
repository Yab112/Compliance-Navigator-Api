import Image from "next/image";
import Link from "next/link";
import { CheckmarkBadge01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { landingContent } from "@/content/landing";
import { stockImages } from "@/content/stock-images";

function Heading({ title, am, lead }: { title: string; am: string; lead?: string }) {
  return (
    <div className="mb-8 max-w-3xl">
      <div>
        <h2 className="text-gov-ink text-xl font-bold md:text-2xl">{title}</h2>
        <p className="text-muted-foreground text-sm">{am}</p>
      </div>
      {lead && <p className="text-muted-foreground mt-4 text-base leading-relaxed">{lead}</p>}
    </div>
  );
}

function Check({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-2 text-sm">
      <HugeiconsIcon icon={CheckmarkBadge01Icon} className="text-primary mt-0.5 size-4 shrink-0" />
      <span>{children}</span>
    </li>
  );
}

/** The problem and our answer, in plain words. */
export function WhatItIs() {
  const { problem, answer, promises } = landingContent.explainer;
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <div className="grid items-center gap-10 lg:grid-cols-2">
        <div className="relative aspect-[4/3] overflow-hidden rounded-md">
          <Image
            src={stockImages.queue}
            alt="A busy street in the Piazza district of Addis Ababa"
            fill
            sizes="(max-width: 1024px) 100vw, 50vw"
            className="object-cover"
          />
          <p className="absolute bottom-0 left-0 bg-black/60 px-3 py-1.5 text-xs text-white">Piazza, Addis Ababa</p>
        </div>
        <div>
          <Heading title="What is Compliance Navigator?" am="ኮምፕላያንስ ናቪጌተር ምንድን ነው?" />
          <h3 className="font-semibold">The problem · ችግሩ</h3>
          <p className="text-muted-foreground mt-2 leading-relaxed">{problem}</p>
          <h3 className="mt-6 font-semibold">What we do · የምንሰራው</h3>
          <p className="text-muted-foreground mt-2 leading-relaxed">{answer}</p>
          <ul className="mt-6 grid gap-2 sm:grid-cols-2">
            {promises.map((p) => (
              <Check key={p}>{p}</Check>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

/** The three things that make the platform: map, marketplace, organizations. */
export function Pillars() {
  return (
    <section className="border-border bg-card border-y">
      <div className="mx-auto max-w-6xl px-4 py-14">
        <Heading
          title="One platform, three parts"
          am="አንድ መድረክ፣ ሶስት ክፍሎች"
          lead="Citizens, providers and organizations meet in one place, and each makes the others more useful."
        />
        <ol className="grid gap-5 md:grid-cols-3">
          {landingContent.pillars.map((p, i) => (
            <li key={p.title} className="border-gov-yellow flex flex-col border-t-4 pt-4">
              <span className="text-primary text-sm font-bold">0{i + 1}</span>
              <h3 className="mt-1 text-lg font-semibold">
                {p.title} <span className="text-muted-foreground text-sm font-normal">· {p.am}</span>
              </h3>
              <p className="text-muted-foreground mt-2 flex-1 text-sm leading-relaxed">{p.body}</p>
              <Link href={p.href} className="text-primary mt-4 text-sm font-semibold hover:underline">
                {p.cta} →
              </Link>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/** A worked cross-organization example so visitors see exactly what they get. */
export function SamplePath() {
  const { sample } = landingContent;
  return (
    <section className="bg-gov-ink text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <p className="text-gov-yellow text-sm font-semibold">Example · ምሳሌ</p>
          <h2 className="mt-2 text-2xl font-bold md:text-3xl">{sample.title}</h2>
          <p className="mt-4 leading-relaxed text-white/80">{sample.intro}</p>
          <p className="mt-4 text-sm text-white/60">{sample.note}</p>
          <Link
            href="/roadmap/new?goal=trade_license"
            className="bg-gov-yellow text-gov-ink mt-6 inline-block rounded-md px-5 py-2.5 text-sm font-semibold hover:brightness-95"
          >
            Build my own path →
          </Link>
        </div>
        <ol className="relative space-y-3">
          {sample.steps.map((s, i) => (
            <li key={s.title} className="flex gap-4 rounded-md bg-white/5 p-4 ring-1 ring-white/10">
              <span className="bg-gov-yellow text-gov-ink flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-bold">
                {i + 1}
              </span>
              <div className="min-w-0">
                <p className="font-semibold">
                  {s.title} <span className="text-sm font-normal text-white/60">· {s.am}</span>
                </p>
                <p className="mt-1 text-sm text-white/75">{s.where}</p>
                <p className="mt-1 text-xs text-white/60">Bring: {s.bring}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/** The provider marketplace: Guday Geday agents, agencies, and how trust works. */
export function MarketplaceSection() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <Heading
          title="Hire someone you can trust"
          am="የሚታመን ሰው ይቅጠሩ"
          lead="Individuals and companies, all in one marketplace. You see who they are, what they have done, and what their past clients say."
        />
        <Link href="/providers/join" className="text-primary text-sm font-semibold hover:underline">
          Become a provider →
        </Link>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        {landingContent.marketplace.map((m) => (
          <Link
            key={m.type}
            href={`/hire?type=${m.type}`}
            className="group border-border bg-card hover:border-primary overflow-hidden rounded-md border transition-colors"
          >
            <div className="relative aspect-[16/10]">
              <Image src={m.image} alt={m.alt} fill sizes="(max-width: 768px) 100vw, 33vw" className="object-cover" />
            </div>
            <div className="p-5">
              <h3 className="text-lg font-semibold">
                {m.title} <span className="text-muted-foreground text-sm font-normal">· {m.am}</span>
              </h3>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{m.body}</p>
              <span className="text-primary mt-3 inline-block text-sm font-semibold group-hover:underline">Browse and compare →</span>
            </div>
          </Link>
        ))}
      </div>
      <dl className="bg-secondary/60 mt-8 grid gap-6 rounded-md p-6 sm:grid-cols-2 lg:grid-cols-4">
        {landingContent.trust.map((t) => (
          <div key={t.title}>
            <dt className="text-gov-ink font-semibold">{t.title}</dt>
            <dd className="text-muted-foreground mt-1 text-sm leading-relaxed">{t.body}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** Invite service-giving organizations to publish their requirements. */
export function OrganizationsInvite() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <div className="border-border bg-card grid overflow-hidden rounded-md border lg:grid-cols-2">
        <div className="relative min-h-64">
          <Image
            src={stockImages.cityCentre}
            alt="Office buildings in the centre of Addis Ababa"
            fill
            sizes="(max-width: 1024px) 100vw, 50vw"
            className="object-cover"
          />
        </div>
        <div className="p-6 md:p-10">
          <p className="text-primary text-sm font-semibold">For organizations · ለተቋማት</p>
          <h2 className="text-gov-ink mt-2 text-2xl font-bold md:text-3xl">Put your organization on the map. It is free.</h2>
          <p className="text-muted-foreground mt-3 leading-relaxed">
            Ministries, sub-city offices, banks, utilities, hospitals, universities and private service providers:
            register, publish your services with the documents, fees, steps and eligibility questions, and every
            path on the platform will send you customers who are ready.
          </p>
          <ul className="mt-5 space-y-2">
            {landingContent.organizationBenefits.map((b) => (
              <Check key={b}>{b}</Check>
            ))}
          </ul>
          <div className="mt-6 flex flex-wrap gap-3 text-sm font-semibold">
            <Link href="/organizations/join" className="bg-primary rounded-md px-5 py-2.5 text-white hover:bg-primary/90">
              Register your organization
            </Link>
            <Link href="/organizations" className="text-primary rounded-md px-5 py-2.5 ring-1 ring-primary/40 hover:bg-secondary">
              See organizations
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

/** Who the platform serves, each with a real Addis photo. */
export function WhoItsFor() {
  return (
    <section className="border-border bg-card border-y">
      <div className="mx-auto max-w-6xl px-4 py-14">
        <Heading title="Who it is for" am="ለማን ነው?" />
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {landingContent.audiences.map((a) => (
            <article key={a.title} className="border-border bg-background overflow-hidden rounded-md border">
              <div className="relative aspect-[4/3]">
                <Image src={a.image} alt={a.alt} fill sizes="(max-width: 640px) 100vw, 25vw" className="object-cover" />
              </div>
              <div className="p-4">
                <h3 className="font-semibold">{a.title}</h3>
                <p className="text-muted-foreground text-xs">{a.am}</p>
                <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{a.body}</p>
                <Link href={a.href} className="text-primary mt-3 inline-block text-sm font-semibold hover:underline">
                  {a.cta} →
                </Link>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
