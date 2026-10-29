import { Suspense } from "react";
import { AdminPayments } from "@/modules/marketplace/admin-payments";

export default function AdminPaymentsPage() {
  return (
    <Suspense>
      <AdminPayments />
    </Suspense>
  );
}
