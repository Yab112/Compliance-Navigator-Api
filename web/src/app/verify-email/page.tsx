import { Suspense } from "react";
import { VerifyEmail } from "@/modules/auth/pages/verify-email";

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
