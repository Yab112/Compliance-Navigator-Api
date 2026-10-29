import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";

// One id per build: pages compare theirs with the server's to offer a reload after an update.
// Set once in the env so the build's worker processes, which reload this file, all share it.
process.env.BUILD_ID ??= `b${Date.now()}`;
const buildId = process.env.BUILD_ID;

const adminUrl = (process.env.NEXT_PUBLIC_ADMIN_URL ?? "http://localhost:3001").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Shared code is TypeScript source in the workspace packages
  transpilePackages: ["@cn/core", "@cn/ui"],
  // Staff pages moved to the admin app; old links (bookmarks, notifications) still land there
  async redirects() {
    return [
      { source: "/admin", destination: `${adminUrl}/`, permanent: false },
      { source: "/admin/:path*", destination: `${adminUrl}/:path*`, permanent: false },
    ];
  },
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
