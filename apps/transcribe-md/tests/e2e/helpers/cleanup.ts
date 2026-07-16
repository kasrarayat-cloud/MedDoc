// ============================================================================
// E2E cleanup — delete test users + their cascaded data by email prefix
// ----------------------------------------------------------------------------
// Called by globalTeardown and by each test's afterEach so a failed run
// doesn't leave orphaned qa-e2e-* users behind.
//
// Uses the CI `PSQL_BIN` channel or `docker compose exec postgres psql`
// instead of the Prisma client:
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
  const direct = process.env.PSQL_BIN;
  if (direct) {
    const database = execSync(
      `${direct} -v ON_ERROR_STOP=1 -A -t -c "SELECT current_database();"`,
      {
        encoding: 'utf8',
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    ).trim();
    assertNonProdDbName(database);
    execSync(`${direct} -v ON_ERROR_STOP=1 -A -t -f -`, {
      input: sql,
      stdio: ['pipe', 'pipe', 'inherit'],
    });
    return;
  }

  // FAIL-CLOSED: never run a DELETE against a prod (or unconfirmable) DB.
  assertNonProdDbName(CLEANUP_DB);
  // Feed SQL over stdin so quoting stays literal. ON_ERROR_STOP makes schema
  // drift or an FK-order regression fail the test instead of returning a
  // misleading successful psql exit code.
  execSync(
    `${COMPOSE} exec -T postgres psql -v ON_ERROR_STOP=1 -U meddoc -d ${CLEANUP_DB} -A -t -f -`,
    {
      input: sql,
      stdio: ['pipe', 'pipe', 'inherit'],
    },
  );
}

/** Wipe every qa-e2e-* user and their cascaded state. Idempotent —
 *  safe to call before or after a test that hasn't actually seeded
 *  anything. Logs how many users were deleted so the test output
 *  shows whether cleanup is actually running. */
export function cleanupTestUsers(): void {
  // Materialize the exact synthetic tenant set, lock its practice/user/visit
  // rows in deterministic order, then delete in FK order inside one
  // transaction. The locks wait for in-flight child inserts and block new FK
  // KEY SHARE writers until cleanup commits.
  const sql = `
    BEGIN;

    CREATE TEMP TABLE e2e_target_users ON COMMIT DROP AS
      SELECT id, "practiceId"
      FROM users
      WHERE email LIKE '${TEST_EMAIL_PREFIX}%';

    CREATE TEMP TABLE e2e_target_practices ON COMMIT DROP AS
      SELECT DISTINCT "practiceId" AS id FROM e2e_target_users;

    SELECT p.id
    FROM practices p
    JOIN e2e_target_practices target ON target.id = p.id
    ORDER BY p.id
    FOR UPDATE OF p;

    SELECT u.id
    FROM users u
    JOIN e2e_target_users target ON target.id = u.id
    ORDER BY u.id
    FOR UPDATE OF u;

    CREATE TEMP TABLE e2e_target_visits ON COMMIT DROP AS
      SELECT id FROM transcribe_visits
      WHERE "userId" IN (SELECT id FROM e2e_target_users);

    SELECT v.id
    FROM transcribe_visits v
    JOIN e2e_target_visits target ON target.id = v.id
    ORDER BY v.id
    FOR UPDATE OF v;

    DELETE FROM audit_logs
    WHERE "practiceId" IN (SELECT id FROM e2e_target_practices);
    DELETE FROM rx_warning_overrides
    WHERE "visitId" IN (SELECT id FROM e2e_target_visits);
    DELETE FROM visit_deliveries
    WHERE "visitId" IN (SELECT id FROM e2e_target_visits);
    DELETE FROM ai_calls
    WHERE "practiceId" IN (SELECT id FROM e2e_target_practices);
    DELETE FROM transcribe_visits
    WHERE id IN (SELECT id FROM e2e_target_visits);
    DELETE FROM user_sessions
    WHERE "userId" IN (SELECT id FROM e2e_target_users);
    DELETE FROM users
    WHERE id IN (SELECT id FROM e2e_target_users);
    DELETE FROM practices
    WHERE id IN (SELECT id FROM e2e_target_practices)
      AND name LIKE 'Solo — %';

    COMMIT;
  `;
  psql(sql);
}
