/**
 * Shared details for every legal page.
 *
 * LEGAL_DRAFT shows the "Draft, to be reviewed by an Ethiopian lawyer" banner on every legal page.
 * Set it to false once a lawyer has reviewed and approved the texts.
 *
 * Values in [square brackets] are placeholders the owner must fill in before launch.
 */
export const LEGAL_DRAFT = true;

export const LEGAL_DRAFT_NOTICE =
  "Draft, to be reviewed by an Ethiopian lawyer. These texts explain how we intend to work but have not yet had legal review.";
export const LEGAL_DRAFT_NOTICE_AM = "ረቂቅ፣ በኢትዮጵያ የሕግ ባለሙያ የሚገመገም";

export const COMPANY = {
  brand: "Compliance Navigator",
  legalName: "[Registered company name]",
  address: "[Registered address], Addis Ababa, Ethiopia",
  tin: "[TIN]",
  legalEmail: "[legal@your-domain.et]",
  privacyEmail: "[privacy@your-domain.et]",
  supportPath: "/account/support",
};

/** Plain-language summary of the off-platform payment rule, shown at sign-up and on the rules page. */
export const OFF_PLATFORM_SUMMARY =
  "Pay and get paid only through Compliance Navigator. Paying a provider directly breaks our rules: the account can be suspended or closed, the commission is owed, and we may take the matter to court.";

/** "2026-10-29" -> "29 October 2026" */
export function formatLegalDate(iso: string): string {
  return new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}
