export type AdminNavItem = { href: string; label: string; group: string };

export const ADMIN_NAV: AdminNavItem[] = [
  { href: "/admin", label: "Overview", group: "Dashboard" },
  { href: "/admin/support", label: "Support desk", group: "Dashboard" },
  { href: "/admin/marketplace", label: "Providers", group: "Marketplace" },
  { href: "/admin/marketplace/hires", label: "Hires and complaints", group: "Marketplace" },
  { href: "/admin/marketplace/payments", label: "Payments", group: "Marketplace" },
  { href: "/admin/marketplace/payouts", label: "Payouts", group: "Marketplace" },
  { href: "/admin/marketplace/reviews", label: "Reviews", group: "Marketplace" },
  { href: "/admin/organizations", label: "Organizations", group: "Organizations" },
  { href: "/admin/submissions", label: "Service submissions", group: "Organizations" },
  { href: "/admin/data-sources", label: "Data sources", group: "Data" },
  { href: "/admin/catalog", label: "MESOB catalog", group: "Data" },
  { href: "/admin/graph", label: "Knowledge graph", group: "Data" },
  { href: "/admin/ai", label: "AI assistant", group: "Data" },
  { href: "/admin/feedback", label: "Feedback queue", group: "Operations" },
  { href: "/admin/users", label: "Users & roles", group: "Operations" },
];
