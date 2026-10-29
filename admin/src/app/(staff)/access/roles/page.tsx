import { Suspense } from "react";
import { RolesPage } from "@/modules/access/roles-page";

export default function Page() {
  return (
    <Suspense>
      <RolesPage />
    </Suspense>
  );
}
