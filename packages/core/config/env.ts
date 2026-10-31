import { z } from "zod";

const envSchema = z.object({
  NEXT_PUBLIC_API_BASE_URL: z.url(),
  NEXT_PUBLIC_SITE_URL: z.url(),
  NEXT_PUBLIC_ADMIN_URL: z.url(),
  NEXT_PUBLIC_SENTRY_DSN: z.url().optional(),
  SENTRY_AUTH_TOKEN: z.string().optional(),
  SENTRY_ORG: z.string().optional(),
  SENTRY_PROJECT: z.string().optional(),
});

export const env = envSchema.parse({
  NEXT_PUBLIC_API_BASE_URL:
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api/v1",
  // The public site and the staff app are separate deployments that link to each other
  NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  NEXT_PUBLIC_ADMIN_URL: process.env.NEXT_PUBLIC_ADMIN_URL ?? "http://localhost:3001",
  // Hosts often pass unset values as empty strings; treat those as not set
  NEXT_PUBLIC_SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN || undefined,
  SENTRY_AUTH_TOKEN: process.env.SENTRY_AUTH_TOKEN || undefined,
  SENTRY_ORG: process.env.SENTRY_ORG || undefined,
  SENTRY_PROJECT: process.env.SENTRY_PROJECT || undefined,
});

const join = (base: string, path: string) => base.replace(/\/$/, "") + (path.startsWith("/") ? path : `/${path}`);

/** Absolute link to a page on the public site (from the admin app). */
export const siteUrl = (path = "/") => join(env.NEXT_PUBLIC_SITE_URL, path);

/** Absolute link to a page in the admin app (from the public site). */
export const adminUrl = (path = "/") => join(env.NEXT_PUBLIC_ADMIN_URL, path);
