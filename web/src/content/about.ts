import { stockImages } from "./stock-images";

export const aboutProduct = {
  name: "Compliance Navigator",
  tagline: "The connected map of Ethiopian services, and the people you can trust to get them done",
  shortDescription:
    "Know what to do first, which office to visit, what to bring, and how to pay, before you queue.",
  description:
    "Compliance Navigator is an independent platform. We link the requirements of every organization into one knowledge graph, so a citizen or a company sees the whole path across all the offices involved. Next to the map is a marketplace of verified Guday Geday agents and agencies, rated only by the clients who hired them.",
};

export const aboutSections = {
  hero: { image: stockImages.cityCentre, alt: "Busy city centre in Addis Ababa" },
  mission: {
    text: "Almost everyone hits the same wall: one office needs a paper from another office, nobody shows the whole chain, and one missing document sends you home. People then turn to intermediaries they cannot check. We fix both sides: a complete, connected path, and providers whose identity, licenses and track record are visible.",
    image: stockImages.merkato,
    alt: "Shoppers and traders in Merkato, Addis Ababa",
  },
  principles: [
    {
      title: "Order matters",
      body: "You are told to go to Office B, but Office A was required first. We show the real order, worked out from how each document depends on another.",
      image: stockImages.meskelSquare,
      alt: "Meskel Square, Addis Ababa",
    },
    {
      title: "The right office",
      body: "Not a vague “go to the revenue office”. Your sub-city branch, or the nearest MESOB center when the step can be done there, with a map link.",
      image: stockImages.officeDetail,
      alt: "Commercial Bank of Ethiopia headquarters tower",
    },
    {
      title: "Fees & time, from the source",
      body: "The fee in birr and the expected processing time for each service, published by the organization or taken from official catalogs, before you stand in line.",
      image: stockImages.cityCentre,
      alt: "Busy city centre street in Addis Ababa",
    },
    {
      title: "Track your progress",
      body: "Tick what you finished. See what is next. Get help from a verified Guday Geday agent if you need it.",
      image: stockImages.consultation,
      alt: "Two people reviewing a document together",
    },
  ],
  builtForPeople: [
    {
      title: "You need a passport or ID",
      body: "Students, workers, parents: anyone who needs travel or legal ID and does not know the full chain.",
      image: stockImages.peopleDocuments,
      alt: "Two young women walking with papers",
    },
    {
      title: "You were sent back twice",
      body: "Wrong form, missing Kebele stamp, no payment receipt. You are not alone, it happens every day.",
      image: stockImages.queue,
      alt: "A busy street in the Piazza district",
    },
    {
      title: "You are starting a business",
      body: "Kebele ID, lease, TIN, registration, trade license. Five offices, one chain. We put them in order.",
      image: stockImages.trade,
      alt: "A smiling vendor at her market stall",
    },
    {
      title: "You run a company",
      body: "Renewals, sector permits, imports and inspections, each mapped across the offices involved.",
      image: stockImages.registration,
      alt: "A machinist at work in a workshop",
    },
    {
      title: "You are helping family",
      body: "Applying for a parent, spouse or child: one clear list you can follow together at home.",
      image: stockImages.peopleHelp,
      alt: "A traditional Ethiopian coffee ceremony",
    },
    {
      title: "You lost a day in traffic for nothing",
      body: "Wrong sub-city branch, office closed, document from last year. We cut that waste.",
      image: stockImages.peopleCity,
      alt: "Light rail and traffic on an Addis Ababa street",
    },
  ],
  /** What makes the platform different, and how it works with MESOB */
  difference: [
    {
      title: "A connected map, not a list",
      body: "Catalogs list one office's services. We connect them: which document each service needs, which organization issues it, and what that organization needs first.",
    },
    {
      title: "Organizations publish their own requirements",
      body: "Any office or company that gives a service can register for free and keep its documents, fees, steps and eligibility questions current. They get prepared customers; everyone gets accurate data.",
    },
    {
      title: "A marketplace of trusted intermediaries",
      body: "Guday Geday agents and agencies, as individuals or companies, with Fayda ID checks, license checks, a transparent score and reviews only from real clients.",
    },
  ],
  partnership:
    "MESOB one-stop centers bring many federal institutions under one roof. We are an independent platform and a data partner: where a step can be done at a MESOB center, our paths point there, and MESOB's public service catalog is one of our sources next to the data organizations publish directly.",
  forOrganizations: [
    { title: "Prepared customers", body: "People arrive with the right documents in the right order, so fewer applications are rejected at the window." },
    { title: "Your data, kept current by you", body: "Edit services, fees, forms and eligibility questions any time; our team reviews changes before they go live." },
    { title: "Connected to other offices", body: "Your requirements link to the organizations that issue them, so citizens see where to get each document." },
    { title: "Insight into demand", body: "See how many people view your services, check eligibility and plan a visit." },
    { title: "Free to join", body: "There is no fee for organizations to publish their services." },
    { title: "Trusted agents", body: "Clients who hire an agent for your service hire someone verified and reviewed." },
  ],
};

export const projectCredit = {
  builtIn: "Built in Addis Ababa, Ethiopia",
};
