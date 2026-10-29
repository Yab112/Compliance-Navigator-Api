import { Suspense } from "react";
import { AdminProviders } from "@/modules/marketplace/admin-providers";

export default function AdminMarketplacePage() {
  return (
    <Suspense>
      <AdminProviders />
    </Suspense>
  );
}
