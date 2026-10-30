import { Suspense } from "react";
import { Login } from "@/modules/auth/pages/login";

export const metadata = { title: "Sign in · Compliance Navigator" };

export default function LoginPage() {
  return (
    <Suspense>
      <Login />
    </Suspense>
  );
}
