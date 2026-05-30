"use client";

import { useQuery } from "@tanstack/react-query";
import { endpoints } from "@/config";
import { AuthServices } from "@/services";
import { useEffect, useState } from "react";
import { useUserStore } from "@/store";
import { getAccessToken } from "@/lib/auth-token";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { setUser } = useUserStore();
  const [hasToken, setHasToken] = useState(false);

  useEffect(() => {
    setHasToken(!!getAccessToken());
  }, []);

  const { data, isError } = useQuery({
    queryKey: [endpoints.auth.me.query],
    queryFn: AuthServices.getMe,
    enabled: hasToken,
    retry: false,
  });

  useEffect(() => {
    if (data?.data?.payload?.user) {
      setUser(data.data.payload.user);
      return;
    }
    if (isError) {
      setUser(null);
    }
  }, [data, isError, setUser]);

  return <>{children}</>;
}
