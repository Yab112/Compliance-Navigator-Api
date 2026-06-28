"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { landingContent, landingQuickGoals } from "@/content/landing";
import { useUserStore } from "@/store";
import { cn } from "@/lib/utils";

export function LandingHero() {
  const user = useUserStore((s) => s.user);
  const { hero } = landingContent;

  return (
    <section className="relative overflow-hidden">
      <div className="from-primary/8 via-background to-background absolute inset-0 bg-gradient-to-b" />

      <div className="relative mx-auto max-w-3xl px-4 pt-16 pb-12 text-center md:pt-24 md:pb-16">
        <p className="text-primary mb-4 text-xs font-semibold tracking-widest uppercase">
          {hero.badge}
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-balance md:text-5xl md:leading-tight">
          {hero.headline}
        </h1>
        <p className="text-muted-foreground mx-auto mt-5 max-w-lg text-base leading-relaxed">
          {hero.subhead}
        </p>

        <div className="mt-10 grid gap-3 sm:grid-cols-3">
          {landingQuickGoals.map((g) => (
            <Link
              key={g.id}
              href={`/roadmap/new?goal=${g.id}`}
              className={cn(
                "group border-border rounded-xl border bg-card p-5 text-left",
                "hover:border-primary/40",
              )}
            >
              <p className="text-base font-semibold">{g.label}</p>
              <p className="text-muted-foreground mt-1 text-xs">{g.hint}</p>
              <span className="text-primary mt-4 inline-block text-xs font-medium">
                Start →
              </span>
            </Link>
          ))}
        </div>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link href="/roadmap/new">
            <Button size="lg" className="rounded-lg px-8">
              Other process
            </Button>
          </Link>
          <Link href="/how-it-works">
            <Button variant="ghost" size="lg" className="rounded-lg">
              How it works
            </Button>
          </Link>
        </div>

        {user && (
          <p className="text-muted-foreground mt-6 text-sm">
            Welcome back, {user.fullname}.{" "}
            <Link href="/roadmap" className="text-primary font-medium underline-offset-4 hover:underline">
              Continue your path
            </Link>
          </p>
        )}
      </div>
    </section>
  );
}
