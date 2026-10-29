/**
 * Which permission each existing admin page needs, so the sidebar can hide pages a staff member
 * can't open. Pages not listed stay visible; the server is the real check either way.
 */
export const NAV_PERMISSIONS: Record<string, string> = {
  "/": "overview.view",
  "/support": "support.view",
  "/marketplace": "providers.view",
  "/marketplace/hires": "hires.view",
  "/marketplace/payments": "payments.view",
  "/marketplace/payouts": "payouts.view",
  "/marketplace/reviews": "reviews.view",
  "/organizations": "organizations.view",
  "/submissions": "submissions.view",
  "/data-sources": "data_sources.view",
  "/catalog": "data_sources.view",
  "/graph": "graph.view",
  "/ai": "ai.view",
  "/feedback": "feedback.view",
  "/users": "users.view",
  "/settings": "settings.view",
};
