import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for Docker deployment (copies only required node_modules)
  output: 'standalone',
  // pdf-parse bundles an old pdf.js that Turbopack can't parse.
  // Externalizing it tells Next.js to use Node's native require instead.
  serverExternalPackages: ['pdf-parse'],
};

export default nextConfig;
