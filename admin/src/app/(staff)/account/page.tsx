import { Suspense } from "react";
import { AccountPage } from "@/modules/access/account-page";

export default function Page() {
  return (
    <Suspense>
      <AccountPage />
    </Suspense>
  );
}
