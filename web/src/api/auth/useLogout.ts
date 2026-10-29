"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiPaths } from "@/lib/constants/api-paths";
import { broadcastAuth, endSession, postAuth } from "@/lib/auth-session";

export const useLogout = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [isLoggingOut, setPending] = useState(false);

  /** `everywhere` also ends the account's sessions on other devices. */
  const logout = async (everywhere = false) => {
    setPending(true);
    try {
      await postAuth(everywhere ? apiPaths.auth.logoutAll : apiPaths.auth.logout);
    } catch {
      // Sign out locally even if the server can't be reached; the cookie expires on its own
    } finally {
      endSession();
      broadcastAuth({ type: "signed-out" });
      queryClient.clear();
      setPending(false);
      router.push("/");
    }
  };

  return { logout, isLoggingOut };
};
