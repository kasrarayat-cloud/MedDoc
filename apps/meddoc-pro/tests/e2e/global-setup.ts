// ============================================================================
// Playwright globalSetup — pre-warm Turbopack
// ----------------------------------------------------------------------------
// Phase 19 (h13-meddoc-e2e-tenancy-residual): under `next dev` the
// first request to a route triggers Turbopack's compile-on-demand,
// which can take 30+ seconds for /dashboard subtrees on a cold CI
// runner. Five tenancy/auth/chart-id specs were timing out on
// page.waitForURL() because the post-login redirect landed on a
// not-yet-compiled route.
//
// We hit each protected route once before the test suite begins, so
// Turbopack has compiled them by the time the first spec navigates.
// Failures here do NOT fail the suite — pre-warm is best-effort.
// ============================================================================

import type { FullConfig } from '@playwright/test';

const ROUTES = [
  '/',
  '/login',
  '/dashboard',
  '/dashboard/patients',
  '/dashboard/patients/abc',  // shape of the dynamic route — 404s but still compiles the segment
  '/system-admin',
];

export default async function globalSetup(_config: FullConfig) {
  const base = 'http://localhost:3000';
  const start = Date.now();
  console.log('[playwright globalSetup] pre-warming Turbopack…');
  for (const path of ROUTES) {
    const t0 = Date.now();
    try {
      const res = await fetch(`${base}${path}`, {
        redirect: 'manual',
        signal: AbortSignal.timeout(60_000),
      });
      console.log(
        `[playwright globalSetup]   ${path} → ${res.status} (${Date.now() - t0}ms)`
      );
    } catch (err) {
      console.warn(
        `[playwright globalSetup]   ${path} → ${(err as Error).message ?? err}`
      );
    }
  }
  console.log(
    `[playwright globalSetup] done in ${((Date.now() - start) / 1000).toFixed(1)}s`
  );
}
