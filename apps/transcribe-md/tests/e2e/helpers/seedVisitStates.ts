// ============================================================================
// seedVisitStates — write three TranscribeVisit rows in distinct lifecycle
// states (READY / SIGNED / PROCESSING) so the a11y spec can hit
// /visits/[id] in each state without driving the full pipeline.
// ----------------------------------------------------------------------------
// Why direct SQL: the worker pipeline (with MOCK_AI_CALLS=true) takes
// 1-3s per visit even on mocks; multiplying by three lifecycle states
// across two viewports times every test would dominate the suite. The
// merge-prep runner at /tmp/mp/runner.mjs proved this seeding pattern
// against the production DB; this is the same SQL, ported into the
// e2e helper layer.
//
// Why same channel as cleanup.ts: keeps a single deps surface (docker
// compose exec postgres psql), and the rows we write get picked up by
// the existing prefix-scoped DELETE cascade in cleanupTestUsers().
// No extra teardown plumbing needed.
//
// CI note: The a11y workflow runs Postgres as a sidecar service, NOT
// behind docker compose. When PSQL_BIN is set (the workflow exports it
// to a direct `psql` invocation), seeding switches to that. Otherwise
// it falls back to `docker compose exec postgres psql` for local dev
// against the live VPS.
// ============================================================================

import { execSync } from 'node:child_process';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as SEED_DB } from './qa-compose';

// Safe-by-default: the compose path targets the ISOLATED meddoc-qa stack +
// `meddoc_qa_test`, NOT prod — same F1/F4 posture as cleanup.ts (was hardwired
// to docker-compose.yml / db `meddoc`, so the E2E gate couldn't seed and
// mobile-tap-targets' visit-detail-ready route always skipped). Resolution +
// the fail-closed db-guard live in ./qa-compose.

/** PSQL_BIN, when set by CI, is a full prefix like
 *  `psql "postgresql://meddoc:meddoc@localhost:5432/meddoc_qa_test"`. The a11y workflow
 *  sets this so the spec doesn't need a docker daemon — a trusted CI channel
 *  pointed at that workflow's own marker-named throwaway Postgres sidecar,
 *  so it bypasses the compose path + the qa-stack db-guard. */
function psql(sql: string): string {
  const psqlBin = process.env.PSQL_BIN;
  if (psqlBin) {
    return execSync(`${psqlBin} -A -t -c "${sql.replace(/"/g, '\\"')}"`, {
      encoding: 'utf8',
    }).trim();
  }
  // Compose path → the isolated qa stack. FAIL-CLOSED: never seed a prod DB.
  assertNonProdDbName(SEED_DB);
  return execSync(
    `${COMPOSE} exec -T postgres psql -U meddoc -d ${SEED_DB} -A -t -c "${sql.replace(/"/g, '\\"')}"`,
    { encoding: 'utf8' },
  ).trim();
}

export interface SeededVisitIds {
  READY: string;
  SIGNED: string;
  PROCESSING: string;
}

/** Look up the seeded user (by email), seed a Patient + three Visits in
 *  READY / SIGNED / PROCESSING states, return the visit IDs.
 *
 *  The schema lookup mirrors /tmp/mp/runner.mjs: snake_case table names,
 *  camelCase quoted column names. Cuid-shaped IDs are picked
 *  deterministically per timestamp suffix so reruns are debuggable.
 *
 *  Returns null if the channel isn't available (e.g., docker isn't
 *  running locally and PSQL_BIN isn't set). The caller should
 *  test.skip the SIGNED + PROCESSING tests in that case. */
export function seedVisitStates(email: string): SeededVisitIds | null {
  let userId: string;
  try {
    userId = psql(`SELECT id FROM users WHERE email = '${email}' LIMIT 1;`);
  } catch (err) {
    console.error('[seedVisitStates] psql channel unavailable:', (err as Error).message);
    return null;
  }
  if (!userId) {
    throw new Error(`[seedVisitStates] could not find seeded user ${email}`);
  }
  const practiceId = psql(
    `SELECT "practiceId" FROM users WHERE id = '${userId}' LIMIT 1;`
  );
  if (!practiceId) {
    throw new Error(`[seedVisitStates] no practiceId on user ${userId}`);
  }

  // Use a per-call timestamp suffix so parallel CI runs don't collide
  // on the cuid-shaped primary key.
  const stamp = Date.now().toString(36);
  const patientId = `cmkmpa11y${stamp}`;

  psql(`
    INSERT INTO transcribe_md_patients
      (id, "practiceId", name, "createdAt", "updatedAt")
    VALUES
      ('${patientId}', '${practiceId}', 'A11y Test Patient', NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;
  `);

  const ids: SeededVisitIds = {
    READY: `cmvra11y${stamp}`,
    SIGNED: `cmvsa11y${stamp}`,
    PROCESSING: `cmvpa11y${stamp}`,
  };

  // READY visit — has soapFinal but isn't yet signed. Visit-detail view
  // renders the editable SOAP, "Sign & Send" CTA, and the export bar.
  psql(`
    INSERT INTO transcribe_visits
      (id, "userId", "patientId", "patientName", specialty, "inputMode", status,
       "transcriptText", "soapFinal", "createdAt", "updatedAt")
    VALUES
      ('${ids.READY}', '${userId}', '${patientId}', 'A11y Test Patient',
       'Family Medicine', 'audio_upload', 'READY',
       'Synthetic transcript for accessibility QA.',
       E'## Subjective\\nPatient seen for routine follow-up.\\n\\n## Objective\\nVitals stable.\\n\\n## Assessment\\nWell.\\n\\n## Plan\\nReturn in 6 months.',
       NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;
  `);

  // SIGNED visit — soapFinal + signedSoap + signedAt. Visit-detail view
  // renders the read-only signed SOAP and the "delivered" status banner.
  psql(`
    INSERT INTO transcribe_visits
      (id, "userId", "patientId", "patientName", specialty, "inputMode", status,
       "transcriptText", "soapFinal", "signedSoap", "signedAt", "createdAt", "updatedAt")
    VALUES
      ('${ids.SIGNED}', '${userId}', '${patientId}', 'A11y Test Patient',
       'Family Medicine', 'audio_upload', 'READY',
       'Synthetic transcript (signed).',
       E'## Subjective\\nPost-op week 2 follow-up.\\n\\n## Plan\\nDischarge.',
       E'## Subjective\\nPost-op week 2 follow-up.\\n\\n## Plan\\nDischarge.',
       NOW(), NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;
  `);

  // PROCESSING visit — status mid-pipeline (TRANSCRIBING). Visit-detail
  // view renders the progress UI / pending state with no SOAP yet.
  psql(`
    INSERT INTO transcribe_visits
      (id, "userId", "patientId", "patientName", specialty, "inputMode", status,
       "createdAt", "updatedAt")
    VALUES
      ('${ids.PROCESSING}', '${userId}', '${patientId}', 'A11y Test Patient',
       'Family Medicine', 'audio_upload', 'TRANSCRIBING',
       NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;
  `);

  return ids;
}
