/** `perm`: hide the link from staff without this permission (the server still checks every request). */
export type AdminNavItem = { href: string; label: string; group: string; perm?: string };

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
  { href: "/users", label: "Public users", group: "Operations" },
  { href: "/settings", label: "Platform settings", group: "Operations" },
  { href: "/access/approvals", label: "Approvals", group: "Access" },
  { href: "/access/staff", label: "Staff", group: "Access", perm: "staff.view" },
  { href: "/access/roles", label: "Roles", group: "Access", perm: "roles.view" },
  { href: "/access/permissions", label: "Permissions", group: "Access", perm: "roles.view" },
  { href: "/access/audit", label: "Audit log", group: "Access", perm: "audit.view" },
  { href: "/account", label: "My account", group: "Access" },
];
