import { COMPANY, OFF_PLATFORM_SUMMARY } from "./common";
import type { LegalDoc } from "./types";

export const marketplaceRules: LegalDoc = {
  key: "marketplace_rules",
  slug: "marketplace-rules",
  title: "Marketplace Rules and Off-platform Payment Policy",
  titleAm: "የገበያ ደንቦች እና ከመድረኩ ውጭ ክፍያ ፖሊሲ",
  version: "1.0",
  effective: "2026-10-29",
  summary: OFF_PLATFORM_SUMMARY,
  sections: [
    {
      id: "why",
      title: "1. Why these rules exist",
      body: [
        "Clients trust a provider because of their checked identity, documents, reviews and Job Success score. Those only mean something if the work and the payment happen here. Paying through the platform also protects both sides: the client pays after delivery and can report a problem, and the provider has a record that the money is owed and a receipt for tax.",
      ],
    },
    {
      id: "how-hiring-works",
      title: "2. How a hire works",
      body: [
        {
          list: [
            "The client sends a request. The provider accepts it and sets the price.",
            "After acceptance, both sides see each other's phone number and Telegram username to arrange the work.",
            "The provider does the work and marks it delivered with a short note. From then the price is fixed.",
            "The client pays the agreed price through the platform. That closes the job.",
            "The client can then leave a review. The provider can rate the client.",
            "The client can cancel at any time before delivery. After delivery the client can only pay or report a problem.",
          ],
        },
      ],
    },
    {
      id: "off-platform",
      title: "3. The off-platform payment rule",
      body: [
        "For any job that started with a request on Compliance Navigator, and for any further work between the same client and provider within [12 months] of their first contact here:",
        {
          list: [
            "Clients must pay only through the platform, and providers must accept payment only through the platform.",
            "Neither side may ask for, offer or accept cash, a bank transfer, telebirr or any other payment directly, including a \"discount for paying outside\".",
            "Neither side may use the contact details shown after acceptance to arrange work while avoiding the platform.",
            "Government office fees, paid to the office against an official receipt, are not covered by this rule.",
          ],
        },
        {
          note: "Paying outside the platform is not in itself a crime. It is a breach of the agreement you accepted when you signed up, and it has the consequences below.",
        },
      ],
    },
    {
      id: "consequences",
      title: "4. What happens if the rule is broken",
      body: [
        {
          list: [
            "Warning or suspension: we may hide the provider's profile, pause new requests, or suspend either account while we look into it.",
            "Removal: repeated or deliberate breaches lead to the account being closed. A provider removed for this cannot rejoin.",
            "Commission owed as agreed compensation (liquidated damages): the person who broke the rule owes us an amount equal to the commission that would have applied had the payment gone through the platform, that is, the commission percentage in force (currently [10%]) of the price paid outside, and at least [ETB 500] for each job [amounts are placeholders for the owner to confirm with a lawyer]. Both sides agree this is a fair estimate of our loss, which is otherwise hard to measure.",
            "Recovery: for providers we may deduct the amount from earnings not yet paid out. Otherwise we send a written demand, and if it is not paid we may claim it, with costs, before the competent court in Addis Ababa.",
            "Reviews and scores: a job paid outside does not count toward reviews or Job Success, and reviews linked to it may be removed.",
          ],
        },
        "We decide based on evidence, such as messages, screenshots and reports from the other side, and we give the person a chance to explain before closing an account.",
      ],
    },
    {
      id: "report",
      title: "5. If someone asks you to pay or be paid outside",
      body: [
        `Say no and tell us through the support page or ${COMPANY.legalEmail}. A person who reports a request in good faith and did not go along with it is not penalized.`,
      ],
    },
    {
      id: "crimes",
      title: "6. Fraud, fake documents and identity misuse",
      body: [
        "These are not just rule breaks. Deceiving someone to get money (fraud), making or using forged documents or certificates, and using another person's ID or Fayda details are crimes under the Criminal Code of Ethiopia (Proclamation No. 414/2004) and the Computer Crime Proclamation No. 958/2016. We close the accounts involved, keep the evidence, report the matter to the Ethiopian Federal Police or the relevant authority, and cooperate with any investigation.",
      ],
    },
    {
      id: "conduct",
      title: "7. Conduct for everyone",
      body: [
        {
          list: [
            "No bribes, \"speed money\" or unofficial fees to officials, ever. A provider will refuse such a request and so should you.",
            "No brokers (delala). Providers do the work themselves or through their own registered agency team.",
            "Be respectful. No harassment, threats or discrimination.",
            "Honest reviews only, about real jobs paid through the platform.",
            "Clients give accurate information and the documents needed for the errand. Providers keep clients' documents safe and return them.",
          ],
        },
      ],
    },
    {
      id: "related",
      title: "8. Related documents",
      body: [{ see: ["terms", "refund_policy", "provider_agreement", "privacy"] }],
    },
  ],
};
