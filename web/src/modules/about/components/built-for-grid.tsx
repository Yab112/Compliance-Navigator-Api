import Image from "next/image";
import { aboutSections } from "@/content/about";

export function BuiltForGrid() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-14">
      <div className="mb-10 max-w-2xl">
        <div>
          <h2 className="text-gov-ink text-2xl font-bold tracking-tight">Built for people, not paperwork experts</h2>
          <p className="text-muted-foreground text-sm">ለሁሉም ሰው የተሰራ</p>
        </div>
        <p className="text-muted-foreground mt-4 text-sm leading-relaxed">
          If you deal with government offices in Ethiopia, this is for you. Not only businesses. Not only
          lawyers. Everyone.
        </p>
      </div>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {aboutSections.builtForPeople.map((item) => (
          <article key={item.title} className="border-border bg-card overflow-hidden rounded-md border">
            <div className="relative aspect-[3/2]">
              <Image src={item.image} alt={item.alt} fill className="object-cover" sizes="(max-width: 640px) 100vw, 33vw" />
            </div>
            <div className="p-4">
              <h3 className="leading-snug font-semibold">{item.title}</h3>
              <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{item.body}</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
