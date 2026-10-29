import { Suspense } from "react";
import { AdminSubmissions } from "@/modules/admin/organizations/admin-submissions";

export default function AdminSubmissionsPage() {
  return (
    <Suspense>
      <AdminSubmissions />
    </Suspense>
  );
}
