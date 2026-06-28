import { stockImages } from "./stock-images";

export const aboutProduct = {
  name: "Compliance Navigator",
  tagline: "Every government process—mapped step by step",
  shortDescription:
    "Know what to do first, which office to visit, what to bring, and how to pay—before you queue.",
  description:
    "Compliance Navigator is for everyone who deals with government paperwork—passport, Kebele ID, business license, tax, renewals, and more. We show the full path: what comes first, where to go, what it costs, and what to bring.",
};

export const aboutSections = {
  mission: {
    text: "Almost everyone hits the same wall: too many offices, unclear rules, wrong documents, wasted trips. One missing paper sends you home. We turn that maze into a clear path—so ordinary people can finish what they started.",
    image: stockImages.peopleWaiting,
  },
  principles: [
    {
      title: "Order matters",
      body: "You are told to go to Office B, but Office A was required first. We show the real order.",
      image: stockImages.map,
    },
    {
      title: "The right office",
      body: "Not a vague “go to ERCA”—your branch, address, phone, hours, and a photo of the building.",
      image: stockImages.kebele,
    },
    {
      title: "Fees & how to pay",
      body: "How much in birr, cash or CBE Birr or bank slip—before you stand in line.",
      image: stockImages.documents,
    },
    {
      title: "Track your progress",
      body: "Tick what you finished. See what is next. No starting over in your head.",
      image: stockImages.peopleDocuments,
    },
  ],
  /** The problem everyone shares — not niche “audiences” */
  builtForPeople: [
    {
      title: "You need a passport or ID",
      body: "Students, workers, parents—anyone who needs travel or legal ID and does not know the full chain.",
      image: stockImages.passport,
    },
    {
      title: "You were sent back twice",
      body: "Wrong form, missing Kebele stamp, no payment receipt. You are not alone—this happens every day.",
      image: stockImages.queue,
    },
    {
      title: "You are opening a business",
      body: "Shop, taxi, tech, shop owner—registration and license steps pile up fast.",
      image: stockImages.trade,
    },
    {
      title: "It is your first time at a bureau",
      body: "No one explained the process. You should not need an agent for basic clarity.",
      image: stockImages.peopleCity,
    },
    {
      title: "You are helping family",
      body: "Applying for a parent, spouse, or child—you need one clear list to follow together.",
      image: stockImages.peopleHelp,
    },
    {
      title: "You lost a day in traffic for nothing",
      body: "Wrong sub-city branch, office closed, document from last year. We cut that waste.",
      image: stockImages.peopleWaiting,
    },
  ],
};

export const projectCredit = {
  builtIn: "Addis Ababa, Ethiopia",
};
