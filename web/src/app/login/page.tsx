import { Suspense } from "react";
import { Login } from "@/modules/auth/pages/login";

export default function LoginPage() {
  return (
    <Suspense>
      <Login />
    </Suspense>
  );
}
