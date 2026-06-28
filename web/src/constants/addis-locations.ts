/** Addis Ababa sub-cities (kifle ketema) + search aliases for neighborhoods & spellings */

export type AddisLocation = {
  value: string;
  label: string;
  /** Extra terms for search (areas, Amharic transliteration, old names) */
  keywords: string[];
};

export const ADDIS_SUB_CITIES: AddisLocation[] = [
  {
    value: "addis_ketema",
    label: "Addis Ketema",
    keywords: ["addis ketema", "addis ketema", "merkato", "merkato", "autobus tera"],
  },
  {
    value: "akaki",
    label: "Akaki Kaliti",
    keywords: ["akaki", "akaki kaliti", "kaliti", "kality", "wellio"],
  },
  {
    value: "arada",
    label: "Arada",
    keywords: ["arada", "piassa", "piazza", "casanchis", "4 kilo", "saint lazarist"],
  },
  {
    value: "bole",
    label: "Bole",
    keywords: ["bole", "bolé", "mexico", "summit", "bole airport", "gerji"],
  },
  {
    value: "gulele",
    label: "Gulele",
    keywords: ["gulele", "gullele", "shiromeda", "entoto"],
  },
  {
    value: "kirkos",
    label: "Kirkos",
    keywords: ["kirkos", "kerkos", "kirkos", "mexico", "leghar", "old airport"],
  },
  {
    value: "kolfe",
    label: "Kolfe Keranio",
    keywords: ["kolfe", "kolfe keranio", "keranio", "saris", "aba samuel"],
  },
  {
    value: "lideta",
    label: "Lideta",
    keywords: ["lideta", "lideta", "mexico", "tekle haymanot"],
  },
  {
    value: "nifas_silk",
    label: "Nifas Silk-Lafto",
    keywords: ["nifas silk", "lafto", "saris", "kazanchis", "bulbula"],
  },
  {
    value: "yeka",
    label: "Yeka",
    keywords: ["yeka", "ferensay", "ferensai", "aware", "ayat", "cazanchise"],
  },
];

/** Popular picks shown above search */
export const POPULAR_SUB_CITIES = ["bole", "yeka", "kirkos", "arada"] as const;

export function findLocation(value: string): AddisLocation | undefined {
  return ADDIS_SUB_CITIES.find((l) => l.value === value);
}

export function getLocationLabel(value: string): string {
  return findLocation(value)?.label ?? value.replace(/_/g, " ");
}

export function filterLocations(query: string): AddisLocation[] {
  const q = query.trim().toLowerCase();
  if (!q) return ADDIS_SUB_CITIES;
  return ADDIS_SUB_CITIES.filter(
    (loc) =>
      loc.label.toLowerCase().includes(q) ||
      loc.value.replace(/_/g, " ").includes(q) ||
      loc.keywords.some((k) => k.includes(q)),
  );
}
