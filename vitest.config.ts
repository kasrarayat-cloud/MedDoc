import { defineConfig } from 'vitest/config';

// ============================================================================
// Vitest config
// ----------------------------------------------------------------------------
// Adversarial unit suite for backend tenant isolation. Tests hit the real
// data layer against the DATABASE_URL Postgres, construct synthetic Session
// objects for each persona, and verify that forged cross-tenant IDs return
// null / empty / throw.
//
// Test files live under `tests/unit/` so Playwright's `*.spec.ts` matcher
// in tests/e2e/ doesn't collide. `dotenv/config` loads .env so DATABASE_URL
// is populated without wrapper scripts.
// ============================================================================

export default defineConfig({
  resolve: { tsconfigPaths: true },
  test: {
    include: ['tests/unit/**/*.test.ts'],
    environment: 'node',
    setupFiles: ['dotenv/config'],
    // Run serially — tests mutate real rows and depend on the seed state.
    // Ownership-check assertions that a parallel run could race on.
    fileParallelism: false,
    pool: 'forks',
    maxWorkers: 1,
    testTimeout: 15000,
  },
});
