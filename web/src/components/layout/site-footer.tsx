import Link from "next/link";
import { FlagStripe } from "@cn/ui/layout/flag-stripe";
import { Logo } from "@cn/ui/layout/logo";
import { siteIdentity } from "@cn/core/content/site";
import { LEGAL_DOCS, legalHref } from "@/content/legal";

const columns = [
  {
    title: "Services · አገልግሎቶች",
    links: [
      { href: "/services", label: "All services" },
      { href: "/roadmap/new", label: "Find my path" },
      { href: "/organizations", label: "Organizations" },
      { href: "/chat", label: "Ask a question" },
    ],
  },
  {
    title: "Marketplace · ገበያ",
    links: [
      { href: "/hire?type=guday_geday", label: "Guday Geday agents" },
      { href: "/hire?type=agency", label: "Agencies" },
      { href: "/providers/join", label: "Become a provider" },
    ],
  },
  {
    title: "Partners · አጋሮች",
    links: [
      { href: "/organizations/join", label: "Register your organization" },
      { href: "/about", label: "About us" },
      { href: "/how-it-works", label: "How it works" },
    ],
  },
];

export function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="bg-gov-ink mt-auto text-white">
      <FlagStripe />
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Logo size="md" inverted />
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-white/75">
              Every requirement across Ethiopian offices, connected into one path, and the trusted people
              who can get it done for you.
            </p>
          </div>
          {columns.map((col) => (
            <div key={col.title}>
              <h3 className="text-gov-yellow text-sm font-semibold">{col.title}</h3>
              <ul className="mt-4 space-y-2">
                {col.links.map((link) => (
                  <li key={link.href}>
                    <Link href={link.href} className="text-sm text-white/75 hover:text-white hover:underline">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <p className="mt-10 rounded-md bg-white/5 px-4 py-3 text-xs leading-relaxed text-white/80">
          {siteIdentity.disclaimer}
        </p>

        <nav aria-label="Legal" className="mt-8 border-t border-white/15 pt-6">
          <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs">
            <li>
              <Link href="/legal" className="text-gov-yellow font-semibold hover:underline">
                Legal · ሕጋዊ
              </Link>
            </li>
            {LEGAL_DOCS.map((doc) => (
              <li key={doc.key}>
                <Link href={legalHref(doc.key)} className="text-white/75 hover:text-white hover:underline">
                  {doc.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        <div className="mt-6 flex flex-col gap-2 text-xs text-white/60 sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {year} {siteIdentity.name}. Addis Ababa, Ethiopia.
          </p>
          <p>
            Service data: <a href="https://mesobcenter.et" className="underline hover:text-white" target="_blank" rel="noreferrer">mesobcenter.et</a>
          </p>
        </div>
      </div>
    </footer>
  );
}
