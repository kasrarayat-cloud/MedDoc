import { defineConfig, devices } from '@playwright/test';

// ============================================================================
// Playwright config
// ----------------------------------------------------------------------------
// Chromium-only. Auto-starts the Next dev server via the `webServer` block
// so `npm run test:e2e` is self-contained — no need to run `npm run dev` in
// another shell. If a server is already running on :3000 we reuse it.
// ============================================================================

export default defineConfig({
  testDir: './tests/e2e',
  // Phase 19 (h13-meddoc-e2e-tenancy-residual): pre-warm Turbopack
  // routes after webServer is ready but before tests start, so the
  // first cross-tenant page.goto() doesn't time out waiting for a
  // cold-compile of /dashboard subtrees.
  globalSetup: './tests/e2e/global-setup.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    // `next dev` picks up .env automatically — no explicit env wiring needed.
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    // Cold Turbopack boot + Prisma engine init can take a beat.
    timeout: 120_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
