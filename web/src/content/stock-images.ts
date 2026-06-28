/**

 * Public stock photos (Unsplash) — swap URLs anytime.

 * https://unsplash.com/license

 *

 * IDs must be real Unsplash slugs (photo-{timestamp}-{hash}).

 * Broken IDs return 404 from images.unsplash.com and show empty in Next/Image.

 */



const u = (id: string, w = 800) =>

  `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=80`;



export const stockImages = {

  hero: u("photo-1504384308090-c894fdcc538d", 1200),

  officeDetail: u("photo-1497366216548-37526070297c", 900),

  documents: u("photo-1450101499163-c8848c66ca85", 800),

  queue: u("photo-1522071820081-009f0129c71c", 800),

  map: u("photo-1524661135-423995f22d0b", 800),



  passport: u("photo-1526304640581-d334cdbbf45e", 600),

  kebele: u("photo-1497366216548-37526070297c", 600),

  tin: u("photo-1554224155-6726b3ff858f", 600),

  trade: u("photo-1507679799987-c73779587ccf", 600),

  registration: u("photo-1454165804606-c3d57bc86b40", 600),

  fintech: u("photo-1563986768609-322da13575f3", 600),

  notary: u("photo-1586281380349-632531db7ed4", 600),



  /** People — queues, stress, everyday life */

  peopleWaiting: u("photo-1600880292203-757bb62b4baf", 700),

  peopleDocuments: u("photo-1516321318423-f06f85e504b3", 700),

  peopleCity: u("photo-1501785888041-af3ef285b470", 700),

  peopleHelp: u("photo-1521737711867-e3b97375f902", 700),

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


