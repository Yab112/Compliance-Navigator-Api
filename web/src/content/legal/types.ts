/** Keys match the registry in api/services/legal.py. */
export type LegalKey = "terms" | "privacy" | "marketplace_rules" | "provider_agreement" | "refund_policy";

/** A paragraph, a bullet list, a highlighted note, or links to other legal pages. */
export type LegalBlock = string | { list: string[] } | { note: string } | { see: LegalKey[] };

export interface LegalSection {
  /** Anchor in the page URL, e.g. /legal/terms#payments */
  id: string;
  title: string;
  body: LegalBlock[];
}

export interface LegalDoc {
  key: LegalKey;
  /** Path under /legal */
  slug: string;
  title: string;
  titleAm: string;
  /** Bump together with api/services/legal.py when people must agree again */
  version: string;
  /** ISO date this version took effect */
  effective: string;
  /** One or two plain sentences shown at the top and on the /legal index */
  summary: string;
  sections: LegalSection[];
}
