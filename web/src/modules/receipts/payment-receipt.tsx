"use client";

import Link from "next/link";
import { usePaymentReceipt } from "@cn/core/api/payments";
import { formatDateTime } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { ReceiptBlock, ReceiptFrame, ReceiptRow, money } from "@/modules/receipts/receipt-layout";

/**
 * Receipt for a paid hire. The provider also sees how the payment became their earnings; their copy
 * lives at /receipts/statement so the breadcrumb leads back to their profile, not to My hires.
 */
export function PaymentReceiptPage({ txRef, asStatement = false }: { txRef: string; asStatement?: boolean }) {
  const gate = useAuthGate();
  const { data, isLoading, isError, refetch } = usePaymentReceipt(txRef, gate === "ready");
  const r = data?.payload.receipt;
  const cur = r?.currency || "ETB";
  const s = r?.statement;

  return (
    <ReceiptFrame
      title={asStatement ? "Statement · መግለጫ" : "Receipt · ደረሰኝ"}
      navLabel={asStatement ? "Statement" : "Receipt"}
      heading={s ? "Payment receipt and statement" : "Payment receipt"}
      gate={gate}
      isLoading={isLoading}
      isError={isError}
      errorMessage="We could not find a receipt for this payment. It may not be paid yet, or it belongs to another account."
      onRetry={() => refetch()}
      receipt={r}
    >
      {r && (
        <>
          <div className="grid gap-5 sm:grid-cols-2">
            <ReceiptBlock title="Paid by">
              <p className="text-sm font-medium">{r.client.name ?? "-"}</p>
              {r.client.email && <p className="text-muted-foreground text-sm">{r.client.email}</p>}
            </ReceiptBlock>
            <ReceiptBlock title="Provider">
              <p className="text-sm font-medium">{r.provider.name ?? "-"}</p>
              {r.provider.registration_no && <p className="text-muted-foreground text-sm">Reg. no. {r.provider.registration_no}</p>}
              {r.provider.vat_number && <p className="text-muted-foreground text-sm">VAT reg. no. {r.provider.vat_number}</p>}
            </ReceiptBlock>
          </div>

          <ReceiptBlock title="Job">
            <p className="text-sm font-medium">{r.job.title ?? "-"}</p>
            {r.job.service && <p className="text-muted-foreground text-sm">{r.job.service}</p>}
            {r.job.delivered && (
              <p className="mt-1 text-sm whitespace-pre-line">
                <span className="text-muted-foreground">Delivered: </span>
                {r.job.delivered}
              </p>
            )}
          </ReceiptBlock>

          <ReceiptBlock title="Details">
            <dl className="divide-border divide-y">
              {r.lines.map((l, i) => (
                <ReceiptRow key={`${l.label}-${i}`} label={l.label} value={money(l.amount, cur)} />
              ))}
              <ReceiptRow label="Total paid" value={money(r.total, cur)} strong className="border-t-2 pt-2" />
            </dl>
          </ReceiptBlock>

          <ReceiptBlock title="Payment">
            <dl>
              {r.payment.method && <ReceiptRow label="Method" value={r.payment.method} />}
              {r.payment.gateway && <ReceiptRow label="Through" value={r.payment.gateway} />}
              {r.payment.reference && <ReceiptRow label="Reference" value={<span className="font-mono text-xs break-all">{r.payment.reference}</span>} />}
              <ReceiptRow label="Our reference" value={<span className="font-mono text-xs break-all">{txRef}</span>} />
            </dl>
          </ReceiptBlock>

          {r.refunds && r.refunds.length > 0 && (
            <ReceiptBlock title="Refunds">
              <dl>
                {r.refunds.map((f) => (
                  <ReceiptRow
                    key={f.id}
                    label={f.status === "refunded" ? `Refunded ${formatDateTime(f.completed_at)}` : "Refund on its way"}
                    value={
                      f.status === "refunded" ? (
                        <Link href={`/receipts/refund/${f.id}`} className="text-primary underline">-{money(f.amount, cur)}</Link>
                      ) : (
                        `-${money(f.amount, cur)}`
                      )
                    }
                  />
                ))}
              </dl>
            </ReceiptBlock>
          )}

          {s && (
            <ReceiptBlock title="Your statement" className="bg-secondary/40 rounded-lg border p-4 print:bg-transparent">
              <dl>
                <ReceiptRow label="Your price" value={money(s.price, cur)} />
                {s.provider_vat > 0 && (
                  <ReceiptRow label={`VAT you collected (${s.vat_rate}%, you file it)`} value={`+${money(s.provider_vat, cur)}`} />
                )}
                <ReceiptRow label={`Platform commission (${s.commission_percent}%)`} value={`-${money(s.commission, cur)}`} />
                <ReceiptRow label={`VAT on commission (${s.vat_rate}%)`} value={`-${money(s.commission_vat, cur)}`} />
                <ReceiptRow label="Credited to your earnings" value={money(s.provider_amount, cur)} strong className="border-t pt-2" />
              </dl>
            </ReceiptBlock>
          )}
        </>
      )}
    </ReceiptFrame>
  );
}
