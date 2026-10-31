import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { formatLegalDate, LEGAL_BY_KEY, legalHref, type LegalBlock, type LegalDoc } from "@/content/legal";
import { DraftBanner } from "@/modules/legal/components/draft-banner";

function Block({ block }: { block: LegalBlock }) {
  if (typeof block === "string") return <p>{block}</p>;
  if ("list" in block) {
    return (
      <ul className="list-disc space-y-2 pl-5">
        {block.list.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  }
  if ("note" in block) {
    return <p className="bg-secondary/60 rounded-md px-4 py-3">{block.note}</p>;
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {block.see.map((key) => (
        <li key={key}>
          <Link href={legalHref(key)} className="border-border hover:border-primary text-primary inline-block rounded-md border px-3 py-1.5 text-sm">
            {LEGAL_BY_KEY[key].title}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Long-form legal page: draft banner, version and date, contents with anchors, then the sections. */
export function LegalDocument({ doc }: { doc: LegalDoc }) {
  return (
    <PageShell title={`${doc.title} · ${doc.titleAm}`} navLabel={doc.title} description={doc.summary} maxWidth="lg">
      <DraftBanner className="mb-6" />
      <p className="text-muted-foreground mb-6 text-sm">
        Version {doc.version} · Effective {formatLegalDate(doc.effective)}
      </p>

      <nav aria-labelledby="toc-title" className="border-border bg-card mb-10 rounded-md border p-5">
        <h2 id="toc-title" className="text-gov-ink mb-3 text-sm font-semibold">
          Contents · ማውጫ
        </h2>
        <ol className="space-y-1.5 text-sm">
          {doc.sections.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="text-primary hover:underline">
                {s.title}
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <article className="space-y-10">
        {doc.sections.map((s) => (
          <section key={s.id} id={s.id} aria-labelledby={`${s.id}-title`} className="scroll-mt-24">
            <h2 id={`${s.id}-title`} className="text-gov-ink mb-3 text-lg font-semibold">
              <a href={`#${s.id}`} className="hover:underline">
                {s.title}
              </a>
            </h2>
            <div className="text-foreground/90 space-y-3 leading-relaxed break-words">
              {s.body.map((block, i) => (
                <Block key={i} block={block} />
              ))}
            </div>
          </section>
        ))}
      </article>

      <p className="text-muted-foreground border-border mt-12 border-t pt-6 text-sm">
        <Link href="/legal" className="text-primary hover:underline">
          All legal documents
        </Link>
      </p>
    </PageShell>
  );
}
