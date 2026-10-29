import { FlagStripe } from "../layout/flag-stripe";
import { Seal } from "../layout/logo";

type AuthCardProps = {
  title: string;
  am: string;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

/** Centered card used by every sign-in screen. */
export function AuthCard({ title, am, description, children, footer }: AuthCardProps) {
  return (
    <div className="bg-secondary/40 flex min-h-[calc(100dvh-var(--nav-h)-8rem)] items-start justify-center px-4 py-12 md:py-16">
      <div className="w-full max-w-md">
        <div className="border-border bg-card overflow-hidden rounded-md border shadow-sm">
          <FlagStripe />
          <div className="p-6 md:p-8">
            <div className="flex items-center gap-3">
              <Seal className="size-10" />
              <div>
                <h1 className="text-gov-ink text-xl font-bold">{title}</h1>
                <p className="text-muted-foreground text-sm">{am}</p>
              </div>
            </div>
            {description && <div className="text-muted-foreground mt-4 text-sm leading-relaxed">{description}</div>}
            <div className="mt-6">{children}</div>
          </div>
        </div>
        {footer && <div className="text-muted-foreground mt-4 space-y-2 text-center text-sm">{footer}</div>}
      </div>
    </div>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="border-destructive/30 bg-destructive/5 text-destructive rounded-md border px-3 py-2 text-sm">
      {message}
    </p>
  );
}
