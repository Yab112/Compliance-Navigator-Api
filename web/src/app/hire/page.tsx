import { Suspense } from "react";
import { MarketplaceHome } from "@/modules/marketplace/pages/marketplace-home";

export const metadata = { title: "Hire a verified provider · Compliance Navigator" };

export default function HirePage() {
  return (
    <Suspense>
      <MarketplaceHome />
    </Suspense>
  );
}
