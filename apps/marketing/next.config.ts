import path from 'node:path';
import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

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

// Round 3 PR-H — A11-P1 source-map upload + release tagging.
// Marketing has no PHI but we still want stack traces deminified for
// the few client-side errors that surface (3D hero / form validation).
// Sentry project is separate from transcribe-md so alert routing stays
// clean. See docs/runbooks/sentry-setup.md.
const sentryBuildOptions = {
  org: process.env.SENTRY_ORG?.trim() || undefined,
  project: process.env.SENTRY_PROJECT_MARKETING?.trim() || undefined,
  authToken: process.env.SENTRY_AUTH_TOKEN?.trim() || undefined,
  silent: !process.env.CI,
  widenClientFileUpload: true,
  hideSourceMaps: true,
  disableLogger: true,
  dryRun: !process.env.SENTRY_AUTH_TOKEN,
};

export default withSentryConfig(nextConfig, sentryBuildOptions);
