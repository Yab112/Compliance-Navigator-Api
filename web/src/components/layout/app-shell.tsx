"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { PayoutPrompt } from "@/modules/marketplace/components/payout-prompt";
import { SiteFooter } from "./site-footer";
import { SiteHeader } from "./site-header";
import { UpdateBar } from "./update-bar";
import { NavTracker } from "./page-nav";

/** Full-screen app pages: no footer, content fills exactly what the header leaves. */
const APP_SCREENS = ["/chat"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (APP_SCREENS.includes(pathname)) {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <SiteHeader compact />
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        <PayoutPrompt />
        <UpdateBar />
        <Suspense fallback={null}>
          <NavTracker />
        </Suspense>
      </div>
    );
  }
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <div className="flex-1">{children}</div>
      <SiteFooter />
      <PayoutPrompt />
      <UpdateBar />
      <Suspense fallback={null}>
        <NavTracker />
      </Suspense>
    </div>
  );
}
