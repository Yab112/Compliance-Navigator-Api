import { Suspense } from "react";
import { AccountPage } from "@/modules/account/pages/account";

export const metadata = { title: "My account · Compliance Navigator" };

export default function Page() {
  return (
    <Suspense>
      <AccountPage />
    </Suspense>
  );
}
