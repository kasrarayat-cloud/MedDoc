// ============================================================================
// Password-reset token capture (Phase 2 Batch 2).
// ----------------------------------------------------------------------------
// The reset token is stored SHA-256-hashed (auth-tokens.ts) — never in the DB
// as plaintext — so it can't be queried out. But the qa stack leaves
// RESEND_API_KEY unset, which flips the forgot-password route into its
// dev-escape-hatch: instead of emailing, it logs
//   "[auth:forgot-password] … dev-only link: <APP_URL>/reset-password?token=XXX"
// to the app container's stdout. We read that back from the container logs.
//
// This is the same out-of-band-channel pattern as cleanup.ts / seedVisitStates
// (shell out to the qa stack's docker compose), so it works locally and in CI.
// ============================================================================

import { execSync } from 'node:child_process';

import { QA_COMPOSE } from './qa-compose';

/** Read the most recent dev-only reset link from the qa app logs and return
 *  its token. Runs serially (workers=1) so the latest link is the current
 *  test's. Throws if no link is found (e.g. RESEND_API_KEY was set). */
export function captureResetToken(): string {
  const logs = execSync(
    `${QA_COMPOSE} logs --no-color --tail=400 transcribe-md`,
    { encoding: 'utf8', maxBuffer: 20 * 1024 * 1024 },
  );
  const matches = [...logs.matchAll(/dev-only link:\s*\S*?token=([A-Za-z0-9._~-]+)/g)];
  const last = matches.at(-1);
  if (!last) {
    throw new Error(
      '[captureResetToken] no dev-only reset link in app logs — is RESEND_API_KEY set on the qa stack?',
    );
  }
  return decodeURIComponent(last[1]);
}
