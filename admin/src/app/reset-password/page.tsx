import { Suspense } from "react";
import { SetPasswordPage } from "@/modules/access/link-pages";

export const metadata = { title: "Reset password · Admin · Compliance Navigator" };

export default function Page() {
  return (
    <div className="bg-secondary/40 min-h-dvh">
      <Suspense>
        <SetPasswordPage kind="reset" />
      </Suspense>
    </div>
  );
}
