import {
  MarketplaceSection,
  OrganizationsInvite,
  Pillars,
  SamplePath,
  WhatItIs,
  WhoItsFor,
} from "@/modules/landing/components/landing-explainer";
import { LandingHero } from "@/modules/landing/components/landing-hero";
import { CentersList, HowItWorks, InstitutionsStrip, PopularServices } from "@/modules/landing/components/landing-sections";

export function LandingPage() {
  return (
    <div>
      <LandingHero />
      <WhatItIs />
      <Pillars />
      <HowItWorks />
      <SamplePath />
      <MarketplaceSection />
      <PopularServices />
      <OrganizationsInvite />
      <WhoItsFor />
      <InstitutionsStrip />
      <CentersList />
    </div>
  );
}
