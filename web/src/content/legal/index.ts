import { marketplaceRules } from "./marketplace-rules";
import { privacy } from "./privacy";
import { providerAgreement } from "./provider-agreement";
import { refundPolicy } from "./refunds";
import { terms } from "./terms";
import type { LegalDoc, LegalKey } from "./types";

export * from "./common";
export type { LegalBlock, LegalDoc, LegalKey, LegalSection } from "./types";

/** In the order shown on /legal and in the footer. */
export const LEGAL_DOCS: LegalDoc[] = [terms, privacy, marketplaceRules, refundPolicy, providerAgreement];

export const LEGAL_BY_KEY = Object.fromEntries(LEGAL_DOCS.map((d) => [d.key, d])) as Record<LegalKey, LegalDoc>;

export const legalHref = (key: LegalKey) => `/legal/${LEGAL_BY_KEY[key].slug}`;

/** Ticked at sign-up. Matches CLIENT_REQUIRED in api/services/legal.py. */
export const SIGNUP_DOCS: LegalKey[] = ["terms", "privacy", "marketplace_rules"];

/** What the sign-up form sends: document key -> version shown on this page. */
export const signupAcceptance = (): Record<string, string> =>
  Object.fromEntries(SIGNUP_DOCS.map((k) => [k, LEGAL_BY_KEY[k].version]));
