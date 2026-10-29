"use client";

import "@/lib/routes";
import { QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@cn/core/providers/auth-provider";
import { queryClient } from "@cn/core/lib/queryClient";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
