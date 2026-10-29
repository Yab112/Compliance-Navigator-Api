import { PaymentReceiptPage } from "@/modules/receipts/payment-receipt";

export const metadata = { title: "Receipt · Compliance Navigator" };

export default async function Page({ params }: { params: Promise<{ txRef: string }> }) {
  const { txRef } = await params;
  return <PaymentReceiptPage txRef={decodeURIComponent(txRef)} />;
}
