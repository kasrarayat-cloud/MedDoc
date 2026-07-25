// ============================================================================
// Side-effect boot for the keyterm-regression run — FAIL-CLOSED target select.
// ----------------------------------------------------------------------------
// WHAT THIS USED TO DO, and why it was dangerous:
//
//   import { config } from 'dotenv';
//   config({ path: '/opt/meddoc-pro/.env' });
//
// It hard-loaded the PRODUCTION env so @meddoc/db's Prisma client would stop
// emitting SCRAM errors on telemetry writes. The side effect was that every
// AiCall / ApiUsageEvent the run produced was written to the PRODUCTION
// database. Prod Postgres logs show 199 FK-violating INSERTs from these runs
// plus a synthetic practice row (`iov_smoke_practice`) that was actually
// created and later failed to delete — the FK constraint is the only thing
// that stopped the rest. Same class of defect as the QA walker fleet
// defaulting to the prod app: a convenience default aimed at production.
//
// The rule now matches packages/db/src/db-guard.ts: the target must be
// POSITIVELY a non-prod database, and there is deliberately no force flag.
//
//   1. DATABASE_URL already set  -> use it (an explicit operator choice)
//   2. KEYTERM_ENV_FILE set      -> load that file
//   3. otherwise                 -> ABORT with instructions
//
// In every case assertNonProdDatabase() runs, so a prod URL supplied by either
// route still aborts. Quieting stderr is not worth writing to a clinical
// production database.
// ============================================================================

import { config } from 'dotenv';

import { assertNonProdDatabase } from '@meddoc/db/guard';

const explicitUrl = process.env.DATABASE_URL?.trim();
const envFile = process.env.KEYTERM_ENV_FILE?.trim();

if (!explicitUrl) {
  if (envFile) {
    config({ path: envFile });
  } else {
    throw new Error(
      [
        'keyterm-regression: refusing to run without an explicit database target.',
        '',
        'This script writes telemetry (AiCall / ApiUsageEvent) through @meddoc/db.',
        'It used to default to /opt/meddoc-pro/.env — the PRODUCTION database —',
        'which put synthetic rows into prod. That default is gone.',
        '',
        'Choose a target explicitly, e.g. the isolated QA stack:',
        '  DATABASE_URL="postgresql://meddoc:qa_test_pw@127.0.0.1:5432/meddoc_qa_test?schema=public" \\',
        '    npx tsx scripts/keyterm-regression/run.ts',
        '',
        'or point at an env file:',
        '  KEYTERM_ENV_FILE=/path/to/.env.qa npx tsx scripts/keyterm-regression/run.ts',
        '',
        'The database name must carry a qa/test/e2e/ci marker — see',
        'packages/db/src/db-guard.ts. There is intentionally no force flag.',
      ].join('\n')
    );
  }
}

// Runs for BOTH routes above: an explicit DATABASE_URL pointing at prod aborts
// exactly like a prod-pointing env file would.
assertNonProdDatabase();
