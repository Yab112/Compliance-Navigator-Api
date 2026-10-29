import Link from "next/link";
import { cn } from "@/lib/utils";
import { siteIdentity } from "@/content/site";

type LogoProps = {
  showName?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
  /** Light text for dark backgrounds (footer) */
  inverted?: boolean;
};

/** Round seal mark, a portal emblem, deliberately not the national emblem. */
export function Seal({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={cn("shrink-0", className)} aria-hidden>
      <circle cx="24" cy="24" r="23" fill="var(--gov-ink)" />
      <circle cx="24" cy="24" r="19.5" fill="none" stroke="var(--gov-yellow)" strokeWidth="1.5" />
      <circle cx="24" cy="24" r="16" fill="var(--gov-green)" />
      {/* Document with a check, "your paperwork, in order" */}
      <path d="M17 13h10l5 5v17H17z" fill="#fff" />
      <path d="M27 13v5h5" fill="none" stroke="var(--gov-green)" strokeWidth="1.2" />
      <path d="M20.5 26.5l3 3 5.5-6" fill="none" stroke="var(--gov-red)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const sizes = {
  sm: { seal: "size-8", name: "text-sm", am: "text-[10px]" },
  md: { seal: "size-11", name: "text-base", am: "text-xs" },
  lg: { seal: "size-14", name: "text-lg md:text-xl", am: "text-xs md:text-sm" },
};

export function Logo({ showName = true, className, size = "md", inverted }: LogoProps) {
  const s = sizes[size];
  return (
    <Link href="/" className={cn("flex items-center gap-3", className)}>
      <Seal className={s.seal} />
      {showName && (
        <span className="flex flex-col leading-tight">
          <span className={cn("font-bold tracking-tight", s.name, inverted ? "text-white" : "text-gov-ink")}>
            {siteIdentity.name}
          </span>
          <span className={cn(s.am, inverted ? "text-white/70" : "text-muted-foreground")}>
            {siteIdentity.nameAm}
          </span>
        </span>
      )}
    </Link>
  );
}
