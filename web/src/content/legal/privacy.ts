import { COMPANY } from "./common";
import type { LegalDoc } from "./types";

export const privacy: LegalDoc = {
  key: "privacy",
  slug: "privacy",
  title: "Privacy Policy",
  titleAm: "የግላዊነት ፖሊሲ",
  version: "1.0",
  effective: "2026-10-29",
  summary:
    "What personal data we collect, why, who sees it, how long we keep it, and how to use your rights under the Personal Data Protection Proclamation No. 1321/2024.",
  sections: [
    {
      id: "controller",
      title: "1. Who is responsible for your data",
      body: [
        `${COMPANY.legalName} (${COMPANY.brand}), ${COMPANY.address}, decides how your personal data is used and is responsible for it under the Personal Data Protection Proclamation No. 1321/2024. Contact for privacy questions: ${COMPANY.privacyEmail}.`,
      ],
    },
    {
      id: "what-we-collect",
      title: "2. What we collect",
      body: [
        "From everyone with an account:",
        {
          list: [
            "Account details: name, email, phone number (optional), Telegram username (optional), preferred sub-city, password (stored only as a one-way hash).",
            "What you do on the site: saved paths, questions you ask the assistant, support requests, hires, reviews you give and receive.",
            "Security records: sign-ins, devices and browsers, network (IP) address, and password changes, so we can protect your account.",
            "Agreement records: which version of our terms you accepted and when, with the network address and browser used.",
          ],
        },
        "When you hire or pay:",
        {
          list: [
            "Payment details: amount, reference, status and receipt. Card and mobile money details are handled by our payment partner Chapa; we do not see or store your card number or PIN.",
            "Your client record: how many accepted requests you paid for, cancellations after acceptance, and ratings providers gave you.",
          ],
        },
        "From Guday Geday agents and agencies (providers), in addition:",
        {
          list: [
            "Fayda national ID check: we receive the verified name, date of birth and gender from the National ID Program. We do not store your full Fayda number; we keep only the last four digits and a protected code that stops one ID being used for two accounts.",
            "Documents you upload: police clearance certificate, education certificates, photo, trade licence, TIN certificate and ID copy, with their dates and reference numbers, and the names and phone numbers of references we call.",
            "Payout details: your bank and account number (stored encrypted; only the last four digits are shown), your earnings and payouts, and VAT registration if you have one.",
            "Your public profile, reviews, Job Success score and trust score.",
          ],
        },
        {
          note: "A police clearance certificate shows whether a person has a criminal record, and Fayda data includes identity details. The Proclamation treats data about offences as sensitive. We ask for it only from providers, only to decide whether it is safe to send them into people's homes and offices, and we ask for your explicit consent when you upload it.",
        },
      ],
    },
    {
      id: "why",
      title: "3. Why we use it, and on what basis",
      body: [
        {
          list: [
            "To run your account and the services you ask for (performing our contract with you).",
            "To check providers' identity and background before listing them, and to keep clients safe (your explicit consent for sensitive data, and our legitimate interest in a safe marketplace).",
            "To take payments, pay providers, issue receipts and keep tax records (contract and legal obligations, including tax law).",
            "To prevent fraud, misuse and payments outside the platform, and to protect accounts (legitimate interest).",
            "To answer support requests and handle disputes (contract and legitimate interest).",
            "To improve guidance and the assistant, using questions with personal details removed where possible (legitimate interest).",
            "To meet legal duties and lawful requests from authorities (legal obligation).",
          ],
        },
        "We do not sell your personal data and we do not use it for advertising by others.",
      ],
    },
    {
      id: "who-sees-it",
      title: "4. Who sees your data",
      body: [
        {
          list: [
            "Providers you send a request to see your name, your request and your client record. After they accept, you both see each other's phone number and Telegram username so you can talk.",
            "Clients see a provider's public profile, reviews and scores, never their documents, ID details or bank account.",
            "Our staff see what they need for their job (for example vetting, payouts, support or disputes). Their access is limited by role and logged.",
            "Service providers who work for us under contract: Chapa (payments and transfers to providers), our hosting and email providers, and our error-monitoring service. They may use the data only to provide their service to us.",
            "Authorities, such as the police, courts, the Ministry of Revenues or the Ethiopian Communications Authority, when the law requires it or to report a crime.",
          ],
        },
      ],
    },
    {
      id: "abroad",
      title: "5. Data stored or sent outside Ethiopia",
      body: [
        "We keep our main database in [location to be confirmed]. Some of our service providers (for example the error-monitoring service that tells us when a page breaks) may process limited technical data outside Ethiopia. We transfer personal data abroad only as the Proclamation allows, with safeguards, and we do not send sensitive data such as police clearance or ID data abroad without the approval the law requires.",
      ],
    },
    {
      id: "retention",
      title: "6. How long we keep it",
      body: [
        {
          list: [
            "Account and profile: while your account is open, then deleted or anonymized within [12 months] of closing, except the items below.",
            "Payment, payout and tax records: [10 years], as tax and commercial law requires.",
            "Records of what you agreed to: for as long as the agreement can be relied on or challenged, at least [10 years]. Deactivating an account never deletes them.",
            "Provider documents (police clearance and others): while you are listed and for [2 years] after, to answer complaints, then deleted. Older versions you replace are kept for the same period so we can show what was on file and when.",
            "Security logs: [2 years].",
            "Disputes, fraud reports and evidence for legal claims: until the matter is closed and the time to bring a claim has passed.",
          ],
        },
      ],
    },
    {
      id: "rights",
      title: "7. Your rights",
      body: [
        "Under the Proclamation you can:",
        {
          list: [
            "Be told what data we hold about you and get a copy.",
            "Have wrong or incomplete data corrected.",
            "Ask us to delete data we no longer need or have no lawful reason to keep.",
            "Ask us to limit how we use your data, or object to a use based on our legitimate interest.",
            "Withdraw consent at any time (for example to background checks). This does not affect what was done before, but a provider who withdraws consent to vetting can no longer be listed.",
            "Not be subject to a decision based only on automated processing that significantly affects you. Scores help clients compare providers; listing decisions are made by people.",
            "Complain to the Ethiopian Communications Authority, the regulator under the Proclamation.",
          ],
        },
        `To use a right, write to ${COMPANY.privacyEmail} or open a support request while signed in. We may ask you to confirm who you are. We answer within [30 days].`,
        "You can see and change most profile details yourself on your account page, and see which versions of our terms you accepted.",
      ],
    },
    {
      id: "security",
      title: "8. Security and breaches",
      body: [
        "We protect data with encryption in transit, encrypted bank account numbers, hashed passwords, short-lived sign-in tokens, role-based staff access and audit logs. No system is perfectly secure. If a breach puts your rights at risk, we notify the Ethiopian Communications Authority and, where required, you, within the time the Proclamation sets (72 hours from when we become aware), and tell you what you can do.",
      ],
    },
    {
      id: "cookies",
      title: "9. Cookies and browser storage",
      body: [
        "We set one cookie: a secure, sign-in cookie (cn_refresh) that keeps you signed in. It is strictly necessary, so no consent banner is needed. We also keep small items in your browser's storage, for example which assistant conversation you had open, which are not used to track you. We do not use advertising or third-party tracking cookies. If that changes we will ask for your consent first.",
      ],
    },
    {
      id: "children",
      title: "10. Children",
      body: ["Accounts are for people aged 18 and over. We do not knowingly collect data from children."],
    },
    {
      id: "changes",
      title: "11. Changes",
      body: [
        "Each version of this policy has a number and an effective date. When a change matters, we ask you to accept the new version the next time you sign in.",
      ],
    },
  ],
};
