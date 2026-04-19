import path from 'node:path';
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '..', '..'),
  // T-M7: pdfkit + resend both reach into Node-only built-ins (fs, net,
  // tls, dns) and ship asset files (font AFM, type-1 metrics) that
  // Next's bundler can't handle. Marking them external tells Next to
  // leave the imports as-is and require() them at runtime from the
  // standalone build's node_modules/.
  serverExternalPackages: ['pdfkit', 'fontkit', 'resend'],
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
};

export default nextConfig;
