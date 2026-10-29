import { Suspense } from "react";
import { Register } from "@/modules/auth/pages/register";

export default function RegisterPage() {
  return (
    <Suspense>
      <Register />
    </Suspense>
  );
}
