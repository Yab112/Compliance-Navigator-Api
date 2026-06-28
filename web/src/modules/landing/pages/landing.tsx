import { LandingHero } from "../components/landing-hero";
import { LandingSteps } from "../components/landing-steps";
import { LandingValue } from "../components/landing-value";

export function LandingPage() {
  return (
    <div>
      <LandingHero />
      <LandingSteps />
      <LandingValue />
    </div>
  );
}
