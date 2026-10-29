import { cn } from "@cn/core/lib/utils";
import { PageNav } from "@cn/ui/layout/page-nav";

type AdminPageProps = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
};

/** Standard header + body for admin screens. */
export function AdminPage({ title, description, actions, children, className }: AdminPageProps) {
  return (
    <div className={cn("px-4 py-6 lg:px-8", className)}>
      <PageNav label={title.split(" · ")[0]} />
      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {description && (
            <p className="text-muted-foreground mt-1 max-w-2xl text-xs leading-relaxed">
              {description}
            </p>
          )}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </header>
      {children}
    </div>
  );
}
