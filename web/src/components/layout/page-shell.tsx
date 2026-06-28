import { cn } from "@/lib/utils";

type PageShellProps = {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  maxWidth?: "md" | "lg" | "xl" | "full";
};

const maxWidthClass = {
  md: "max-w-lg",
  lg: "max-w-3xl",
  xl: "max-w-6xl",
  full: "max-w-6xl",
};

export function PageShell({
  title,
  description,
  children,
  className,
  maxWidth = "xl",
}: PageShellProps) {
  return (
    <div className={cn("mx-auto px-4 py-10", maxWidthClass[maxWidth], className)}>
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">
          {title}
        </h1>
        {description && (
          <p className="text-muted-foreground mt-2 text-sm leading-relaxed">
            {description}
          </p>
        )}
      </header>
      {children}
    </div>
  );
}
