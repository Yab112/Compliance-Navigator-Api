import Image from "next/image";
import Link from "next/link";
import { aboutSections, projectCredit } from "@/content/about";
import { photoCredits } from "@/content/photo-credits";
import { stockImages } from "@/content/stock-images";
import { AboutHero } from "@/modules/about/components/about-hero";
import { BuiltForGrid } from "@/modules/about/components/built-for-grid";

function SectionHeading({ title, am }: { title: string; am: string }) {
  return (
    <div className="mb-8">
      <h2 className="text-gov-ink text-2xl font-bold tracking-tight">{title}</h2>
      <p className="text-muted-foreground text-sm">{am}</p>
    </div>
  );
}

export function AboutPage() {
  return (
    <div>
      <AboutHero />

      <section className="mx-auto max-w-6xl px-4 py-14">
        <div className="grid items-center gap-10 md:grid-cols-2">
          <div className="relative aspect-[4/3] overflow-hidden rounded-md">
            <Image src={aboutSections.mission.image} alt={aboutSections.mission.alt} fill className="object-cover" sizes="(max-width: 768px) 100vw, 50vw" />
          </div>
          <div>
            <SectionHeading title="The problem everyone knows" am="ሁሉም የሚያውቀው ችግር" />
            <p className="text-muted-foreground leading-relaxed">{aboutSections.mission.text}</p>
          </div>
        </div>
      </section>

      <section className="border-border bg-card border-y py-14">
        <div className="mx-auto max-w-6xl px-4">
          <SectionHeading title="What you get at every step" am="በእያንዳንዱ ደረጃ የሚያገኙት" />
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {aboutSections.principles.map((item) => (
              <article key={item.title} className="border-border overflow-hidden rounded-md border">
                <div className="relative aspect-[4/3]">
                  <Image src={item.image} alt={item.alt} fill className="object-cover" sizes="(max-width: 640px) 100vw, 25vw" />
                </div>
                <div className="p-4">
                  <h3 className="font-semibold">{item.title}</h3>
                  <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{item.body}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <BuiltForGrid />

      <section className="border-border bg-card border-y py-14">
        <div className="mx-auto max-w-6xl px-4">
          <SectionHeading title="What makes us different" am="ልዩ የሚያደርገን" />
          <div className="grid gap-6 md:grid-cols-3">
            {aboutSections.difference.map((d) => (
              <div key={d.title} className="border-gov-yellow border-t-4 pt-4">
                <h3 className="font-semibold">{d.title}</h3>
                <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{d.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="partners" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-14">
        <SectionHeading title="Partnership with MESOB" am="ከመሶብ ጋር ያለን አጋርነት" />
        <p className="text-muted-foreground max-w-3xl leading-relaxed">{aboutSections.partnership}</p>
      </section>

      <section className="bg-gov-ink text-white">
        <div className="mx-auto max-w-6xl px-4 py-14">
          <p className="text-gov-yellow text-sm font-semibold">ለተቋማት</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">For organizations that give services</h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-white/75">
            Ministries, sub-city offices, banks, utilities, hospitals, universities and private providers.
          </p>
          <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
            {aboutSections.forOrganizations.map((f) => (
              <div key={f.title} >
                <dt className="font-semibold">{f.title}</dt>
                <dd className="mt-1 text-sm leading-relaxed text-white/75">{f.body}</dd>
              </div>
            ))}
          </dl>
          <Link href="/organizations/join" className="bg-gov-yellow text-gov-ink mt-8 inline-block rounded-md px-5 py-2.5 text-sm font-semibold hover:brightness-95">
            Register your organization
          </Link>
        </div>
      </section>

      <section className="relative overflow-hidden">
        <Image src={stockImages.merkato} alt="" fill className="object-cover" sizes="100vw" />
        <div className="bg-primary/85 absolute inset-0" />
        <div className="relative mx-auto max-w-6xl px-4 py-14 text-center text-white">
          <p className="text-xl font-bold">Your turn is next. · ተራዎ ደርሷል።</p>
          <p className="mx-auto mt-2 max-w-md text-sm text-white/85">
            See your connected path in under a minute, or hire someone you can trust to walk it for you.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3 text-sm font-semibold">
            <Link href="/roadmap/new" className="bg-gov-yellow text-gov-ink rounded-md px-6 py-2.5 hover:brightness-95">
              Find my path
            </Link>
            <Link href="/hire" className="rounded-md px-6 py-2.5 ring-1 ring-white/60 hover:bg-white/10">
              Hire a provider
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-muted-foreground text-center text-xs">{projectCredit.builtIn}</p>
        <details className="text-muted-foreground mt-4 text-xs">
          <summary className="hover:text-foreground cursor-pointer text-center">Photo credits</summary>
          <ul className="mt-3 grid gap-1 sm:grid-cols-2">
            {photoCredits.map((c) => (
              <li key={c.key}>
                <a href={c.source} target="_blank" rel="noreferrer" className="hover:underline">
                  {c.title}
                </a>
                {`, ${c.author}, `}
                {c.licenseUrl ? (
                  <a href={c.licenseUrl} target="_blank" rel="noreferrer" className="hover:underline">
                    {c.license}
                  </a>
                ) : (
                  c.license
                )}
                , via Wikimedia Commons
              </li>
            ))}
          </ul>
        </details>
      </section>
    </div>
  );
}
