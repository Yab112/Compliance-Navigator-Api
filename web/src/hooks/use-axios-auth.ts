"use client";

import { useEffect } from "react";
import { api } from "@/lib/api";
import { clearAccessToken } from "@/lib/auth-token";

const useAxiosAuth = () => {
  useEffect(() => {
    const responseIntercept = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        if (error.response?.status === 401 && typeof window !== "undefined") {
          clearAccessToken();
          const path = window.location.pathname;
          if (!path.startsWith("/login") && !path.startsWith("/register")) {
            window.location.href = "/login";
          }
        }
        return Promise.reject(error);
      },
    );

    return () => {
      api.interceptors.response.eject(responseIntercept);
    };
  }, []);

  return api;
};

export default useAxiosAuth;
