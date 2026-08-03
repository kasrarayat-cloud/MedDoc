import path from 'node:path';
import type { NextConfig } from 'next';
import { withSentryConfig } from '@sentry/nextjs';

import { roundsRedirects } from './src/config/rounds-redirects';

const nextConfig: NextConfig = {
  output: 'standalone',

  // ── R1 — /dashboard forwards to /board under Rounds ───────────────────────
  // ⚠️ THIS IS HERE, NOT IN THE ROUTE, AND IT TOOK TWO WRONG PLACES TO LEARN
  // WHY. `app/dashboard/loading.tsx` wraps that segment in Suspense, so a
  // `redirect()` thrown anywhere in the page component AFTER an await cannot be
  // an HTTP redirect: the response has already begun, and Next answers `200`
  // with the loading skeleton and streams the redirect in the RSC payload.
  //
  // Measured, three ways, on the QA image:
  //   redirect after `await auth()`        → 200 + skeleton, URL stays /dashboard
  //   redirect hoisted above auth, but     → 200 + skeleton (STILL) — because
  //     still `await searchParams` first      reading searchParams suspends too
  //   this config redirect                 → 307, Location: /board
  //
  // The doctor reached the board in all three; the first two just charged them
  // a skeleton flash and a round trip, and told every bookmark and crawler that
  // `/dashboard` was a live 200. `redirects()` runs before routing, so nothing
  // renders and nothing suspends. It also keeps the auth edge middleware
  // (`src/proxy.ts`) untouched, which is not a file to experiment in.
  //
  // Evaluated at BUILD time, which is the same time `NEXT_PUBLIC_SKIN_ROUNDS`
  // is inlined — so the fork is baked into the image, exactly like every other
  // consumer of the flag. Flag off → an empty array → `/dashboard` is a page
  // again, unchanged.
  //
  // ORDER MATTERS: the `?tab=all` rule must come first. Next takes the first
  // match, and the bare `/dashboard` rule matches regardless of query string,
  // so reversing these silently drops the deep link.
  async redirects() {
    return roundsRedirects(process.env.NEXT_PUBLIC_SKIN_ROUNDS);
  },


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
  // unpdf (.pdf → text, wraps pdfjs) is externalized too — so webpack doesn't
  // try (and fail) to bundle pdfjs. BUT node-file-trace does NOT copy unpdf into
  // the standalone (it's an ESM dual-package; the 2026-06-04 incident shipped a
  // MODULE_NOT_FOUND). unpdf works fine once present + is self-contained (zero
  // deps), so the Dockerfile COPYs its dir into the runner explicitly and a
  // build-time bundle-assert enforces presence on every build.
  serverExternalPackages: ['pdfkit', 'fontkit', 'resend', 'mammoth', 'unpdf'],
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
