// ============================================================================
// E2E cleanup — delete test users + their cascaded data by email prefix
// ----------------------------------------------------------------------------
// Called by globalTeardown and by each test's afterEach so a failed run
// doesn't leave orphaned qa-e2e-* users behind.
//
// Uses `docker compose exec postgres psql` instead of the Prisma client:
//   - Avoids loading /opt/meddoc-pro/.env from the Playwright process.
//   - No dependency on @meddoc/db compiling cleanly.
//   - Same database connection the live app uses; no risk of drift.
//
// Deletion order respects the FKs documented in packages/db/prisma/schema.prisma:
//   visit_deliveries → transcribe_visits → user_sessions + ai_calls →
//   users → practices (only the synthetic Solo- ones a test created).
// ============================================================================

import { execSync } from 'node:child_process';

import { TEST_EMAIL_PREFIX } from './test-utils';

const COMPOSE = 'docker compose -f /opt/meddoc-pro/docker-compose.yml';

function psql(sql: string): void {
  // -A -t trims psql formatting so stderr output is actually diagnostic
  // when something goes wrong. Each call uses its own connection; the
  // volume is small enough that it doesn't matter.
  execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d meddoc -A -t -c "${sql.replace(/"/g, '\\"')}"`, {
    stdio: ['ignore', 'pipe', 'inherit'],
  });
}

/** Wipe every qa-e2e-* user and their cascaded state. Idempotent —
 *  safe to call before or after a test that hasn't actually seeded
 *  anything. Logs how many users were deleted so the test output
 *  shows whether cleanup is actually running. */
export function cleanupTestUsers(): void {
  const sql = `
    WITH target AS (
      SELECT id, "practiceId"
      FROM users
      WHERE email LIKE '${TEST_EMAIL_PREFIX}%'
    ),
    target_visits AS (
      SELECT id FROM transcribe_visits WHERE "userId" IN (SELECT id FROM target)
    ),
    deleted_deliveries AS (
      DELETE FROM visit_deliveries WHERE "visitId" IN (SELECT id FROM target_visits)
      RETURNING 1
    ),
    deleted_aicalls AS (
      DELETE FROM ai_calls WHERE "practiceId" IN (SELECT "practiceId" FROM target)
      RETURNING 1
    ),
    deleted_visits AS (
      DELETE FROM transcribe_visits WHERE id IN (SELECT id FROM target_visits)
      RETURNING 1
    ),
    deleted_sessions AS (
      DELETE FROM user_sessions WHERE "userId" IN (SELECT id FROM target)
      RETURNING 1
    ),
    deleted_users AS (
      DELETE FROM users WHERE id IN (SELECT id FROM target)
      RETURNING "practiceId"
    ),
    deleted_practices AS (
      DELETE FROM practices
      WHERE id IN (SELECT "practiceId" FROM deleted_users)
        AND name LIKE 'Solo — %'
      RETURNING 1
    )
    SELECT COUNT(*) FROM deleted_users;
  `;
  try {
    psql(sql);
  } catch (err) {
    // Don't fail the whole suite if cleanup hits a transient DB
    // snag — the next run will retry.
    console.error('[e2e cleanup] failed (non-fatal):', (err as Error).message);
  }
}
