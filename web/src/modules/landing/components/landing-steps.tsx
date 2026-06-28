import { landingContent } from "@/content/landing";

export function LandingSteps() {
  const { steps } = landingContent;

  return (
    <section className="border-border border-y bg-muted/30 py-12 md:py-16">
      <div className="mx-auto flex max-w-3xl flex-col gap-8 px-4 sm:flex-row sm:justify-between sm:gap-4">
        {steps.map((s) => (
          <div key={s.n} className="flex-1 text-center sm:text-left">
            <span className="text-primary text-2xl font-bold tabular-nums">
              {s.n}
            </span>
            <p className="mt-2 font-medium">{s.title}</p>
            <p className="text-muted-foreground mt-1 text-sm">{s.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
