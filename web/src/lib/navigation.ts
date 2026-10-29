/**
 * Where every page sits, for breadcrumbs and "Back". One map for the whole app: a page's parent is
 * the page a person would expect one level up (My hires -> My account -> Home), not always "/".
 *
 * Dynamic pages (a provider, an organization, a ticket) get their label from the page itself
 * (PageNav `label`), and the label is remembered for the session so their children can show it.
 */

type RouteDef = { pattern: string; label?: string; parent?: string };

const ROUTES: RouteDef[] = [
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
  // Admin
  { pattern: "/admin", label: "Admin dashboard", parent: "/" },
  { pattern: "/admin/support", label: "Support desk", parent: "/admin" },
  { pattern: "/admin/support/[id]", label: "Ticket", parent: "/admin/support" },
  { pattern: "/admin/marketplace", label: "Providers", parent: "/admin" },
  { pattern: "/admin/marketplace/hires", label: "Hires and complaints", parent: "/admin" },
  { pattern: "/admin/marketplace/payments", label: "Payments", parent: "/admin" },
  { pattern: "/admin/marketplace/payouts", label: "Payouts", parent: "/admin" },
  { pattern: "/admin/marketplace/reviews", label: "Reviews", parent: "/admin" },
  { pattern: "/admin/marketplace/[id]", label: "Provider", parent: "/admin/marketplace" },
  { pattern: "/admin/organizations", label: "Organizations", parent: "/admin" },
  { pattern: "/admin/organizations/[id]", label: "Organization", parent: "/admin/organizations" },
  { pattern: "/admin/submissions", label: "Service submissions", parent: "/admin" },
  { pattern: "/admin/submissions/[id]", label: "Submission", parent: "/admin/submissions" },
  { pattern: "/admin/users", label: "Users and roles", parent: "/admin" },
  { pattern: "/admin/feedback", label: "Feedback queue", parent: "/admin" },
  { pattern: "/admin/ai", label: "AI assistant", parent: "/admin" },
  { pattern: "/admin/catalog", label: "MESOB catalog", parent: "/admin" },
  { pattern: "/admin/data-sources", label: "Data sources", parent: "/admin" },
  { pattern: "/admin/graph", label: "Knowledge graph", parent: "/admin" },
];

const LABELS_KEY = "cn-nav-labels";
export const NAV_EVENT = "cn-nav";

function match(pattern: string, path: string): Record<string, string> | null {
  const p = pattern.split("/").filter(Boolean);
  const s = path.split("/").filter(Boolean);
  if (p.length !== s.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < p.length; i++) {
    if (p[i].startsWith("[")) params[p[i].slice(1, -1)] = s[i];
    else if (p[i] !== s[i]) return null;
  }
  return params;
}

/** The route a path belongs to; static patterns win over dynamic ones ("/roadmap/new" vs "/roadmap/[id]"). */
export function findRoute(path: string): { def: RouteDef; params: Record<string, string> } | null {
  const candidates = ROUTES.map((def) => ({ def, params: match(def.pattern, path) })).filter((c) => c.params);
  candidates.sort((a, b) => (a.def.pattern.match(/\[/g)?.length ?? 0) - (b.def.pattern.match(/\[/g)?.length ?? 0));
  const best = candidates[0];
  return best ? { def: best.def, params: best.params! } : null;
}

function fill(pattern: string, params: Record<string, string>): string {
  return pattern.replace(/\[(\w+)\]/g, (_, k: string) => params[k] ?? k);
}

export function readLabels(): Record<string, string> {
  try {
    return JSON.parse(sessionStorage.getItem(LABELS_KEY) ?? "{}");
  } catch {
    return {};
  }
}

/** Pages with a dynamic title (a provider's name) remember it so child pages can show it. */
export function rememberLabel(path: string, label: string) {
  try {
    const labels = readLabels();
    if (labels[path] === label) return;
    labels[path] = label;
    sessionStorage.setItem(LABELS_KEY, JSON.stringify(labels));
    window.dispatchEvent(new Event(NAV_EVENT));
  } catch {}
}

/** `labels`: titles remembered this session (pass {} before the page has mounted). */
export function labelFor(path: string, labels: Record<string, string> = {}): string {
  const def = findRoute(path)?.def;
  if (def?.label && !def.pattern.includes("[")) return def.label; // fixed pages: one name everywhere
  return labels[path] ?? def?.label ?? "previous page";
}

export type Crumb = { label: string; href: string };

/** Home › … › parent, for the current path (the current page itself is added by the caller). */
export function trailFor(path: string, labels: Record<string, string> = {}): Crumb[] {
  const trail: Crumb[] = [];
  let found = findRoute(path);
  let guard = 0;
  while (found?.def.parent && guard++ < 8) {
    const href = fill(found.def.parent, found.params);
    trail.unshift({ label: labelFor(href, labels), href });
    found = findRoute(href);
  }
  return trail;
}

export function parentOf(path: string): string {
  const found = findRoute(path);
  return found?.def.parent ? fill(found.def.parent, found.params) : "/";
}

// ---------------------------------------------------------------- in-app history, for "Back"

const STACK_KEY = "cn-nav-stack";

export function readStack(): string[] {
  try {
    return JSON.parse(sessionStorage.getItem(STACK_KEY) ?? "[]");
  } catch {
    return [];
  }
}

/** Called on every navigation. Going back pops; a new page pushes; same page with new params replaces. */
export function recordVisit(url: string) {
  try {
    const stack = readStack();
    const path = (u: string) => u.split("?")[0];
    if (stack.length >= 2 && stack[stack.length - 2] === url) stack.pop();
    else if (stack.length && path(stack[stack.length - 1]) === path(url)) stack[stack.length - 1] = url;
    else stack.push(url);
    sessionStorage.setItem(STACK_KEY, JSON.stringify(stack.slice(-30)));
    window.dispatchEvent(new Event(NAV_EVENT));
  } catch {}
}

/** For useSyncExternalStore: one string that changes whenever history or labels change. */
export function navSnapshot(): string {
  try {
    return `${sessionStorage.getItem(STACK_KEY) ?? "[]"}\u0000${sessionStorage.getItem(LABELS_KEY) ?? "{}"}`;
  } catch {
    return "";
  }
}

export function subscribeNav(onChange: () => void): () => void {
  window.addEventListener(NAV_EVENT, onChange);
  return () => window.removeEventListener(NAV_EVENT, onChange);
}
