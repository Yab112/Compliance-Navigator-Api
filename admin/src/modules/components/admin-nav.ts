/** `perm`: hide the link from staff without this permission (the server still checks every request). */
export type AdminNavItem = { href: string; label: string; group: string; perm?: string };

/** Navigation sections (menus in the top bar) in display order, with a line explaining what belongs in each. */
export const ADMIN_NAV_GROUPS: { name: string; hint: string }[] = [
  { name: "Daily work", hint: "Queues that need a person today" },
  { name: "Marketplace", hint: "Providers, the jobs they take and what clients say" },
  { name: "Money", hint: "What clients paid and what providers are owed" },
  { name: "Organizations", hint: "Government and partner offices and their services" },
  { name: "Content and data", hint: "Where requirements come from and how they are shown" },
  { name: "People", hint: "Public accounts" },
  { name: "Administration", hint: "Staff, their access and platform rules" },
];

export const ADMIN_NAV: AdminNavItem[] = [
  { href: "/", label: "Overview", group: "Daily work" },
  { href: "/access/approvals", label: "Approvals", group: "Daily work" },
  { href: "/support", label: "Support desk", group: "Daily work" },
  { href: "/feedback", label: "Feedback queue", group: "Daily work" },
  { href: "/marketplace", label: "Providers", group: "Marketplace" },
  { href: "/marketplace/hires", label: "Hires and complaints", group: "Marketplace" },
  { href: "/marketplace/reviews", label: "Reviews", group: "Marketplace" },
  { href: "/marketplace/payments", label: "Payments and refunds", group: "Money" },
  { href: "/marketplace/payouts", label: "Payouts", group: "Money" },
  { href: "/marketplace/payment-health", label: "Payment health", group: "Money" },
  { href: "/organizations", label: "Organizations", group: "Organizations" },
  { href: "/submissions", label: "Service submissions", group: "Organizations" },
  { href: "/data-sources", label: "Data sources", group: "Content and data" },
  { href: "/catalog", label: "MESOB catalog", group: "Content and data" },
  { href: "/graph", label: "Knowledge graph", group: "Content and data" },
  { href: "/ai", label: "AI assistant", group: "Content and data" },
  { href: "/users", label: "Public users", group: "People" },
  { href: "/access/staff", label: "Staff", group: "Administration", perm: "staff.view" },
  { href: "/access/roles", label: "Roles", group: "Administration", perm: "roles.view" },
  { href: "/access/permissions", label: "Permissions", group: "Administration", perm: "roles.view" },
  { href: "/access/audit", label: "Audit log", group: "Administration", perm: "audit.view" },
  { href: "/settings", label: "Platform settings", group: "Administration" },
];
