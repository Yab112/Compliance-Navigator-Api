import {
  MarketplaceSection,
  OrganizationsInvite,
  Pillars,
  SamplePath,
  WhatItIs,
  WhoItsFor,
} from "../components/landing-explainer";
import { LandingHero } from "../components/landing-hero";
import { CentersList, HowItWorks, InstitutionsStrip, PopularServices } from "../components/landing-sections";

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
