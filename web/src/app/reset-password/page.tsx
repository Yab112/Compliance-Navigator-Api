import { Suspense } from "react";
import { ResetPassword } from "@/modules/auth/pages/reset-password";

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPassword />
    </Suspense>
  );
}
