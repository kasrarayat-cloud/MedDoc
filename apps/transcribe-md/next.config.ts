import path from 'node:path';
import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

const nextConfig: NextConfig = {
  output: 'standalone',
  outputFileTracingRoot: path.join(__dirname, '..', '..'),
  // T-M7: pdfkit + resend both reach into Node-only built-ins (fs, net,
  // tls, dns) and ship asset files (font AFM, type-1 metrics) that
  // Next's bundler can't handle. Marking them external tells Next to
  // leave the imports as-is and require() them at runtime from the
  // standalone build's node_modules/.
  // Phase 2b: mammoth (.docx → text) is likewise node-only — bundling it via
  // webpack/tracing failed (it ended up in neither .next/server nor
  // node_modules, so .docx silently fell back to paste). Externalizing it makes
  // node-file-trace copy node_modules/mammoth into the standalone output.
  serverExternalPackages: ['pdfkit', 'fontkit', 'resend', 'mammoth'],
  experimental: {
    optimizePackageImports: ['lucide-react'],
  },
};

// Round 3 PR-H — A11-P1 source-map upload + release tagging.
// withSentryConfig wraps the Next config so the build:
//   1. uploads sourcemaps to Sentry (gated on SENTRY_AUTH_TOKEN)
//   2. tags every event with the release ref so /releases shows commits
//   3. hides the maps from the public bundle (silent: false → CI logs)
// When SENTRY_AUTH_TOKEN is unset (dev / first deploy), the wrapper
// degrades gracefully — events still flow but stack traces stay
// minified. See docs/runbooks/sentry-setup.md.
const sentryBuildOptions = {
  org: process.env.SENTRY_ORG?.trim() || undefined,
  project: process.env.SENTRY_PROJECT_TRANSCRIBE_MD?.trim() || undefined,
  authToken: process.env.SENTRY_AUTH_TOKEN?.trim() || undefined,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  hideSourceMaps: true,
  disableLogger: true,
  // Skip the wrapper entirely when no auth token — avoids "missing
  // SENTRY_AUTH_TOKEN" warnings during local pnpm dev.
  dryRun: !process.env.SENTRY_AUTH_TOKEN,
};

export default withSentryConfig(nextConfig, sentryBuildOptions);
