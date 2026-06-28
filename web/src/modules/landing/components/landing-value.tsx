import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { landingContent } from "@/content/landing";
import { stockImages } from "@/content/stock-images";

export function LandingValue() {
  const { value } = landingContent;

  return (
    <section className="mx-auto max-w-6xl px-4 py-16 md:py-20">
      <div className="grid items-center gap-10 md:grid-cols-2 md:gap-14">
        <div className="relative aspect-5/4 overflow-hidden rounded-xl">
          <Image
            src={stockImages.officeDetail}
            alt="Government office guidance"
            fill
            className="object-cover"
            sizes="(max-width: 768px) 100vw, 50vw"
          />
        </div>
        <div>
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">
            {value.title}
          </h2>
          <ul className="mt-6 space-y-4">
            {value.points.map((p) => (
              <li
                key={p}
                className="text-muted-foreground flex gap-3 text-sm leading-relaxed md:text-base"
              >
                <span className="text-primary mt-0.5 shrink-0">✓</span>
                {p}
              </li>
            ))}
          </ul>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/roadmap/new?goal=passport">
              <Button size="lg" className="rounded-lg">
                Try passport path
              </Button>
            </Link>
            <Link href="/about">
              <Button variant="outline" size="lg" className="rounded-lg">
                About us
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
