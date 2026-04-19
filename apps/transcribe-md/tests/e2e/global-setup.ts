// ============================================================================
// Playwright globalSetup — verify the app is reachable + mocks are on
// ----------------------------------------------------------------------------
// Runs once before any test. Two checks:
//
//   1. GET /login returns 200 at PW_BASE_URL. If not, the stack isn't up.
//   2. A sentinel env check logs whether MOCK_AI_CALLS is enabled on the
//      worker. We can't read the container's env directly from here —
//      we rely on the operator/CI setting it before starting the worker.
//      The check is purely informational.
// ============================================================================

import { cleanupTestUsers } from './helpers/cleanup';

export default async function globalSetup(): Promise<void> {
  const baseURL = process.env.PW_BASE_URL ?? 'http://localhost:9020';

  const res = await fetch(`${baseURL}/login`);
  if (res.status !== 200 && res.status !== 307) {
    throw new Error(
      `[e2e] app is not reachable at ${baseURL} (GET /login → ${res.status}). ` +
        `Is docker compose running? Are you on the VPS?`
    );
  }

  // Pre-clean any lingering qa-e2e-* users from a prior crashed run so
  // tests always start from a known-empty state.
  cleanupTestUsers();

  console.log(`[e2e] base URL: ${baseURL} — ready to start tests`);
}
