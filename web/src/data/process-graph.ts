/**
 * Process definitions aligned with the Government Data Dictionary.
 * Each step is a graph node with office, fees, payment methods, and prerequisites.
 */

import type { OfficeInfo, RoadmapStep } from "@/types/roadmap";
import { stockImages } from "@/content/stock-images";

export type ProcessStepTemplate = Omit<RoadmapStep, "status">;

function office(
  base: Omit<OfficeInfo, "subCity">,
  subCity: string,
  subCityLabel: string,
): OfficeInfo {
  return {
    ...base,
    subCity: subCityLabel,
    address: base.address.replace("{sub_city}", subCityLabel),
    name: base.name.replace("{sub_city}", subCityLabel),
  };
}

const kebeleOffice = (subCity: string, subCityLabel: string): OfficeInfo =>
  office(
    {
      name: "{sub_city} Sub-city Kebele Office",
      parentInstitution: "Addis Ababa City Administration",
      address: "{sub_city} Sub-city Administration, Kebele services wing, Ground floor",
      landmark: "Near sub-city administration main gate",
      latitude: 8.98,
      longitude: 38.78,
      phones: ["+251 11 000 0000"],
      workingHours: "Mon–Fri 08:30–17:00 (EAT)",
      referenceImageUrl: stockImages.kebele,
    },
    subCity,
    subCityLabel,
  );

const passportOffice = (subCityLabel: string): OfficeInfo => ({
  name: "Immigration and Citizenship Service — Main Department",
  parentInstitution: "Immigration and Citizenship Service",
  subCity: subCityLabel,
  address: "Addis Ababa, around Mexico Square, Main Department building",
  landmark: "ICS Main Department — follow signage for passport services",
  latitude: 9.005,
  longitude: 38.75,
  phones: ["+251 11 662 7688", "+251 11 662 7699"],
  workingHours: "Mon–Fri 08:30–16:30 (EAT)",
  referenceImageUrl: stockImages.passport,
});

const ercaOffice = (subCity: string, subCityLabel: string): OfficeInfo =>
  office(
    {
      name: "ERCA {sub_city} Branch",
      parentInstitution: "Ethiopian Revenue and Customs Authority",
      address: "{sub_city} Sub-city, ERCA taxpayer service centre",
      phones: ["+251 11 000 0001"],
      workingHours: "Mon–Fri 08:30–17:00 (EAT)",
      referenceImageUrl: "/references/erca-office.svg",
    },
    subCity,
    subCityLabel,
  );

const tradeBureau = (subCity: string, subCityLabel: string): OfficeInfo =>
  office(
    {
      name: "{sub_city} Sub-city Trade Bureau",
      parentInstitution: "Addis Ababa Trade Bureau",
      address: "{sub_city} Sub-city trade licensing desk",
      phones: ["+251 11 000 0002"],
      workingHours: "Mon–Fri 08:30–17:00 (EAT)",
      referenceImageUrl: stockImages.trade,
    },
    subCity,
    subCityLabel,
  );

/** Step templates — office resolved per sub-city at build time */
export function getPassportSteps(
  subCity: string,
  subCityLabel: string,
): ProcessStepTemplate[] {
  const kebele = kebeleOffice(subCity, subCityLabel);
  const passport = passportOffice(subCityLabel);

  return [
    {
      id: "birth_certificate",
      order: 1,
      title: "Birth certificate (or witness affidavit)",
      titleAm: "የትውልድ ሰርተፍኬት",
      issuingAuthority: "Local Kebele Office",
      formCode: "KB-BC-01",
      feeEtb: 50,
      paymentMethods: ["Cash at Kebele office"],
      estimatedDays: "3–7",
      legalBasis: "Resident registration requirements",
      requiredInputs: [
        "Parent national IDs (if available)",
        "Witness with Kebele ID (if no birth record on file)",
        "Two passport-size photographs",
      ],
      prerequisiteIds: [],
      office: kebele,
      rejectionReasons: [
        "Witness not registered in same Kebele",
        "Incomplete parent identification",
      ],
      sourceUrl: "https://addisababa.gov.et",
    },
    {
      id: "kebele_id",
      order: 2,
      title: "Kebele ID / Resident registration",
      titleAm: "የገበታ መታወቂያ",
      issuingAuthority: "Local Kebele Office",
      formCode: "KB-ID-02",
      feeEtb: 0,
      paymentMethods: ["No fee (verify locally)"],
      estimatedDays: "3–7",
      requiredInputs: [
        "Birth certificate or valid witness affidavit",
        "Proof of address (utility bill or landlord letter)",
        "Two passport-size photographs",
      ],
      prerequisiteIds: ["birth_certificate"],
      office: kebele,
      rejectionReasons: [
        "Address proof missing Kebele stamp",
        "Photographs do not meet specification",
      ],
    },
    {
      id: "passport",
      order: 3,
      title: "Ethiopian passport (new / renewal)",
      titleAm: "የኢትዮጵያ ፓስፖርት",
      issuingAuthority: "Immigration and Citizenship Service",
      formCode: "ICS-P-100",
      feeEtb: 2500,
      paymentMethods: [
        "CBE Birr mobile banking",
        "Cash at designated bank before appointment",
        "Online appointment portal (when available)",
      ],
      estimatedDays: "10–21",
      legalBasis: "Immigration Proclamation — passport issuance",
      requiredInputs: [
        "Valid Kebele ID or National ID",
        "Birth certificate",
        "Completed passport application form",
        "Two biometric photographs (ICS specification)",
        "Previous passport (for renewal)",
        "Payment receipt",
      ],
      prerequisiteIds: ["kebele_id", "birth_certificate"],
      office: passport,
      rejectionReasons: [
        "Payment receipt not attached",
        "Photographs wrong background or size",
        "Kebele stamp missing on supporting letter",
        "Appointment slot not booked",
      ],
      sourceUrl: "https://www.ics.gov.et",
    },
  ];
}

