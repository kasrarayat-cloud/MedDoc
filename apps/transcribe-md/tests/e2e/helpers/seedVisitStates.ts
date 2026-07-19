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
import { createHash } from 'node:crypto';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { canonicalSoapSha256 } from '../../../src/lib/template-twin/soap-binding';
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

const AUTOMATION_LAYERS = [
  ['icd_coding', 'l7a-v1'],
  ['cpt_coding', 'l7b-v1'],
  ['rx_drafting', 'l7c-v1'],
  ['referrals', 'l7d-v1'],
  ['patient_summary', 'l7e-v1'],
  ['em_mdm_prewarm', 'em-mdm-prewarm-v1'],
] as const;

function sha256(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

function sqlLiteral(value: string | null): string {
  return value === null ? 'NULL' : `'${value.replaceAll("'", "''")}'`;
}

/**
 * Seed a terminal visit through the production database invariant:
 * AUTOMATING first, then an exact six-layer proof and its audit outbox event,
 * then the terminal transition. Provider automation is deliberately absent
 * from this synthetic accessibility fixture, so every layer is explicit N/A.
 */
function seedTerminalVisit(input: {
  visitId: string;
  userId: string;
  practiceId: string;
  patientId: string;
  transcript: string;
  soapFinal: string;
  finalStatus: 'READY' | 'SIGNED';
}): void {
  const manifestId = `${input.visitId}-automation`;
  const soapSha256 = canonicalSoapSha256(input.soapFinal);
  const sourceSha256 = sha256(`synthetic-a11y-source:${input.visitId}`);
  const layerRows = AUTOMATION_LAYERS.map(([layerId, layerVersion], index) => {
    const inputSha256 = sha256(`${manifestId}:${layerId}:input`);
    const idempotencyKey = sha256(`${manifestId}:${layerId}:idempotency`);
    return `(
      '${manifestId}-layer-${index + 1}', '${manifestId}', '${input.practiceId}',
      '${input.visitId}', '${layerId}', '${layerVersion}', 'NOT_APPLICABLE',
      'NOT_APPLICABLE', 0, '${inputSha256}', NULL, NULL,
      '${idempotencyKey}', NULL, NOW(), NOW(), NOW()
    )`;
  }).join(',');
  const signedSoap =
    input.finalStatus === 'SIGNED' ? sqlLiteral(input.soapFinal) : 'NULL';
  const signedAt = input.finalStatus === 'SIGNED' ? 'NOW()' : 'NULL';
  const eventKey = `synthetic-a11y-automation:${sha256(input.visitId)}`;

  psql(`
    BEGIN;

    INSERT INTO transcribe_visits
      (id, "userId", "patientId", "patientName", specialty, "inputMode", status,
       "transcriptText", "soapFinal", "signedSoap", "signedAt",
       "createdAt", "updatedAt")
    VALUES
      ('${input.visitId}', '${input.userId}', '${input.patientId}',
       'A11y Test Patient', 'Family Medicine', 'audio_upload', 'AUTOMATING',
       ${sqlLiteral(input.transcript)}, ${sqlLiteral(input.soapFinal)},
       ${signedSoap}, ${signedAt}, NOW(), NOW())
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO visit_automation_manifests
      (id, "practiceId", "visitId", "soapVersion", "soapSha256",
       "sourceVersion", "sourceSha256", "policyVersion", "manifestVersion",
       status, "attemptCount", "startedAt", "createdAt", "updatedAt")
    VALUES
      ('${manifestId}', '${input.practiceId}', '${input.visitId}', 1,
       '${soapSha256}', 'soap-final-v1', '${sourceSha256}',
       'visit-automation-policy-v1', 1, 'RUNNING', 1, NOW(), NOW(), NOW())
    ON CONFLICT ("visitId") DO NOTHING;

    INSERT INTO visit_automation_layers
      (id, "manifestId", "practiceId", "visitId", "layerId", "layerVersion",
       requirement, status, "attemptCount", "inputSha256", "outputSha256",
       "failureCode", "idempotencyKey", "startedAt", "completedAt",
       "createdAt", "updatedAt")
    VALUES ${layerRows}
    ON CONFLICT ("manifestId", "layerId") DO NOTHING;

    UPDATE visit_automation_manifests
    SET status = 'COMPLETE', "completedAt" = NOW(), "updatedAt" = NOW()
    WHERE id = '${manifestId}' AND status = 'RUNNING';

    INSERT INTO template_twin_audit_outbox
      (id, "practiceId", "actorId", "eventKey", action, "targetId",
       "targetType", metadata, status, "attemptCount", "availableAt",
       "createdAt", "updatedAt")
    VALUES
      ('${manifestId}-audit', '${input.practiceId}', '${input.userId}',
       '${eventKey}', 'VISIT_AUTOMATION_COMPLETED', '${input.visitId}',
       'TranscribeVisit',
       '{"proofVersion":"visit-automation-proof-v1","syntheticFixture":true}'::jsonb,
       'PENDING', 0, NOW(), NOW(), NOW())
    ON CONFLICT ("eventKey") DO NOTHING;

    UPDATE transcribe_visits
    SET status = '${input.finalStatus}', "updatedAt" = NOW()
    WHERE id = '${input.visitId}' AND status = 'AUTOMATING';

    COMMIT;
  `);
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
  seedTerminalVisit({
    visitId: ids.READY,
    userId,
    practiceId,
    patientId,
    transcript: 'Synthetic transcript for accessibility QA.',
    soapFinal:
      '## Subjective\nPatient seen for routine follow-up.\n\n## Objective\nVitals stable.\n\n## Assessment\nWell.\n\n## Plan\nReturn in 6 months.',
    finalStatus: 'READY',
  });

  // SIGNED visit — soapFinal + signedSoap + signedAt. Visit-detail view
  // renders the read-only signed SOAP and the "delivered" status banner.
  seedTerminalVisit({
    visitId: ids.SIGNED,
    userId,
    practiceId,
    patientId,
    transcript: 'Synthetic transcript for signed accessibility QA.',
    soapFinal:
      '## Subjective\nSynthetic follow-up.\n\n## Plan\nSynthetic discharge.',
    finalStatus: 'SIGNED',
  });

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
