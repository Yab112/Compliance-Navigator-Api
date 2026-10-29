import { formatBirr } from "@/api/payments";
import { Badge } from "@/components/ui/badge";
import type { HirePaymentStatus } from "@/types/payments";

const PAYMENT_STATUS: Record<HirePaymentStatus, { label: string; className: string }> = {
  unpaid: { label: "Unpaid", className: "bg-zinc-200 text-zinc-800" },
  failed: { label: "Unpaid", className: "bg-zinc-200 text-zinc-800" },
  pending: { label: "Payment pending", className: "bg-amber-100 text-amber-900" },
  paid: { label: "Paid ✓", className: "bg-emerald-100 text-emerald-900" },
  refunded: { label: "Refunded", className: "bg-sky-100 text-sky-900" },
};

export function PaymentBadge({ status }: { status?: HirePaymentStatus | null }) {
  const s = PAYMENT_STATUS[status ?? "unpaid"];
  return <Badge className={s.className}>{s.label}</Badge>;
}

/** "Price: 1,200 ETB · note" line with the payment badge. Renders nothing until a price is set. */
export function PriceLine({
  price,
  note,
  status,
  vat,
}: {
  price?: number | null;
  note?: string | null;
  status?: HirePaymentStatus | null;
  /** VAT added on top of the price (VAT-registered providers) */
  vat?: number | null;
}) {
  if (price == null) return null;
  return (
    <p className="flex flex-wrap items-center gap-2 text-xs">
      <span>
        Price · ዋጋ: <strong className="text-gov-ink tabular-nums">{formatBirr(price)} ETB</strong>
        {vat ? <span className="text-muted-foreground"> + VAT {formatBirr(vat)} ETB</span> : null}
        {note ? <span className="text-muted-foreground"> · {note}</span> : null}
      </span>
      <PaymentBadge status={status} />
    </p>
  );
}
