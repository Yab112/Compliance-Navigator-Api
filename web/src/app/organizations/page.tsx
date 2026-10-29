import { Suspense } from "react";
import { OrganizationDirectory } from "@/modules/organizations/pages/directory";

export const metadata = { title: "Organizations · Compliance Navigator" };

export default function OrganizationsPage() {
  return (
    <Suspense>
      <OrganizationDirectory />
    </Suspense>
  );
}
