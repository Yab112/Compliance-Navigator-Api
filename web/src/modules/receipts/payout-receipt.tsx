"use client";

import { usePayoutReceipt } from "@cn/core/api/payments";
import { formatDateTime } from "@cn/ui/guday/shared";
import { useAuthGate } from "@/modules/guday/components/use-auth-gate";
import { ReceiptBlock, ReceiptFrame, ReceiptRow, money } from "@/modules/receipts/receipt-layout";

/** Receipt for a withdrawal that was sent to the provider's bank. */
export function PayoutReceiptPage({ id }: { id: string }) {
  const gate = useAuthGate();
  const { data, isLoading, isError, refetch } = usePayoutReceipt(id, gate === "ready");
  const r = data?.payload.receipt;
  const cur = r?.currency || "ETB";

  return (
    <ReceiptFrame
      title="Withdrawal receipt · የክፍያ ደረሰኝ"
      heading="Withdrawal receipt"
      gate={gate}
      isLoading={isLoading}
      isError={isError}
      errorMessage="We could not find a receipt for this withdrawal. Receipts are ready once the money is sent."
      onRetry={() => refetch()}
      receipt={r}
    >
      {r && (
        <>
          <ReceiptBlock title="Paid to">
            <p className="text-sm font-medium">{r.provider.name ?? "-"}</p>
            {r.provider.registration_no && <p className="text-muted-foreground text-sm">Reg. no. {r.provider.registration_no}</p>}
          </ReceiptBlock>

          <ReceiptBlock title="Details">
            <dl>
              <ReceiptRow
                label="Bank account"
                value={`${r.to.bank ?? "Bank"}${r.to.account_last4 ? ` •••• ${r.to.account_last4}` : ""}`}
              />
              {r.to.account_name && <ReceiptRow label="Account name" value={r.to.account_name} />}
              <ReceiptRow label="Sent on" value={formatDateTime(r.paid_at)} />
              {r.transfer_reference && (
                <ReceiptRow label="Transfer reference" value={<span className="font-mono text-xs break-all">{r.transfer_reference}</span>} />
              )}
              <ReceiptRow label="Our reference" value={<span className="font-mono text-xs break-all">{id}</span>} />
              <ReceiptRow label="Amount sent" value={money(r.amount, cur)} strong className="border-t-2 pt-2" />
            </dl>
          </ReceiptBlock>
        </>
      )}
    </ReceiptFrame>
  );
}
