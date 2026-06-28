import Image from "next/image";
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { aboutSections } from "@/content/about";

export function BuiltForGrid() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <div className="mb-10 max-w-2xl">
        <h2 className="text-2xl font-semibold tracking-tight">
          Built for people—not paperwork experts
        </h2>
        <p className="text-muted-foreground mt-3 text-sm leading-relaxed">
          If you live in Addis Ababa and deal with government offices, this is
          for you. Not only businesses. Not only lawyers. Everyone.
        </p>
      </div>
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {aboutSections.builtForPeople.map((item) => (
          <Card key={item.title} className="overflow-hidden pt-0">
            <div className="relative h-48">
              <Image
                src={item.image}
                alt={item.title}
                fill
                className="object-cover"
                sizes="33vw"
              />
            </div>
            <CardHeader>
              <CardTitle className="text-base leading-snug">
                {item.title}
              </CardTitle>
              <CardDescription className="leading-relaxed">
                {item.body}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </section>
  );
}
