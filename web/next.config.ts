import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";
import path from "node:path";

// One id per build: pages compare theirs with the server's to offer a reload after an update.
// Set once in the env so the build's worker processes, which reload this file, all share it.
process.env.BUILD_ID ??= `b${Date.now()}`;
const buildId = process.env.BUILD_ID;

const isProd = process.env.NODE_ENV === "production";

function originOf(url: string | undefined): string | null {
  try {
    return url ? new URL(url).origin : null;
  } catch {
    return null;
  }
}

// The API serves JSON and uploaded photos and logos
// Same fallback as packages/core/config/env.ts, so the policy allows the API the app actually calls
const apiOrigin = originOf(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api/v1");

/*
 * Content Security Policy. Scripts: Next.js App Router writes small inline scripts into every page
 * (the streamed page data), so script-src needs either a per-request nonce or 'unsafe-inline'. Nonces
 * would force every page to render on each request (no static pages or caching), so we use
 * 'unsafe-inline' with 'self' only: no other script origin is allowed, React escapes all text, and the
 * app has no dangerouslySetInnerHTML. Styles need 'unsafe-inline' for Next and Tailwind.
 * Payments (Chapa) and Fayda are full-page redirects, which CSP does not restrict. Sentry reports go
 * through our own /monitoring route, so they count as 'self'. Fonts are self-hosted by next/font.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  // Institution logos and photo credits come from other https sites
  ["img-src 'self' data: blob: https:", apiOrigin].filter(Boolean).join(" "),
  "font-src 'self' data:",
  // Voice input records audio in the browser
  "media-src 'self' blob:",
  ["connect-src 'self'", apiOrigin, isProd ? null : "ws: wss:"].filter(Boolean).join(" "),
  "worker-src 'self' blob:",
  "frame-src 'none'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  ...(isProd ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Only the microphone, for voice questions
  { key: "Permissions-Policy", value: "camera=(), microphone=(self), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  ...(isProd ? [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }] : []),
];

const nextConfig: NextConfig = {
  // Shared code is TypeScript source in the workspace packages
  transpilePackages: ["@cn/core", "@cn/ui"],
  // Docker images (Dockerfile.next) run the small self-contained server; the workspace root is traced
  // so the shared packages are included
  ...(process.env.NEXT_STANDALONE
    ? { output: "standalone" as const, outputFileTracingRoot: path.join(process.cwd(), "..") }
    : {}),
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  // No link or redirect to the staff app: it has its own address and its own sign-in
  generateBuildId: async () => buildId,
  env: { NEXT_PUBLIC_BUILD_ID: buildId },
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/**",
      },
    ],
  },
};

export default withSentryConfig(nextConfig, {
  // For all available options, see:
  // https://www.npmjs.com/package/@sentry/webpack-plugin#options

  org: process.env.SENTRY_ORG,

  project: process.env.SENTRY_PROJECT,

  // Only print logs for uploading source maps in CI
  silent: !process.env.CI,

  // For all available options, see:
  // https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/

  // Upload a larger set of source maps for prettier stack traces (increases build time)
  widenClientFileUpload: true,

  // Route browser requests to Sentry through a Next.js rewrite to circumvent ad-blockers.
  // This can increase your server load as well as your hosting bill.
  // Note: Check that the configured route will not match with your Next.js middleware, otherwise reporting of client-
  // side errors will fail.
  tunnelRoute: "/monitoring",

  webpack: {
    // Enables automatic instrumentation of Vercel Cron Monitors. (Does not yet work with App Router route handlers.)
    // See the following for more information:
    // https://docs.sentry.io/product/crons/
    // https://vercel.com/docs/cron-jobs
    automaticVercelMonitors: true,

    // Tree-shaking options for reducing bundle size
    treeshake: {
      // Automatically tree-shake Sentry logger statements to reduce bundle size
      removeDebugLogging: true,
    },
  }
});
