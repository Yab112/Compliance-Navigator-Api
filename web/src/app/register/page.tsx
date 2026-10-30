import { Suspense } from "react";
import { Register } from "@/modules/auth/pages/register";

export const metadata = { title: "Create an account · Compliance Navigator" };

export default function RegisterPage() {
  return (
    <Suspense>
      <Register />
    </Suspense>
  );
}
