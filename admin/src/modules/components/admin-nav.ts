export type AdminNavItem = { href: string; label: string; group: string };

export const ADMIN_NAV: AdminNavItem[] = [
  { href: "/", label: "Overview", group: "Dashboard" },
  { href: "/support", label: "Support desk", group: "Dashboard" },
  { href: "/marketplace", label: "Providers", group: "Marketplace" },
  { href: "/marketplace/hires", label: "Hires and complaints", group: "Marketplace" },
  { href: "/marketplace/payments", label: "Payments", group: "Marketplace" },
  { href: "/marketplace/payouts", label: "Payouts", group: "Marketplace" },
  { href: "/marketplace/reviews", label: "Reviews", group: "Marketplace" },
  { href: "/organizations", label: "Organizations", group: "Organizations" },
  { href: "/submissions", label: "Service submissions", group: "Organizations" },
  { href: "/data-sources", label: "Data sources", group: "Data" },
  { href: "/catalog", label: "MESOB catalog", group: "Data" },
  { href: "/graph", label: "Knowledge graph", group: "Data" },
  { href: "/ai", label: "AI assistant", group: "Data" },
  { href: "/feedback", label: "Feedback queue", group: "Operations" },
  { href: "/users", label: "Users & roles", group: "Operations" },
];
