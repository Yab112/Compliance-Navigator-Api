import { Suspense } from "react";
import { JoinMarketplace } from "@/modules/marketplace/pages/join";

export const metadata = { title: "Join the marketplace · Compliance Navigator" };

export default function JoinPage() {
  return (
    <Suspense>
      <JoinMarketplace />
    </Suspense>
  );
}
