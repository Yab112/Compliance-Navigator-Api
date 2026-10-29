import { stockImages } from "./stock-images";

export const landingContent = {
  explainer: {
    problem:
      "Most services in Ethiopia need documents from other offices first. A trade license needs a TIN, the TIN needs a notarized lease, the lease needs a Kebele ID. Nobody shows the whole chain, so people lose days going back and forth, or pay intermediaries they cannot check.",
    answer:
      "Compliance Navigator connects the requirements of every organization into one map. Pick what you need and we show the complete path across all the offices involved, in the right order, with fees, times and documents. If you would rather not do it yourself, hire a verified agent or agency, rated by the people who hired them before.",
    promises: [
      "The full chain across organizations, not one office at a time",
      "Requirements published by the organizations themselves",
      "Fees, processing times and the right branch",
      "Verified agents and agencies with real reviews",
      "Ask in Amharic or English",
      "Free for citizens",
    ],
  },
  pillars: [
    {
      title: "The connected map",
      am: "የተገናኘ ካርታ",
      body: "One office's service needs another office's document. Our knowledge graph links those requirements across ministries, sub-city offices, banks and agencies, so your path is complete from the first office to the last.",
      href: "/roadmap/new",
      cta: "Find my path",
    },
    {
      title: "Trusted providers",
      am: "የታመኑ አገልግሎት ሰጪዎች",
      body: "Guday Geday errand agents and agencies such as customs clearing and legal firms, individuals or companies. Every provider is ID verified, scored, and reviewed only by clients who actually hired them.",
      href: "/hire",
      cta: "Hire someone",
    },
    {
      title: "Organizations publish their own data",
      am: "ተቋማት የራሳቸውን መረጃ ያቀርባሉ",
      body: "Offices register for free and keep their services, documents, fees and eligibility questions up to date. Their customers arrive prepared, with complete applications.",
      href: "/organizations/join",
      cta: "Register an organization",
    },
  ],
  /** Real output of the roadmap engine for a trade license in Bole. */
  sample: {
    title: "One trade license. Five offices. One connected path.",
    intro:
      "This is the path the platform builds for a new trade license in Bole sub-city. Each step is a different organization, and each one needs a document from the step before it. Already have some of them? Tick them and those steps disappear.",
    note: "Fees and times come from the organizations and from the MESOB catalog, e.g. commercial registration 102 ETB, about 20 minutes.",
    steps: [
      { title: "Kebele ID", am: "የቀበሌ መታወቂያ", where: "Bole Sub-city Kebele Office", bring: "Birth certificate, proof of address, 2 photos" },
      { title: "Notarized lease agreement", am: "የተረጋገጠ የኪራይ ውል", where: "Documents Authentication and Registration Service (DARS)", bring: "Original lease, Kebele ID, owner consent" },
      { title: "TIN certificate", am: "የግብር ከፋይ መለያ ቁጥር", where: "Ministry of Revenues, Bole branch", bring: "Notarized lease, Kebele ID, IT-101 form" },
      { title: "Commercial registration", am: "የንግድ ምዝገባ", where: "Ministry of Trade and Regional Integration", bring: "TIN certificate, name reservation" },
      { title: "Trade license", am: "የንግድ ፈቃድ", where: "Bole Sub-city Trade Office", bring: "Commercial registration, TIN, premises proof" },
    ],
  },
  marketplace: [
    {
      type: "guday_geday",
      title: "Guday Geday",
      am: "ጉዳይ ገዳይ",
      body: "Errand agents who take your file through the offices: renewals, registrations, certificates.",
      image: stockImages.consultation,
      alt: "Two people reviewing a document together",
    },
    {
      type: "agency",
      title: "Agencies",
      am: "ኤጀንሲዎች",
      body: "Companies such as customs clearing, travel and visa, employment and consultancy firms, with their teams.",
      image: stockImages.officeDetail,
      alt: "An office tower in Addis Ababa",
    },
  ],
  trust: [
    { title: "Identity checked", body: "Individuals and company representatives verify with Fayda, the national ID." },
    { title: "Licenses checked", body: "Company TIN, trade license and professional permits are reviewed by our team." },
    { title: "Reviews from real clients", body: "Only someone who hired a provider and finished the job can rate them." },
    { title: "A score you can read", body: "Ratings, completed jobs, verification and complaints, combined into one transparent score." },
  ],
  organizationBenefits: [
    "Customers arrive with the right documents",
    "Fewer incomplete applications at the window",
    "One place to keep requirements, fees and forms current",
    "Linked to the paths and agents people already use",
    "Free, and you stay in control of your data",
  ],
  audiences: [
    {
      title: "Citizens",
      am: "ዜጎች",
      body: "Passport, Kebele ID, certificates, licenses. See the full chain before you leave home.",
      image: stockImages.peopleDocuments,
      alt: "Two young women walking with papers",
      href: "/roadmap/new",
      cta: "Find my path",
    },
    {
      title: "Companies",
      am: "ድርጅቶች",
      body: "Registrations, sector permits, renewals and imports, mapped across every office involved.",
      image: stockImages.registration,
      alt: "A machinist at work in an Ethiopian workshop",
      href: "/services",
      cta: "Browse services",
    },
    {
      title: "Providers",
      am: "አገልግሎት ሰጪዎች",
      body: "Guday Geday agents and agencies get a verified profile, a score and clients who already know what they need.",
      image: stockImages.consultation,
      alt: "Two people reviewing a document together",
      href: "/providers/join",
      cta: "Become a provider",
    },
    {
      title: "Organizations",
      am: "ተቋማት",
      body: "Publish your requirements once. Every path and every agent on the platform uses them.",
      image: stockImages.meskelSquare,
      alt: "Meskel Square and the Addis Ababa skyline",
      href: "/organizations/join",
      cta: "Register your organization",
    },
  ],
  steps: [
    { n: "1", title: "Choose what you need", desc: "A license, an ID, a certificate, or any service" },
    { n: "2", title: "See the connected path", desc: "Every office involved, in order, with fees and documents" },
    { n: "3", title: "Do it yourself or hire", desc: "Follow the steps, or give the job to a verified provider" },
  ],
} as const;
