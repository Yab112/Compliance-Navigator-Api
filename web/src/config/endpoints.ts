/**
 * @deprecated Use `apiPaths` from `@/lib/constants/api-paths` and query keys in `src/api/*` hooks.
 * Kept for backward compatibility with older docs.
 */
import { apiPaths } from "@/lib/constants/api-paths";

export const endpoints = {
  auth: {
    login: { query: "login", endpoint: `/${apiPaths.users.login}` },
    register: { query: "register", endpoint: `/${apiPaths.users.register}` },
    me: { query: "me", endpoint: `/${apiPaths.auth.me}` },
    logout: { query: "logout", endpoint: `/${apiPaths.auth.logout}` },
  },
  processes: { query: "processes", endpoint: `/${apiPaths.processes}` },
  roadmaps: { query: "roadmaps", endpoint: `/${apiPaths.roadmaps}` },
};