export function getKebeleIdSteps(
  subCity: string,
  subCityLabel: string,
): ProcessStepTemplate[] {
  return getPassportSteps(subCity, subCityLabel).slice(0, 2);
}

export function getBusinessSteps(
  subCity: string,
  subCityLabel: string,
  includeFintech = false,
): ProcessStepTemplate[] {
  const kebele = kebeleOffice(subCity, subCityLabel);
  const erca = ercaOffice(subCity, subCityLabel);
  const trade = tradeBureau(subCity, subCityLabel);

  const steps: ProcessStepTemplate[] = [
    {
      id: "kebele_id",
      order: 1,
      title: "Kebele ID / National ID",
      issuingAuthority: "Local Kebele Office",
      feeEtb: 0,
      paymentMethods: ["No fee (verify locally)"],
      estimatedDays: "3–7",
      requiredInputs: ["Birth certificate or witness", "Proof of address", "Photographs"],
      prerequisiteIds: [],
      office: kebele,
      rejectionReasons: ["Missing Kebele stamp on address proof"],
    },
    {
      id: "notarized_lease",
      order: 2,
      title: "Notarized lease agreement",
      issuingAuthority: "Sub-city notary office",
      feeEtb: 500,
      paymentMethods: ["Cash at notary office"],
      estimatedDays: "1",
      requiredInputs: ["Original lease agreement", "Kebele ID", "Owner consent if applicable"],
      prerequisiteIds: ["kebele_id"],
      office: office(
        {
          name: "{sub_city} Sub-city Notary Office",
          parentInstitution: "Addis Ababa City Administration",
          address: "{sub_city} Sub-city justice & notary services",
          phones: ["+251 11 000 0003"],
          workingHours: "Mon–Fri 08:30–17:00 (EAT)",
          referenceImageUrl: stockImages.notary,
        },
        subCity,
        subCityLabel,
      ),
      rejectionReasons: ["Lease missing landlord signature", "Kebele stamp not applied"],
    },
    {
      id: "tin",
      order: 3,
      title: "TIN certificate",
      formCode: "IT-101",
      issuingAuthority: "Ethiopian Revenue and Customs Authority",
      feeEtb: 0,
      paymentMethods: ["No issuance fee"],
      estimatedDays: "1–2",
      legalBasis: "Proc. 1396/2024",
      requiredInputs: ["Notarized lease", "Kebele ID", "Completed IT-101 form"],
      prerequisiteIds: ["notarized_lease", "kebele_id"],
      office: erca,
      rejectionReasons: ["Lease not notarized", "Form IT-101 incomplete"],
      sourceUrl: "https://erca.gov.et",
    },
    {
      id: "commercial_registration",
      order: 4,
      title: "Commercial registration",
      issuingAuthority: "Ministry of Trade and Regional Integration",
      feeEtb: 1200,
      paymentMethods: ["Bank payment slip", "MoTRI online portal"],
      estimatedDays: "2–3",
      requiredInputs: ["TIN certificate", "Memorandum of association (PLC)", "Name reservation"],
      prerequisiteIds: ["tin"],
      office: {
        name: "MoTRI Business Registration Office",
        parentInstitution: "Ministry of Trade and Regional Integration",
        subCity: "City-wide",
        address: "Addis Ababa, MoTRI main registration hall",
        phones: ["+251 11 000 0004"],
        workingHours: "Mon–Fri 08:30–17:00 (EAT)",
        referenceImageUrl: stockImages.registration,
      },
      rejectionReasons: ["Name reservation expired", "TIN mismatch"],
      sourceUrl: "https://motrade.gov.et",
    },
    {
      id: "trade_license",
      order: 5,
      title: "Trade license",
      issuingAuthority: "Sub-city trade bureau",
      feeEtb: 800,
      paymentMethods: ["Cash", "CBE Birr at sub-city treasury"],
      estimatedDays: "3–5",
      requiredInputs: [
        "Commercial registration certificate",
        "TIN certificate",
        "Lease / business premises proof",
        "Sector-specific clearance (if applicable)",
      ],
      prerequisiteIds: ["commercial_registration", "tin"],
      office: trade,
      rejectionReasons: [
        "Premises proof missing bureau stamp",
        "Activity code mismatch with registration",
      ],
    },
  ];

  if (includeFintech) {
    steps.push({
      id: "nbe_fintech_permit",
      order: 6,
      title: "NBE fintech permit",
      issuingAuthority: "National Bank of Ethiopia",
      feeEtb: null,
      paymentMethods: ["As per NBE directive — bank transfer"],
      estimatedDays: "6–12 weeks",
      legalBasis: "NBE payment instrument issuer directive",
      sectorSpecific: true,
      requiredInputs: [
        "Trade license",
        "IT audit report",
        "Capital adequacy statement",
        "Business plan",
      ],
      prerequisiteIds: ["trade_license"],
      office: {
        name: "National Bank of Ethiopia — Licensing",
        parentInstitution: "National Bank of Ethiopia",
        subCity: "Addis Ababa",
        address: "NBE headquarters, licensing division",
        phones: ["+251 11 000 0005"],
        workingHours: "Mon–Fri 08:30–16:30 (EAT)",
        referenceImageUrl: stockImages.fintech,
      },
      rejectionReasons: ["Insufficient capital proof", "IT audit outdated"],
      sourceUrl: "https://nbe.gov.et",
    });
  }

  return steps;
}

