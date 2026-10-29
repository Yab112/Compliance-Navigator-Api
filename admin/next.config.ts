import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Shared code is TypeScript source in the workspace packages
  transpilePackages: ["@cn/core", "@cn/ui"],
};

export default nextConfig;
