import { Suspense } from "react";
import { AdminLogin } from "@/modules/components/admin-login";

export const metadata = { title: "Sign in · Admin · Compliance Navigator" };

export default function Page() {
  return (
    <div className="bg-secondary/40 min-h-dvh">
      <Suspense>
        <AdminLogin />
      </Suspense>
    </div>
  );
}
