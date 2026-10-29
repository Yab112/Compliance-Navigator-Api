import { COMPANY } from "./common";
import type { LegalDoc } from "./types";

export const providerAgreement: LegalDoc = {
  key: "provider_agreement",
  slug: "provider-agreement",
  title: "Guday Geday Provider Agreement",
  titleAm: "የጉዳይ ገዳይ አገልግሎት ሰጪ ስምምነት",
  version: "1.0",
  effective: "2026-10-29",
  summary:
    "The agreement between Compliance Navigator and every Guday Geday agent or agency listed in the marketplace: vetting, conduct, commission, payouts, tax, ending the agreement and disputes.",
  sections: [
    {
      id: "parties",
      title: "1. Who this agreement is between",
      body: [
        `This agreement is between ${COMPANY.legalName} (${COMPANY.brand}, "we") and you, an individual Guday Geday agent or an agency (a "provider"). It adds to the Terms of Service and the Marketplace Rules, which you also accept. If an agency accepts, the person accepting confirms they may sign for it.`,
        "You are an independent provider, not our employee, agent or partner. You decide whether to accept a request, what price to offer and how to do the work, within the rules below. You are responsible for your own taxes, licences and insurance.",
      ],
    },
    {
      id: "vetting",
      title: "2. Identity, documents and background checks",
      body: [
        "Before you are listed, and from time to time after, we check:",
        {
          list: [
            "Your identity through Fayda, the national ID.",
            "A police clearance certificate that is recent enough (we tell you the accepted age). You must renew it before it gets too old.",
            "Education certificates, a photo, and for agencies a trade licence and TIN certificate.",
            "References we may call.",
          ],
        },
        "You consent to these checks, including the use of your police clearance, which is sensitive data, for this purpose only (see the Privacy Policy). Everything you give must be genuine and yours. Giving a forged or someone else's document is a crime, and we report it to the police.",
        "You must tell us within [7 days] if anything changes that a client would reasonably want to know, for example a new criminal charge or conviction, or losing a licence.",
        "Your listing is valid for a set period and must be renewed. We may refuse, pause or end a listing if a check fails or a document expires.",
      ],
    },
    {
      id: "conduct",
      title: "3. How you work",
      body: [
        {
          list: [
            "Do the work yourself, or through members of your own agency team on the platform. No subcontracting to brokers (delala).",
            "Never offer or pay bribes or unofficial fees to officials, and refuse clients who ask for this.",
            "Pay office fees only against official receipts, and give the client the receipts.",
            "Keep clients' documents and personal data safe, use them only for the errand, return originals promptly, and do not keep copies after the job unless the law requires it.",
            "Be honest about what you can achieve and how long it takes. Do not promise outcomes that only an office can decide.",
            "Keep your Telegram username and phone number current so clients can reach you after you accept.",
            "Treat clients with respect. No harassment, threats or discrimination.",
          ],
        },
      ],
    },
    {
      id: "payments",
      title: "4. Payment only through the platform",
      body: [
        "You accept payment for jobs only through the platform, as the Marketplace Rules set out. Asking a client to pay you directly, or accepting it, breaks this agreement. We may suspend or remove you, and you owe the commission that would have applied as agreed compensation (liquidated damages), which we may deduct from your unpaid earnings or claim in court.",
        { see: ["marketplace_rules"] },
      ],
    },
    {
      id: "commission",
      title: "5. Commission, earnings and payouts",
      body: [
        {
          list: [
            "The client pays the agreed price to us through Chapa. We keep the platform commission (currently [10%] of the price, plus VAT on the commission if we are VAT registered) and add the rest to your earnings.",
            "The commission rate in force when a payment is made applies to that payment. We tell you at least [30 days] before we raise it.",
            "You can ask for a payout once your earnings reach the minimum shown in your account. We transfer to a bank account in your own name (or your agency's name). Payouts to a recently changed account may be held for extra checks.",
            "Each payout comes with a statement and receipt. Tell us within [30 days] if you think an amount is wrong.",
            "If a client is refunded after a dispute decided against you, the amount is taken from your earnings.",
          ],
        },
      ],
    },
    {
      id: "tax",
      title: "6. VAT and other tax",
      body: [
        "If you are VAT registered, tell us your VAT number. The client is then charged VAT on your price, which we pass to you and you must declare and pay under the VAT Proclamation No. 1341/2024. You are responsible for income tax and any other tax on your earnings. We give you statements to help, and we report to the tax authority what the law requires us to report.",
      ],
    },
    {
      id: "reviews",
      title: "7. Reviews, scores and your profile",
      body: [
        "Only clients who paid for a job through the platform can review you. You can reply to reviews. Your Job Success score and trust score are calculated from jobs, reviews, complaints and checks, as explained on the site. You may not post reviews about yourself, pay for reviews, or pressure clients about them.",
      ],
    },
    {
      id: "ending",
      title: "8. Suspension and ending this agreement",
      body: [
        "You can stop accepting requests or close your listing at any time, after finishing or cancelling jobs already accepted.",
        "We may suspend or end your listing if you break this agreement, the Terms or the Marketplace Rules, if a check fails or a document expires, or if we receive serious complaints. For anything other than an urgent safety or fraud risk, we tell you the reason and give you [7 days] to respond.",
        "After ending, we pay out earnings you are owed, minus amounts you owe us (for example compensation for off-platform payments or refunds), and we keep records as the Privacy Policy explains.",
      ],
    },
    {
      id: "disputes",
      title: "9. Disputes",
      body: [
        "Disputes with clients go through the Refund and Dispute Policy. If you disagree with a decision of ours, ask for a review through the support page within [14 days]. If we still cannot agree within 30 days, either side may go to the competent court in Addis Ababa. This agreement is governed by Ethiopian law.",
        { see: ["refund_policy"] },
      ],
    },
    {
      id: "changes",
      title: "10. Changes",
      body: [
        "We may update this agreement. You will be asked to accept a new version before you can keep using your provider account. If you do not accept, you can close your listing and we pay out what you are owed.",
      ],
    },
  ],
};
