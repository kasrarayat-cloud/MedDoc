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

import { assertNonProdDbName } from '@meddoc/db/guard';

import { TEST_EMAIL_PREFIX } from './test-utils';
import { QA_COMPOSE as COMPOSE, QA_DB as CLEANUP_DB } from './qa-compose';

// Safe-by-default: target the ISOLATED meddoc-qa stack, NOT prod (resolution +
// the fail-closed db-guard live in ./qa-compose). The previous hardwired
// /opt/meddoc-pro path made this a silent no-op on the CI runner.

function psql(sql: string): void {
  // FAIL-CLOSED: never run a DELETE against a prod (or unconfirmable) DB.
  assertNonProdDbName(CLEANUP_DB);
  // -A -t trims psql formatting so stderr output is actually diagnostic
  // when something goes wrong. Each call uses its own connection; the
  // volume is small enough that it doesn't matter.
  execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${CLEANUP_DB} -A -t -c "${sql.replace(/"/g, '\\"')}"`, {
    stdio: ['ignore', 'pipe', 'inherit'],
  });
}

/** Wipe every qa-e2e-* user and their cascaded state. Idempotent —
 *  safe to call before or after a test that hasn't actually seeded
 *  anything. Logs how many users were deleted so the test output
 *  shows whether cleanup is actually running. */
export function cleanupTestUsers(): void {
  // audit_logs.practiceId has an IMMEDIATE FK to practices, so the practices
  // DELETE in the cascade below cannot proceed while audit rows reference the
  // practice — and a single multi-CTE statement can't fix that (data-modifying
  // CTE order is undefined and each CTE sees the statement-start snapshot, so
  // the practices DELETE still sees the un-deleted audit rows → the whole
  // statement rolls back). The page surfaces (VIEWED_PATIENT_LIST / _FILE /
  // VISIT_LIST) write these rows, so Phase 2's patient/visit specs trip it.
  // Delete the test practices' audit rows FIRST, in their own guarded
  // statement (test data only — the db-guard still forbids prod).
  const auditSql = `
    DELETE FROM audit_logs
    WHERE "practiceId" IN (
      SELECT "practiceId" FROM users WHERE email LIKE '${TEST_EMAIL_PREFIX}%'
    );
  `;
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
    psql(auditSql);
    psql(sql);
  } catch (err) {
    // Don't fail the whole suite if cleanup hits a transient DB
    // snag — the next run will retry.
    console.error('[e2e cleanup] failed (non-fatal):', (err as Error).message);
  }
}
