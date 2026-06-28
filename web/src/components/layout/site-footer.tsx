import Link from "next/link";
import { Logo } from "./logo";
import { aboutProduct } from "@/content/about";

const productLinks = [
  { href: "/roadmap/new", label: "Find my path" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/roadmap", label: "My path" },
];

const companyLinks = [{ href: "/about", label: "About" }];

export function SiteFooter() {
  const year = new Date().getFullYear();

  return (
    <footer className="border-border bg-muted/15 mt-auto border-t">
      <div className="mx-auto max-w-6xl px-4 py-12">
        <div className="grid gap-10 md:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <Logo size="md" />
            <p className="text-muted-foreground mt-4 max-w-sm text-sm leading-relaxed">
              {aboutProduct.tagline}. Built for people navigating government
              processes in Addis Ababa—not paperwork experts.
            </p>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-widest">
              Product
            </h3>
            <ul className="mt-4 space-y-2">
              {productLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-muted-foreground hover:text-foreground text-sm"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-widest">
              Company
            </h3>
            <ul className="mt-4 space-y-2">
              {companyLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-muted-foreground hover:text-foreground text-sm"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
            <p className="text-muted-foreground mt-6 text-sm">
              Addis Ababa, Ethiopia
            </p>
          </div>
        </div>

        <div className="border-border text-muted-foreground mt-10 flex flex-col gap-2 border-t pt-8 text-xs sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {year} {aboutProduct.name}. All rights reserved.
          </p>
          <p>Built for people navigating government processes.</p>
        </div>
      </div>
    </footer>
  );
}
