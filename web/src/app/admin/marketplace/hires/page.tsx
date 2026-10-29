import { Suspense } from "react";
import { AdminHires } from "@/modules/admin/marketplace/admin-hires";

export default function AdminHiresPage() {
  return (
    <Suspense>
      <AdminHires />
    </Suspense>
  );
}
