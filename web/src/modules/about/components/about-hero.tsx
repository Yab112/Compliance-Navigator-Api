import Image from "next/image";
import Link from "next/link";
import { aboutProduct } from "@/content/about";
import { stockImages } from "@/content/stock-images";
import { Button } from "@/components/ui/button";

export function AboutHero() {
  return (
    <section className="border-border border-b">
      <div className="relative h-56 w-full md:h-72">
        <Image
          src={stockImages.peopleWaiting}
          alt="People waiting for government services"
          fill
          className="object-cover"
          priority
          sizes="100vw"
        />
        <div className="from-background/90 via-background/70 absolute inset-0 bg-gradient-to-t to-transparent" />
        <div className="absolute right-0 bottom-0 left-0 mx-auto max-w-6xl px-4 pb-8">
          <p className="text-primary mb-1 text-xs font-medium uppercase tracking-widest">
            {aboutProduct.name}
          </p>
          <h1 className="max-w-xl text-3xl font-semibold tracking-tight md:text-4xl">
            {aboutProduct.tagline}
          </h1>
        </div>
      </div>
      <div className="mx-auto max-w-6xl px-4 py-8">
        <p className="text-muted-foreground max-w-2xl text-sm leading-relaxed">
          {aboutProduct.description}
        </p>
        <Link href="/roadmap/new" className="mt-6 inline-block">
          <Button size="lg">Find my path</Button>
        </Link>
      </div>
    </section>
  );
}
