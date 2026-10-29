import { Suspense } from "react";
import { AdminPayments } from "@/modules/admin/marketplace/admin-payments";

export default function AdminPaymentsPage() {
  return (
    <Suspense>
      <AdminPayments />
    </Suspense>
  );
}
