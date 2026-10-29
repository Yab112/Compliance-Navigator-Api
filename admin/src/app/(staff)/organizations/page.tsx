import { Suspense } from "react";
import { AdminOrganizations } from "@/modules/organizations/admin-organizations";

export default function AdminOrganizationsPage() {
  return (
    <Suspense>
      <AdminOrganizations />
    </Suspense>
  );
}
