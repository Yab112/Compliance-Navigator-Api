import Image from "next/image";
import Link from "next/link";
import { aboutSections, projectCredit } from "@/content/about";
import { stockImages } from "@/content/stock-images";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { AboutHero } from "../components/about-hero";
import { BuiltForGrid } from "../components/built-for-grid";

export function AboutPage() {
  return (
    <div className="pb-20">
      <AboutHero />

      <section className="mx-auto max-w-6xl px-4 py-14">
        <div className="grid items-center gap-8 md:grid-cols-2">
          <div className="relative aspect-[4/3] overflow-hidden border">
            <Image
              src={aboutSections.mission.image}
              alt="People in line for public services"
              fill
              className="object-cover"
              sizes="50vw"
            />
          </div>
          <div>
            <h2 className="text-xl font-semibold">The problem everyone knows</h2>
            <p className="text-muted-foreground mt-4 text-sm leading-relaxed">
              {aboutSections.mission.text}
            </p>
          </div>
        </div>
      </section>

      <section className="bg-muted/20 border-border border-y py-14">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="mb-8 text-xl font-semibold">What you get at every step</h2>
          <div className="grid gap-6 sm:grid-cols-2">
            {aboutSections.principles.map((item) => (
              <Card key={item.title} className="overflow-hidden pt-0">
                <div className="relative h-44">
                  <Image
                    src={item.image}
                    alt={item.title}
                    fill
                    className="object-cover"
                    sizes="50vw"
                  />
                </div>
                <CardHeader>
                  <CardTitle className="text-base">{item.title}</CardTitle>
                  <CardDescription className="leading-relaxed">
                    {item.body}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <BuiltForGrid />

      <section className="border-border relative border-t">
        <div className="relative h-48 md:h-56">
          <Image
            src={stockImages.peopleHelp}
            alt="Community and support"
            fill
            className="object-cover"
            sizes="100vw"
          />
          <div className="bg-background/85 absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
            <p className="text-lg font-medium">Your turn is next.</p>
            <p className="text-muted-foreground mt-1 max-w-md text-sm">
              Pick passport, ID, or license—and see your path in under a minute.
            </p>
            <Link href="/roadmap/new" className="mt-5">
              <Button size="lg">Find my path</Button>
            </Link>
          </div>
        </div>
      </section>

      <p className="text-muted-foreground mx-auto max-w-6xl px-4 pt-8 text-center text-xs">
        {projectCredit.builtIn}
      </p>
    </div>
  );
}
