import { Suspense } from "react";
import { MyProviderPage } from "@/modules/marketplace/pages/my-provider";

export const metadata = { title: "My provider profile · Compliance Navigator" };

export default function Page() {
  return (
    <Suspense>
      <MyProviderPage />
    </Suspense>
  );
}
