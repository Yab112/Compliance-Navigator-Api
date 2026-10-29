import { registerRoutes, type RouteDef } from "@cn/core/lib/navigation";

/** Breadcrumbs and "Back" for the admin app. */
const ADMIN_ROUTES: RouteDef[] = [
  { pattern: "/", label: "Admin dashboard" },
  { pattern: "/support", label: "Support desk", parent: "/" },
  { pattern: "/support/[id]", label: "Ticket", parent: "/support" },
  { pattern: "/marketplace", label: "Providers", parent: "/" },
  { pattern: "/marketplace/hires", label: "Hires and complaints", parent: "/" },
  { pattern: "/marketplace/payments", label: "Payments", parent: "/" },
  { pattern: "/marketplace/payouts", label: "Payouts", parent: "/" },
  { pattern: "/marketplace/reviews", label: "Reviews", parent: "/" },
  { pattern: "/marketplace/[id]", label: "Provider", parent: "/marketplace" },
  { pattern: "/organizations", label: "Organizations", parent: "/" },
  { pattern: "/organizations/[id]", label: "Organization", parent: "/organizations" },
  { pattern: "/submissions", label: "Service submissions", parent: "/" },
  { pattern: "/submissions/[id]", label: "Submission", parent: "/submissions" },
  { pattern: "/users", label: "Users and roles", parent: "/" },
  { pattern: "/feedback", label: "Feedback queue", parent: "/" },
  { pattern: "/ai", label: "AI assistant", parent: "/" },
  { pattern: "/catalog", label: "MESOB catalog", parent: "/" },
  { pattern: "/data-sources", label: "Data sources", parent: "/" },
  { pattern: "/graph", label: "Knowledge graph", parent: "/" },
  { pattern: "/settings", label: "Platform settings", parent: "/" },
];

registerRoutes(ADMIN_ROUTES);
