/**
 * Portal identity shown in the header and footer.
 * We are an independent platform and a data partner of MESOB, not a MESOB site,
 * so never present the portal as a government office.
 */
export const siteIdentity = {
  name: "Compliance Navigator",
  nameAm: "የአገልግሎት መመሪያ",
  /** Top utility bar */
  servingLine: "Every requirement, every office, every trusted agent",
  servingLineAm: "ሁሉም መስፈርቶች፣ ሁሉም ቢሮዎች፣ የታመኑ ወኪሎች",
  disclaimer:
    "Requirements come from the organizations themselves and from official catalogs such as MESOB, our partner. Always confirm at the service window before paying.",
};

export const mainNav = [
  { href: "/", label: "Home", am: "መነሻ" },
  { href: "/services", label: "Services", am: "አገልግሎቶች" },
  { href: "/roadmap/new", label: "Find my path", am: "ሂደቴን ፈልግ" },
  { href: "/hire", label: "Hire", am: "ይቅጠሩ" },
  { href: "/organizations", label: "Organizations", am: "ተቋማት" },
  { href: "/chat", label: "Ask", am: "ይጠይቁ" },
  { href: "/about", label: "About", am: "ስለ እኛ" },
] as const;
