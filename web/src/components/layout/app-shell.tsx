"use client";

import { usePathname } from "next/navigation";
import { Suspense } from "react";
import { PayoutPrompt } from "@/modules/marketplace/components/payout-prompt";
import { LegalGate } from "@/modules/legal/components/legal-gate";
import { VerifyEmailBanner } from "@/modules/auth/components/verify-email-banner";
import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { UpdateBar } from "@/components/layout/update-bar";
import { NavTracker } from "@cn/ui/layout/page-nav";

/** Full-screen app pages: no footer, content fills exactly what the header leaves. */
const APP_SCREENS = ["/chat"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (APP_SCREENS.includes(pathname)) {
    return (
      <div className="flex h-dvh flex-col overflow-hidden">
        <SiteHeader compact />
        <VerifyEmailBanner />
        <div className="flex min-h-0 flex-1 flex-col">{children}</div>
        <PayoutPrompt />
        <LegalGate />
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
      <VerifyEmailBanner />
      <div className="flex-1">{children}</div>
      <SiteFooter />
      <PayoutPrompt />
      <LegalGate />
      <UpdateBar />
      <Suspense fallback={null}>
        <NavTracker />
      </Suspense>
    </div>
  );
}
