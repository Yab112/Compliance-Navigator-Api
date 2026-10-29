import { Suspense } from "react";
import { AdminPayouts } from "@/modules/admin/marketplace/admin-payouts";

export default function AdminPayoutsPage() {
  return (
    <Suspense>
      <AdminPayouts />
    </Suspense>
  );
}
