import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import { formatLegalDate, LEGAL_DOCS, legalHref } from "@/content/legal";
import { DraftBanner } from "@/modules/legal/components/draft-banner";

export function LegalIndexPage() {
  return (
    <PageShell
      title="Legal · ሕጋዊ ሰነዶች"
      navLabel="Legal"
      description="The agreements and policies that apply when you use Compliance Navigator. Everyone accepts the Terms, the Privacy Policy and the Marketplace Rules when signing up; providers also accept the Provider Agreement."
      maxWidth="lg"
    >
      <DraftBanner className="mb-6" />
      <ul className="space-y-4">
        {LEGAL_DOCS.map((doc) => (
          <li key={doc.key} className="border-border bg-card rounded-md border p-5">
            <h2 className="text-gov-ink font-semibold">
              <Link href={legalHref(doc.key)} className="hover:underline">
                {doc.title}
              </Link>{" "}
              <span className="text-muted-foreground text-sm font-normal">· {doc.titleAm}</span>
            </h2>
            <p className="text-muted-foreground mt-2 text-sm leading-relaxed">{doc.summary}</p>
            <p className="text-muted-foreground mt-2 text-xs">
              Version {doc.version} · Effective {formatLegalDate(doc.effective)}
            </p>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-8 text-sm">
        We set only one cookie, which keeps you signed in. It is strictly necessary, so there is no cookie banner. See{" "}
        <Link href="/legal/privacy#cookies" className="text-primary underline">
          Cookies and browser storage
        </Link>{" "}
        in the Privacy Policy.
      </p>
    </PageShell>
  );
}
