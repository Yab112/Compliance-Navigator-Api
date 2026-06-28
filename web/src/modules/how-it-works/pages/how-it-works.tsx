import Image from "next/image";
import Link from "next/link";
import { howItWorks } from "@/content/how-it-works";
import { stockImages } from "@/content/stock-images";
import { Button } from "@/components/ui/button";

export function HowItWorksPage() {
  return (
    <div className="pb-20">
      <section className="relative h-48 w-full md:h-56">
        <Image
          src={stockImages.peopleWaiting}
          alt="How Compliance Navigator works for everyone"
          fill
          className="object-cover"
          priority
          sizes="100vw"
        />
        <div className="from-background/90 absolute inset-0 flex flex-col items-center justify-end bg-gradient-to-t px-4 pb-8 text-center">
          <h1 className="text-3xl font-semibold tracking-tight">
            {howItWorks.title}
          </h1>
          <p className="text-muted-foreground mt-2 text-sm">
            {howItWorks.subtitle}
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-3xl space-y-12 px-4 py-14">
        {howItWorks.steps.map((step) => (
          <div
            key={step.number}
            className="border-border grid items-stretch gap-0 overflow-hidden border md:grid-cols-2"
          >
            <div className="relative min-h-[200px] md:min-h-full">
              <Image
                src={step.image}
                alt={step.title}
                fill
                className="object-cover"
                sizes="50vw"
              />
            </div>
            <div className="flex flex-col justify-center p-6">
              <span className="text-primary text-2xl font-bold tabular-nums">
                {step.number}
              </span>
              <h2 className="mt-1 text-lg font-semibold">{step.title}</h2>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
                {step.body}
              </p>
            </div>
          </div>
        ))}
      </section>

      <section className="bg-muted/25 border-border border-y py-14">
        <div className="mx-auto grid max-w-4xl items-center gap-8 px-4 md:grid-cols-2">
          <div className="relative aspect-square overflow-hidden border">
            <Image
              src={stockImages.documents}
              alt="Your path on screen"
              fill
              className="object-cover"
              sizes="400px"
            />
          </div>
          <div>
            <h2 className="text-lg font-semibold">{howItWorks.result.title}</h2>
            <ul className="mt-4 space-y-2">
              {howItWorks.result.bullets.map((b) => (
                <li key={b} className="text-muted-foreground text-sm">
                  ✓ {b}
                </li>
              ))}
            </ul>
            <Link href="/roadmap/new" className="mt-6 inline-block">
              <Button size="lg">Find my path</Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
