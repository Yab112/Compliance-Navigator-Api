import { PayoutReceiptPage } from "@/modules/receipts/payout-receipt";

export const metadata = { title: "Withdrawal receipt · Compliance Navigator" };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PayoutReceiptPage id={decodeURIComponent(id)} />;
}
