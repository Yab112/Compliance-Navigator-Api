import { cn } from "@cn/core/lib/utils";
import { PageNav } from "@cn/ui/layout/page-nav";

type PageShellProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  maxWidth?: "md" | "lg" | "xl" | "full";
  /** Short name for breadcrumbs and "Back to …" on other pages; defaults to the English part of the title */
  navLabel?: string;
};

const maxWidthClass = {
  md: "max-w-lg",
  lg: "max-w-3xl",
  xl: "max-w-6xl",
  full: "max-w-6xl",
};

/** Standard page: green title band with breadcrumb, then the content column. */
export function PageShell({
  title,
  description,
  children,
  className,
  maxWidth = "xl",
  navLabel,
}: PageShellProps) {
  return (
    <>
      <header className="border-border bg-secondary/60 border-b">
        <div className={cn("mx-auto px-4 py-6 md:py-8", maxWidthClass[maxWidth])}>
          <PageNav label={navLabel ?? title.split(" · ")[0]} />
          <h1 className="text-gov-ink border-gov-green border-l-4 pl-3 text-2xl font-bold tracking-tight md:text-3xl">
            {title}
          </h1>
          {description && (
            <p className="text-muted-foreground mt-3 max-w-3xl text-sm leading-relaxed">{description}</p>
          )}
        </div>
      </header>
      <div className={cn("mx-auto px-4 py-8", maxWidthClass[maxWidth], className)}>{children}</div>
    </>
  );
}
