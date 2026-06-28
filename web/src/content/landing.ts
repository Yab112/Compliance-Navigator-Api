import { stockImages } from "./stock-images";

export const landingContent = {
  hero: {
    badge: "Addis Ababa",
    headline: "Know exactly what to do at each government office",
    subhead:
      "Passport, Kebele ID, trade license—your steps in order, with the right branch, fees, and documents. Free, no account needed.",
  },
  steps: [
    { n: "1", title: "Choose your goal", desc: "Passport, ID, or license" },
    { n: "2", title: "Pick your sub-city", desc: "Correct branch every time" },
    { n: "3", title: "Get your path", desc: "Offices, fees, checklist" },
  ],
  value: {
    title: "Made for real queues, real rejections",
    points: [
      "Steps in the order offices actually require",
      "Branch address, phone, hours, and fees in birr",
      "What to bring—and why people get sent back",
    ],
  },
} as const;

export const landingQuickGoals = [
  {
    id: "passport",
    label: "Passport",
    hint: "New or renewal",
    image: stockImages.passport,
  },
  {
    id: "kebele_id",
    label: "Kebele ID",
    hint: "Resident ID",
    image: stockImages.kebele,
  },
  {
    id: "trade_license",
    label: "Trade license",
    hint: "Open a business",
    image: stockImages.trade,
  },
] as const;
