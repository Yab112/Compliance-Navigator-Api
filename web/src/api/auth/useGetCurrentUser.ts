"use client";

import { useUserStore } from "@/store/user-store";

/** The signed-in user from the session store (filled by AuthProvider). */
export const useGetCurrentUser = () => {
  const user = useUserStore((s) => s.user);
  const status = useUserStore((s) => s.status);
  return { currentUser: user, isLoading: status === "loading", status };
};
