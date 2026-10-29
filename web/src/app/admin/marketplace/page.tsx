import { Suspense } from "react";
import { AdminProviders } from "@/modules/admin/marketplace/admin-providers";

export default function AdminMarketplacePage() {
  return (
    <Suspense>
      <AdminProviders />
    </Suspense>
  );
}
