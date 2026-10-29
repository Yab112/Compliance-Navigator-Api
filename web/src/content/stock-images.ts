/**
 * Local photos of Addis Ababa and Ethiopian life (public/images/ethiopia).
 * Sources and licenses: content/photo-credits.ts, keep that list in sync when swapping images.
 */

const p = (name: string) => `/images/ethiopia/${name}.jpg`;

export const stockImages = {
  hero: p("addis-skyline"),
  city: p("addis-city"),
  cityCentre: p("city-centre"),
  meskelSquare: p("meskel-square"),
  officeDetail: p("cbe-tower"),
  documents: p("students-papers"),
  queue: p("piazza-street"),
  map: p("meskel-square"),
  passport: p("students-papers"),
  kebele: p("piazza-street"),
  tin: p("city-centre"),
  trade: p("market-vendor"),
  registration: p("machinist"),
  fintech: p("cbe-tower"),
  notary: p("consultation"),
  merkato: p("merkato"),
  welder: p("welder"),
  coffeeTasters: p("coffee-tasters"),
  /** People, everyday life in Addis */
  peopleWaiting: p("piazza-street"),
  peopleDocuments: p("students-papers"),
  peopleCity: p("light-rail"),
  peopleHelp: p("coffee-ceremony"),
  consultation: p("consultation"),
} as const;

/** Office reference photos in roadmap steps */
export const officeStockByStep: Record<string, string> = {
  birth_certificate: stockImages.kebele,
  kebele_id: stockImages.kebele,
  passport: stockImages.passport,
  notarized_lease: stockImages.notary,
  tin: stockImages.tin,
  commercial_registration: stockImages.registration,
  trade_license: stockImages.trade,
  nbe_fintech_permit: stockImages.fintech,
};
