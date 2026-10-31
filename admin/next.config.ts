import type { NextConfig } from "next";
import path from "node:path";

const isProd = process.env.NODE_ENV === "production";

function originOf(url: string | undefined): string | null {
  try {
    return url ? new URL(url).origin : null;
  } catch {
    return null;
  }
}

// Same fallback as packages/core/config/env.ts, so the policy allows the API the app actually calls
const apiOrigin = originOf(process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api/v1");

/*
 * Content Security Policy for the staff app. Next.js App Router writes small inline scripts into every
 * page, so script-src needs a per-request nonce or 'unsafe-inline'; we use 'unsafe-inline' with 'self'
 * only (no other script origin, React escapes all text, no dangerouslySetInnerHTML). Styles need
 * 'unsafe-inline' for Next and Tailwind. Private documents are shown from blob: URLs after the API
 * hands them over. Fonts are self-hosted by next/font. Nothing may frame the staff app.
 */
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? "" : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline'",
  ["img-src 'self' data: blob: https:", apiOrigin].filter(Boolean).join(" "),
  "font-src 'self' data:",
  "media-src 'self' blob:",
  ["connect-src 'self'", apiOrigin, isProd ? null : "ws: wss:"].filter(Boolean).join(" "),
  "worker-src 'self' blob:",
  "frame-src 'none'",
  "frame-ancestors 'none'",
  // A PDF opened from a blob: URL keeps this policy, and the browser's PDF viewer counts as an object
  "object-src 'self' blob:",
  "base-uri 'self'",
  "form-action 'self'",
  ...(isProd ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Staff pages carry record ids in their addresses; never send them to other sites
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  // The staff app is never listed by search engines
  { key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" },
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
};

export default nextConfig;