export type ProcessGoal = {
  id: string;
  label: string;
  category: "identity" | "travel" | "business" | "tax";
  description: string;
  getSteps: (subCity: string, subCityLabel: string, options?: { fintech?: boolean }) => ProcessStepTemplate[];
};

export const PROCESS_GOALS: ProcessGoal[] = [
  {
    id: "passport",
    label: "Passport",
    category: "travel",
    description: "New or renewal passport through Immigration and Citizenship Service.",
    getSteps: getPassportSteps,
  },
  {
    id: "kebele_id",
    label: "Kebele ID",
    category: "identity",
    description: "Local resident identification at your Kebele office.",
    getSteps: getKebeleIdSteps,
  },
  {
    id: "tin",
    label: "TIN certificate",
    category: "tax",
    description: "Tax identification number from ERCA.",
    getSteps: (sc, sl) =>
      getBusinessSteps(sc, sl).filter((s) => s.order <= 3),
  },
  {
    id: "trade_license",
    label: "Trade license",
    category: "business",
    description: "Sub-city trade bureau license for operating a business.",
    getSteps: (sc, sl) => getBusinessSteps(sc, sl),
  },
  {
    id: "commercial_registration",
    label: "Commercial registration",
    category: "business",
    description: "Register your company with MoTRI.",
    getSteps: (sc, sl) =>
      getBusinessSteps(sc, sl).filter((s) => s.order <= 4),
  },
  {
    id: "fintech_license",
    label: "Fintech license",
    category: "business",
    description: "Full path including NBE fintech permit.",
    getSteps: (sc, sl) => getBusinessSteps(sc, sl, true),
  },
];

export const ALL_DOCUMENT_IDS = [
  "birth_certificate",
  "kebele_id",
  "passport",
  "notarized_lease",
  "tin",
  "commercial_registration",
  "trade_license",
  "nbe_fintech_permit",
] as const;

export const DOCUMENT_LABELS: Record<string, string> = {
  birth_certificate: "Birth certificate",
  kebele_id: "Kebele ID / National ID",
  passport: "Ethiopian passport",
  notarized_lease: "Notarized lease agreement",
  tin: "TIN certificate",
  commercial_registration: "Commercial registration",
  trade_license: "Trade license",
  nbe_fintech_permit: "NBE fintech permit",
};
