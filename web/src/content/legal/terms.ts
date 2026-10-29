import { COMPANY } from "./common";
import type { LegalDoc } from "./types";

export const terms: LegalDoc = {
  key: "terms",
  slug: "terms",
  title: "Terms of Service",
  titleAm: "የአገልግሎት ውል",
  version: "1.0",
  effective: "2026-10-29",
  summary:
    "The agreement between you and Compliance Navigator when you use the site, save paths, ask questions or hire a Guday Geday agent or agency.",
  sections: [
    {
      id: "who-we-are",
      title: "1. Who we are",
      body: [
        `${COMPANY.brand} is operated by ${COMPANY.legalName}, ${COMPANY.address} (TIN ${COMPANY.tin}). In these terms "we", "us" and "our" mean that company. "You" means the person using the site.`,
        "We are an independent platform. We are not a government office and we are not MESOB. MESOB and other organizations are partners that share service information with us. Government offices decide every application; we cannot promise any outcome.",
      ],
    },
    {
      id: "agreement",
      title: "2. Agreeing to these terms",
      body: [
        "You agree to these terms by ticking the box when you create an account, or by accepting an updated version when we ask you to. We keep a record of the version you accepted, the date and time, and the network address and browser you used. Under the Electronic Transactions Proclamation No. 1205/2020, an agreement made electronically is valid in the same way as one on paper.",
        "These terms include the documents listed below. If they conflict, the more specific document applies to its subject.",
        { see: ["privacy", "marketplace_rules", "refund_policy", "provider_agreement"] },
        "You must be at least 18 years old and able to enter into a contract under Ethiopian law to create an account.",
      ],
    },
    {
      id: "what-we-offer",
      title: "3. What we offer",
      body: [
        {
          list: [
            "Guidance: lists of requirements, documents, fees and steps for services across Ethiopian offices, drawn from the organizations themselves and from official catalogs.",
            "Paths and an assistant: a personal plan of what to do and in which order, and answers to questions.",
            "A marketplace: vetted Guday Geday agents and agencies you can hire to do errands and paperwork for you, paid through the platform.",
            "Organization pages: offices and companies can publish their own services and requirements.",
          ],
        },
        "Guidance is general information, not legal advice. Requirements change, so always confirm at the service window before you pay any office fee.",
      ],
    },
    {
      id: "your-account",
      title: "4. Your account",
      body: [
        {
          list: [
            "Give true information about yourself and keep it up to date.",
            "Keep your password secret. You are responsible for what happens under your account until you tell us it was misused.",
            "One person, one account. Do not create accounts for other people without their permission or to get around a suspension.",
            "Tell us straight away through the support page if you think someone else has used your account.",
          ],
        },
      ],
    },
    {
      id: "acceptable-use",
      title: "5. What you must not do",
      body: [
        {
          list: [
            "Give false documents, a false identity, or someone else's Fayda ID or details.",
            "Ask a provider to do anything unlawful, such as paying a bribe, skipping a queue unfairly or forging a document.",
            "Pay or get paid for a job outside the platform, or try to move a client or provider off the platform (see the Marketplace Rules).",
            "Harass, threaten or discriminate against anyone, or post false or misleading reviews.",
            "Copy our data in bulk, overload the site, probe it for weaknesses, or get around security measures.",
            "Use the site in a way that breaks any Ethiopian law.",
          ],
        },
      ],
    },
    {
      id: "marketplace",
      title: "6. Hiring through the marketplace",
      body: [
        "When you hire a provider, the contract for the work is between you and the provider. We are not a party to that work, but we run the platform it happens on, hold the payment, keep the record, and help when something goes wrong.",
        "The steps are: you send a request, the provider accepts and sets a price, the provider does the work and marks it delivered, you pay through the platform, and then you can leave a review. You can cancel until the work is delivered.",
        "Providers are independent. They are not our employees or agents. We check their identity and documents before they are listed, but we do not guarantee the result of any errand.",
      ],
    },
    {
      id: "payments",
      title: "7. Payments, commission and tax",
      body: [
        "You pay the agreed price through our payment partner (Chapa). The price shown at checkout includes VAT where the provider is VAT registered. We keep a platform commission from the provider's share and pass the rest to the provider. You get a receipt for every payment.",
        "Office fees paid to a government body are separate and are paid by you or on your behalf as agreed with the provider, with the official receipt.",
        "Paying or accepting payment for a job outside the platform breaks these terms. The Marketplace Rules explain what happens.",
        { see: ["marketplace_rules", "refund_policy"] },
      ],
    },
    {
      id: "content",
      title: "8. Reviews and what you post",
      body: [
        "You keep ownership of what you write, and you allow us to show it on the site and use it to run and improve the service. Reviews must be honest and about a real job. We may remove content that breaks these terms or the law. A review can only be changed through a change request that our staff check.",
      ],
    },
    {
      id: "suspension",
      title: "9. Suspending or closing accounts",
      body: [
        "We may warn you, limit what you can do, suspend or close your account if you break these terms, if we are required to by law, or to protect other users. Where it is safe to do so, we tell you why and give you a chance to respond through the support page.",
        "You can stop using the service at any time and ask us to close your account. Some records stay after closing, as the Privacy Policy explains (for example payment records and the record of what you agreed to).",
      ],
    },
    {
      id: "liability",
      title: "10. Our responsibility to you",
      body: [
        "We take reasonable care to keep information accurate and the service available, but we cannot promise it is always complete, current or uninterrupted.",
        "As far as Ethiopian law allows, we are not responsible for decisions made by government offices, for the work of independent providers beyond our duties in the Marketplace Rules and Refund and Dispute Policy, or for indirect losses. Nothing in these terms limits responsibility that cannot be limited by law, including for fraud or gross negligence, or your rights under the Trade Competition and Consumers Protection Proclamation No. 813/2013.",
      ],
    },
    {
      id: "crimes",
      title: "11. Fraud and other crimes",
      body: [
        "Breaking these terms is usually a matter of contract between you and us. Some acts are also crimes under Ethiopian law, for example fraud, using forged documents, or using someone else's identity. When we find these we keep the evidence, close the account and report the matter to the police or the relevant authority, and we cooperate with lawful requests from them.",
      ],
    },
    {
      id: "disputes",
      title: "12. Complaints, disputes and the courts",
      body: [
        "Most problems are solved through the support page. For a problem with a job, use \"Report a problem\" on the hire; our staff review both sides as set out in the Refund and Dispute Policy.",
        "If we cannot settle a dispute between you and us within 30 days, either side may take it to the competent court in Addis Ababa. These terms are governed by the laws of the Federal Democratic Republic of Ethiopia. You can also complain to the Ethiopian Trade Competition and Consumers Protection Authority.",
      ],
    },
    {
      id: "changes",
      title: "13. Changes to these terms",
      body: [
        "We may update these terms. Each version has a number and an effective date at the top of this page. When a change affects your rights, we ask you to read and accept the new version the next time you sign in, and you cannot keep using your account until you accept or close it. Small fixes, such as spelling, do not need a new acceptance.",
      ],
    },
    {
      id: "contact",
      title: "14. Contact",
      body: [`Questions about these terms: ${COMPANY.legalEmail}, or the support page while signed in.`],
    },
  ],
};
