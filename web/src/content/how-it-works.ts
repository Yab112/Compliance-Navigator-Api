import { stockImages } from "./stock-images";

export const howItWorks = {
  title: "How it works",
  subtitle: "Three steps. No categories. No jargon.",
  steps: [
    {
      number: "1",
      title: "What do you need?",
      body: "Tap Passport, Kebele ID, or Trade license—or search for something else. That’s it.",
      image: stockImages.passport,
    },
    {
      number: "2",
      title: "Where are you?",
      body: "Pick your Addis Ababa sub-city so we show the right office branch.",
      image: stockImages.map,
    },
    {
      number: "3",
      title: "What do you already have?",
      body: "Optional: tick documents you already hold. We skip those steps.",
      image: stockImages.documents,
    },
  ],
  result: {
    title: "You get a path",
    bullets: [
      "Steps in the right order",
      "Office name, address, phone, hours",
      "Fee and how to pay",
      "What to bring",
      "Mark each step done as you go",
    ],
  },
};
