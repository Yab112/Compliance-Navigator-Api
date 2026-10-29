"use client";

import Link from "next/link";
import { useRefundReceipt } from "@cn/core/api/payments";
import { formatDateTime } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { ReceiptBlock, ReceiptFrame, ReceiptRow, money } from "@/modules/receipts/receipt-layout";

/** Receipt for money given back to a client. The provider (and staff) also see what came out of each side. */
export function RefundReceiptPage({ id }: { id: string }) {
  const gate = useAuthGate();
  const { data, isLoading, isError, refetch } = useRefundReceipt(id, gate === "ready");
  const r = data?.payload.receipt;
  const cur = r?.currency || "ETB";
  const s = r?.statement;

  return (
    <ReceiptFrame
      title="Refund receipt · የተመላሽ ደረሰኝ"
      navLabel="Refund receipt"
      heading="Refund receipt"
      gate={gate}
      isLoading={isLoading}
      isError={isError}
      errorMessage="We could not find this refund receipt. Receipts are ready once the money has gone back, and only for the people in the job."
      onRetry={() => refetch()}
      receipt={r ? { ...r, paid_at: r.refunded_at } : undefined}
    >
      {r && (
        <>
          <div className="grid gap-5 sm:grid-cols-2">
            <ReceiptBlock title="Refunded to">
              <p className="text-sm font-medium">{r.client.name ?? "-"}</p>
              {r.client.email && <p className="text-muted-foreground text-sm">{r.client.email}</p>}
            </ReceiptBlock>
            <ReceiptBlock title="Provider">
              <p className="text-sm font-medium">{r.provider.name ?? "-"}</p>
              {r.provider.registration_no && <p className="text-muted-foreground text-sm">Reg. no. {r.provider.registration_no}</p>}
              {r.provider.vat_number && <p className="text-muted-foreground text-sm">VAT reg. no. {r.provider.vat_number}</p>}
            </ReceiptBlock>
          </div>

          <ReceiptBlock title="For">
            <p className="text-sm font-medium">{r.job.title ?? "-"}</p>
            {r.job.service && <p className="text-muted-foreground text-sm">{r.job.service}</p>}
            <p className="mt-1 text-sm">
              <span className="text-muted-foreground">Original payment: </span>
              <Link href={`/receipts/payment/${encodeURIComponent(r.original.receipt_no)}`} className="text-primary font-mono text-xs underline">
                {r.original.receipt_no}
              </Link>{" "}
              · {money(r.original.amount, cur)} · {formatDateTime(r.original.paid_at)}
            </p>
            <p className="mt-1 text-sm">
              <span className="text-muted-foreground">Reason: </span>
              {r.reason}
            </p>
          </ReceiptBlock>

          <ReceiptBlock title="Details">
            <dl className="divide-border divide-y">
              {r.lines.map((l, i) => (
                <ReceiptRow key={`${l.label}-${i}`} label={l.label} value={money(l.amount, cur)} />
              ))}
              <ReceiptRow label="Total refunded" value={money(r.total, cur)} strong className="border-t-2 pt-2" />
            </dl>
          </ReceiptBlock>

          <ReceiptBlock title="How it was sent">
            <dl>
              <ReceiptRow label="Method" value={r.method === "manual" ? "Bank transfer from us" : "Back to how you paid"} />
              {r.to && <ReceiptRow label="Bank account" value={`${r.to.bank ?? "Bank"}${r.to.account_last4 ? ` •••• ${r.to.account_last4}` : ""}`} />}
              {r.to?.account_name && <ReceiptRow label="Account name" value={r.to.account_name} />}
              {r.to?.transfer_reference && (
                <ReceiptRow label="Transfer reference" value={<span className="font-mono text-xs break-all">{r.to.transfer_reference}</span>} />
              )}
              {r.reference && <ReceiptRow label="Payment service reference" value={<span className="font-mono text-xs break-all">{r.reference}</span>} />}
              <ReceiptRow label="Our reference" value={<span className="font-mono text-xs break-all">{r.receipt_no}</span>} />
            </dl>
          </ReceiptBlock>

          {s && (
            <ReceiptBlock title="Taken back from earnings" className="bg-secondary/40 rounded-lg border p-4 print:bg-transparent">
              <dl>
                <ReceiptRow label="Platform commission given back" value={money(s.commission, cur)} />
                <ReceiptRow label="VAT on commission given back" value={money(s.commission_vat, cur)} />
                {s.provider_vat > 0 && <ReceiptRow label="VAT you collected, refunded (adjust your VAT filing)" value={money(s.provider_vat, cur)} />}
                <ReceiptRow label="Taken from your earnings" value={`-${money(s.provider_amount, cur)}`} strong className="border-t pt-2" />
              </dl>
            </ReceiptBlock>
          )}
        </>
      )}
    </ReceiptFrame>
  );
}
