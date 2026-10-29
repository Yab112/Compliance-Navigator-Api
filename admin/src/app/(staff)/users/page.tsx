import { Suspense } from "react";
import { UsersPage } from "@/modules/users/users-page";

export default function AdminUsersRoute() {
  return (
    <Suspense>
      <UsersPage />
    </Suspense>
  );
}
