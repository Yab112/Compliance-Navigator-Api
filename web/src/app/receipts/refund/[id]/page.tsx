import { RefundReceiptPage } from "@/modules/receipts/refund-receipt";

export const metadata = { title: "Refund receipt · Compliance Navigator" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RefundReceiptPage id={decodeURIComponent(id)} />;
}
