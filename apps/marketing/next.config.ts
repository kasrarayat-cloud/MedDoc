import path from 'node:path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '..', '..'),
  experimental: {
    // Three.js is large; keep it out of the main server bundle. The
    // 3D hero is a 'use client' component so this mostly just quiets
    // Webpack's bundle-analysis warning.
    optimizePackageImports: ['lucide-react'],
  },
};

export default nextConfig;
