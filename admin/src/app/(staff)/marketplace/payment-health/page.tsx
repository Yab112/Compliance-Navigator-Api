import { Suspense } from "react";
import { AdminPaymentHealth } from "@/modules/marketplace/admin-payment-health";

export default function AdminPaymentHealthPage() {
  return (
    <Suspense>
      <AdminPaymentHealth />
    </Suspense>
  );
}
