import { Suspense } from "react";
import { JoinPage } from "@/modules/organizations/pages/join";

export const metadata = { title: "Register your organization · Compliance Navigator" };

export default function OrganizationJoinPage() {
  return (
    <Suspense>
      <JoinPage />
    </Suspense>
  );
}
