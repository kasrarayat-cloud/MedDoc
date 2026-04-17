import path from 'node:path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Standalone output for Docker deployment (copies only required node_modules).
  output: 'standalone',
  // Monorepo: tell Next the workspace root so file tracing follows imports
  // into packages/*. Without this, `next build` warns and may ship an
  // incomplete standalone bundle.
  outputFileTracingRoot: path.join(__dirname, '..', '..'),
  // pdf-parse bundles an old pdf.js that Turbopack can't parse.
  // Externalizing it tells Next.js to use Node's native require instead.
  serverExternalPackages: ['pdf-parse'],
};

export default nextConfig;
