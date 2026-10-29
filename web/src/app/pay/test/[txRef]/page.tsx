import { TestCheckoutPage } from "@/modules/payments/test-checkout";

export const metadata = { title: "Test checkout · Compliance Navigator" };

export default async function Page({ params }: { params: Promise<{ txRef: string }> }) {
  const { txRef } = await params;
  return <TestCheckoutPage txRef={decodeURIComponent(txRef)} />;
}
