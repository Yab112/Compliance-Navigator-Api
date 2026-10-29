"use client";

import { formatETB } from "@cn/core/api/payments";
import { PageShell } from "@/components/layout/page-shell";
import { Button } from "@cn/ui/button";
import { cn } from "@cn/core/lib/utils";
import { ErrorState, LoadingState, formatDateTime } from "@cn/ui/guday/shared";
import type { ReceiptIssuer } from "@cn/core/types/payments";

/** Money in the receipt's currency, two decimals. */
export function money(amount: number | null | undefined, currency = "ETB"): string {
  return formatETB(amount).replace(/ ETB$/, ` ${currency || "ETB"}`);
}

export function ReceiptRow({ label, value, strong, className }: { label: string; value: React.ReactNode; strong?: boolean; className?: string }) {
  return (
    <div className={cn("flex items-baseline justify-between gap-4 py-1.5 text-sm", strong && "font-semibold", className)}>
      <dt className={cn(!strong && "text-muted-foreground")}>{label}</dt>
      <dd className="text-right tabular-nums">{value}</dd>
    </div>
  );
}

export function ReceiptBlock({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("break-inside-avoid", className)}>
      <h2 className="text-muted-foreground mb-1.5 text-[11px] font-semibold tracking-wide uppercase">{title}</h2>
      {children}
    </section>
  );
}

type FrameProps = {
  title: string;
  navLabel?: string;
  heading: string;
  gate: "loading" | "ready";
  isLoading: boolean;
  isError: boolean;
  errorMessage: string;
  onRetry: () => void;
  receipt: { receipt_no: string; paid_at: string | null; notice: string | null; issued_by: ReceiptIssuer } | undefined;
  children?: React.ReactNode;
};

/** Page around a receipt: loading and error states, the print button, issuer header and the notice. */
export function ReceiptFrame({ title, navLabel = "Receipt", heading, gate, isLoading, isError, errorMessage, onRetry, receipt, children }: FrameProps) {
  const issuer = receipt?.issued_by;
  return (
    <PageShell title={title} navLabel={navLabel} maxWidth="lg">
      {gate === "loading" || isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState message={errorMessage} onRetry={onRetry} />
      ) : receipt && issuer ? (
        <>
          <div className="mb-4 flex justify-end" data-print-hide>
            <Button type="button" variant="outline" onClick={() => window.print()}>
              Print or save as PDF
            </Button>
          </div>
          <article
            data-print-receipt
            aria-label={heading}
            className="border-border bg-card text-foreground mx-auto max-w-2xl space-y-6 rounded-xl border p-6 md:p-8 print:max-w-none print:rounded-none print:bg-white print:text-black"
          >
            <header className="flex flex-col gap-4 border-b pb-5 sm:flex-row sm:items-start sm:justify-between">
              <div className="text-sm leading-relaxed">
                <p className="text-base font-bold">{issuer.legal_name}</p>
                {issuer.tin && <p>TIN: {issuer.tin}</p>}
                {issuer.vat_number && <p>VAT reg. no.: {issuer.vat_number}</p>}
                {issuer.address && <p className="text-muted-foreground">{issuer.address}</p>}
              </div>
              <div className="text-sm sm:text-right">
                <p className="text-lg font-bold">{heading}</p>
                <p>
                  No. <span className="font-mono">{receipt.receipt_no}</span>
                </p>
                <p className="text-muted-foreground">{formatDateTime(receipt.paid_at)}</p>
              </div>
            </header>
            {children}
            {receipt.notice && <p className="text-muted-foreground border-t pt-4 text-[11px] leading-relaxed">{receipt.notice}</p>}
          </article>
        </>
      ) : null}
    </PageShell>
  );
}
