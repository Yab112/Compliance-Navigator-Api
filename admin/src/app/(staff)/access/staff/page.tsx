import { Suspense } from "react";
import { StaffPage } from "@/modules/access/staff-page";

export default function Page() {
  return (
    <Suspense>
      <StaffPage />
    </Suspense>
  );
}
