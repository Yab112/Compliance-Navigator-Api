"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useCatalogStats } from "@/api/catalog";
import { stockImages } from "@/content/stock-images";
import { useUserStore } from "@/store";

const POPULAR_SEARCHES = ["Passport", "Trade license", "TIN", "Birth certificate", "Driving license"];

export function LandingHero() {
  const router = useRouter();
  const user = useUserStore((s) => s.user);
  const stats = useCatalogStats().data?.payload;
  const [q, setQ] = useState("");

  const go = (term: string) =>
    router.push(term.trim() ? `/services?q=${encodeURIComponent(term.trim())}` : "/services");

  return (
    <section className="bg-primary relative overflow-hidden text-white">
      {/* Addis Ababa skyline under a green wash */}
      <Image src={stockImages.hero} alt="" fill priority sizes="100vw" className="object-cover object-[50%_70%]" />
      <div className="from-primary via-primary/90 to-primary/60 absolute inset-0 bg-gradient-to-r" />

      <div className="relative mx-auto grid max-w-6xl gap-10 px-4 py-12 md:py-16 lg:grid-cols-[1fr_320px] lg:items-center">
        <div>
          <p className="text-gov-yellow text-sm font-semibold">የእያንዳንዱን ቢሮ መስፈርት ይወቁ። የሚታመን ሰው ይቅጠሩ።</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-balance md:text-5xl md:leading-tight">
            Every office. Every requirement. One path.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-white/85">
            We connect the requirements of ministries, sub-city offices, banks and agencies into one
            map, so you see the whole path before you start. Do it yourself, or hire a verified agent,
            or agency rated by real clients.
          </p>

          <form
            role="search"
            className="mt-8 flex max-w-xl overflow-hidden rounded-md bg-white shadow-lg"
            onSubmit={(e) => {
              e.preventDefault();
              go(q);
            }}
          >
            <label htmlFor="hero-search" className="sr-only">
              What service do you need?
            </label>
            <input
              id="hero-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="What service do you need? · ምን አገልግሎት ይፈልጋሉ?"
              className="text-foreground min-w-0 flex-1 px-4 py-3.5 text-base outline-none"
            />
            <button type="submit" className="bg-gov-yellow text-gov-ink flex items-center gap-2 px-5 font-semibold hover:brightness-95">
              <HugeiconsIcon icon={Search01Icon} className="size-5" />
              <span className="hidden sm:inline">Search</span>
            </button>
          </form>
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
            <span className="text-white/70">Popular:</span>
            {POPULAR_SEARCHES.map((term) => (
              <button
                key={term}
                type="button"
                onClick={() => go(term)}
                className="rounded-full border border-white/30 px-3 py-1 text-white/90 hover:bg-white/10"
              >
                {term}
              </button>
            ))}
          </div>

          <div className="mt-6 flex flex-wrap gap-3 text-sm font-semibold">
            <Link href="/roadmap/new" className="bg-gov-yellow text-gov-ink rounded-md px-5 py-2.5 hover:brightness-95">
              Find my path
            </Link>
            <Link href="/hire" className="rounded-md px-5 py-2.5 ring-1 ring-white/50 hover:bg-white/10">
              Hire a verified provider
            </Link>
          </div>

          {user && (
            <p className="mt-6 text-sm text-white/85">
              Welcome back, {user.fullname}.{" "}
              <Link href="/roadmap" className="text-gov-yellow font-semibold hover:underline">
                Continue your path →
              </Link>
            </p>
          )}
        </div>

        {/* Live counts, floating over the skyline */}
        <dl aria-label="On the platform today · ዛሬ በመድረኩ ላይ" className="grid grid-cols-3 gap-4 lg:grid-cols-1 lg:gap-7 lg:justify-self-end">
          {[
            { label: "Services", am: "አገልግሎቶች", value: stats?.services, delay: "0s" },
            { label: "Institutions", am: "ተቋማት", value: stats?.institutions, delay: "-2s" },
            { label: "MESOB partner centers", am: "የመሶብ ማዕከላት", value: stats?.centers, delay: "-4s" },
          ].map((s) => (
            <div key={s.label} className="hero-float text-center lg:text-right" style={{ animationDelay: s.delay }}>
              <dt className="mt-1 text-xs font-medium text-white/85 lg:text-sm">
                {s.label}
                <span className="block text-white/60">{s.am}</span>
              </dt>
              <dd className="text-gov-yellow text-4xl font-bold tabular-nums drop-shadow-[0_2px_10px_rgba(0,0,0,0.35)] lg:text-6xl">
                {s.value != null ? s.value.toLocaleString("en") : "-"}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
