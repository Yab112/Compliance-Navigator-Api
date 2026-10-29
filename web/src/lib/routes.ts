import { registerRoutes, type RouteDef } from "@cn/core/lib/navigation";

/** Breadcrumbs and "Back" for the public site. Staff pages live in the admin app. */
const WEB_ROUTES: RouteDef[] = [
  { pattern: "/", label: "Home" },
  // Services and paths
  { pattern: "/services", label: "Services", parent: "/" },
  { pattern: "/services/[id]", parent: "/services" },
  { pattern: "/roadmap/new", label: "Find my path", parent: "/" },
  { pattern: "/roadmap", label: "My current path", parent: "/" },
  { pattern: "/roadmap/[id]", label: "Saved path", parent: "/account/paths" },
  { pattern: "/chat", label: "Ask", parent: "/" },
  { pattern: "/about", label: "About", parent: "/" },
  { pattern: "/how-it-works", label: "How it works", parent: "/" },
  { pattern: "/legal", label: "Legal", parent: "/" },
  { pattern: "/legal/[slug]", parent: "/legal" },
  // Marketplace
  { pattern: "/hire", label: "Hire", parent: "/" },
  { pattern: "/hire/how-scores-work", label: "How scores work", parent: "/hire" },
  { pattern: "/providers/join", label: "Become a provider", parent: "/hire" },
  { pattern: "/providers/[slug]", label: "Provider", parent: "/hire" },
  // Organizations
  { pattern: "/organizations", label: "Organizations", parent: "/" },
  { pattern: "/organizations/join", label: "Register your organization", parent: "/organizations" },
  { pattern: "/organizations/[slug]", label: "Organization", parent: "/organizations" },
  { pattern: "/organizations/[slug]/services/[serviceSlug]", label: "Service", parent: "/organizations/[slug]" },
  // Account
  { pattern: "/account", label: "My account", parent: "/" },
  { pattern: "/account/requests", label: "My hires", parent: "/account" },
  { pattern: "/account/paths", label: "My saved paths", parent: "/account" },
  { pattern: "/account/support", label: "My support requests", parent: "/account" },
  { pattern: "/account/support/[id]", label: "Request", parent: "/account/support" },
  { pattern: "/me/provider", label: "My provider profile", parent: "/account" },
  { pattern: "/org", label: "My organization", parent: "/account" },
  { pattern: "/org/[orgId]", label: "Organization workspace", parent: "/org" },
  { pattern: "/org/[orgId]/services/new", label: "New service", parent: "/org/[orgId]" },
  { pattern: "/org/[orgId]/services/[serviceId]", label: "Service", parent: "/org/[orgId]" },
  { pattern: "/pay/test/[txRef]", label: "Test checkout", parent: "/account/requests" },
  { pattern: "/receipts/payment/[txRef]", label: "Receipt", parent: "/account/requests" },
  { pattern: "/receipts/statement/[txRef]", label: "Statement", parent: "/me/provider" },
  { pattern: "/receipts/payout/[id]", label: "Receipt", parent: "/me/provider" },
];

registerRoutes(WEB_ROUTES);
