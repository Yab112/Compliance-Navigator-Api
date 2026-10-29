import { ADDIS_SUB_CITIES } from "@cn/core/constants/addis-locations";

export { ADDIS_SUB_CITIES, POPULAR_SUB_CITIES, filterLocations, getLocationLabel, findLocation } from "@cn/core/constants/addis-locations";
export type { AddisLocation } from "@cn/core/constants/addis-locations";

/** @deprecated Use ADDIS_SUB_CITIES, kept for existing imports */
export const SUB_CITIES = ADDIS_SUB_CITIES.map(({ value, label }) => ({
  value,
  label,
}));

export { PROCESS_GOALS, DOCUMENT_LABELS, ALL_DOCUMENT_IDS } from "@/data/process-graph";
