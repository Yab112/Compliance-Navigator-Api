import { Suspense } from "react";
import { AdminPayouts } from "@/modules/marketplace/admin-payouts";

export default function AdminPayoutsPage() {
  return (
    <Suspense>
      <AdminPayouts />
    </Suspense>
  );
}
