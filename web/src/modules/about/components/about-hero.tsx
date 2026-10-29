import Image from "next/image";
import Link from "next/link";
import { aboutProduct, aboutSections } from "@/content/about";
import { PageNav } from "@/components/layout/page-nav";

export function AboutHero() {
  return (
    <section className="relative overflow-hidden text-white">
      <Image
        src={aboutSections.hero.image}
        alt={aboutSections.hero.alt}
        fill
        priority
        sizes="100vw"
        className="object-cover"
      />
      <div className="from-gov-ink via-gov-ink/85 to-gov-ink/40 absolute inset-0 bg-gradient-to-r" />
      <div className="relative mx-auto max-w-6xl px-4 py-16 md:py-24">
        <PageNav label="About" tone="onDark" className="mb-4" />
        <p className="text-gov-yellow text-sm font-semibold">ስለ እኛ · About us</p>
        <h1 className="mt-2 max-w-2xl text-3xl font-bold tracking-tight text-balance md:text-5xl">
          {aboutProduct.tagline}
        </h1>
        <p className="mt-5 max-w-2xl leading-relaxed text-white/85">{aboutProduct.description}</p>
        <div className="mt-8 flex flex-wrap gap-3 text-sm font-semibold">
          <Link href="/roadmap/new" className="bg-gov-yellow text-gov-ink rounded-md px-5 py-2.5 hover:brightness-95">
            Find my path
          </Link>
          <Link href="/hire" className="rounded-md px-5 py-2.5 ring-1 ring-white/50 hover:bg-white/10">
            Hire a provider
          </Link>
        </div>
      </div>
    </section>
  );
}
