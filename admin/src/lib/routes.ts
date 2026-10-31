import { registerRoutes, type RouteDef } from "@cn/core/lib/navigation";

/** Breadcrumbs and "Back" for the admin app. */
const ADMIN_ROUTES: RouteDef[] = [
  { pattern: "/", label: "Admin dashboard" },
  { pattern: "/support", label: "Support desk", parent: "/" },
  { pattern: "/support/[id]", label: "Ticket", parent: "/support" },
  { pattern: "/marketplace", label: "Providers", parent: "/" },
  { pattern: "/marketplace/hires", label: "Hires and complaints", parent: "/" },
  { pattern: "/marketplace/hires/[id]", label: "Hire", parent: "/marketplace/hires" },
  { pattern: "/marketplace/payments", label: "Payments", parent: "/" },
  { pattern: "/marketplace/payouts", label: "Payouts", parent: "/" },
  { pattern: "/marketplace/payment-health", label: "Payment health", parent: "/" },
  { pattern: "/marketplace/reviews", label: "Reviews", parent: "/" },
  { pattern: "/marketplace/[id]", label: "Provider", parent: "/marketplace" },
  { pattern: "/organizations", label: "Organizations", parent: "/" },
  { pattern: "/organizations/[id]", label: "Organization", parent: "/organizations" },
  { pattern: "/submissions", label: "Service submissions", parent: "/" },
  { pattern: "/submissions/[id]", label: "Submission", parent: "/submissions" },
  { pattern: "/users", label: "Public users", parent: "/" },
  { pattern: "/feedback", label: "Feedback queue", parent: "/" },
  { pattern: "/ai", label: "AI assistant", parent: "/" },
  { pattern: "/catalog", label: "MESOB catalog", parent: "/" },
  { pattern: "/data-sources", label: "Data sources", parent: "/" },
  { pattern: "/graph", label: "Knowledge graph", parent: "/" },
  { pattern: "/settings", label: "Platform settings", parent: "/" },
  { pattern: "/access/staff", label: "Staff", parent: "/" },
  { pattern: "/access/staff/[id]", label: "Staff member", parent: "/access/staff" },
  { pattern: "/access/roles", label: "Roles", parent: "/" },
  { pattern: "/access/roles/new", label: "New role", parent: "/access/roles" },
  { pattern: "/access/roles/[id]", label: "Role", parent: "/access/roles" },
  { pattern: "/access/permissions", label: "Permissions", parent: "/" },
  { pattern: "/access/approvals", label: "Approvals", parent: "/" },
  { pattern: "/access/audit", label: "Audit log", parent: "/" },
  { pattern: "/account", label: "My account", parent: "/" },
];

registerRoutes(ADMIN_ROUTES);
