// ============================================================================
// Seed ONE purpose-built READY visit for the pre-sign document surface.
// ----------------------------------------------------------------------------
// The surface's interesting states all depend on data the generic
// seedVisitStates helper does not produce: verifier-demoted claims, a critical
// Rx interaction, and an unacknowledged E/M level change. Each drives a control
// that now carries sign-path weight, so each has to be deterministic rather
// than "whatever the seed happened to contain".
//
// Same psql channel and the same fail-closed db-guard as seedVisitStates —
// PSQL_BIN in CI, the isolated meddoc-qa stack locally, never a prod database.
// ============================================================================

import { execSync } from 'node:child_process';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as SEED_DB } from './qa-compose';

function psql(sql: string): string {
  const psqlBin = process.env.PSQL_BIN;
  if (psqlBin) {
    return execSync(`${psqlBin} -A -t -c "${sql.replace(/"/g, '\\"')}"`, {
      encoding: 'utf8',
    }).trim();
  }
  assertNonProdDbName(SEED_DB);
  return execSync(
    `${COMPOSE} exec -T postgres psql -U meddoc -d ${SEED_DB} -A -t -c "${sql.replace(/"/g, '\\"')}"`,
    { encoding: 'utf8' },
  ).trim();
}

const NOTE = [
  '## Subjective',
  'Chief Complaint: Asthma review',
  'HPI: Established patient, symptoms several weeks, moderate severity.',
  '',
  '## Objective',
  'Vital Signs: BP 138/86, HR 74, RR 14.',
  '',
  '## Assessment',
  '1. Asthma — stable.',
  '',
  '## Plan',
  '1. Continue current medications.',
].join('\n');

/** Three claims, one per section, so placement is checkable per section. The
 *  third is deliberately LONG — a card taller than a phone viewport is the case
 *  an intersectionRatio-based read-gate can never satisfy, and it shipped
 *  broken once. */
const CLAIMS = [
  { text: 'Patient reports nocturnal cough 2-3 nights per week.', reason: 'not_entailed', section: 'Subjective', anchor: 'no anchor' },
  { text: 'Peak flow 380 L/min in office.', reason: 'digits_unsupported', section: 'Objective', anchor: 'no anchor' },
  {
    text:
      'Add inhaled corticosteroid for step-up therapy. ' +
      'Counselled on inhaler technique, spacer use, and the difference between reliever and preventer inhalers. ' +
      'Discussed trigger avoidance including dust, cold air and exercise, and agreed a written action plan. ' +
      'Advised to return sooner if reliever use exceeds three times weekly or night waking increases. ' +
      'Reviewed adherence, discussed side effects including oral candidiasis and the value of rinsing after use.',
    reason: 'not_entailed',
    section: 'Plan',
    anchor: 'no anchor',
  },
];

/** One CRITICAL interaction — the sign-blocking class. Shape mirrors what L7c
 *  writes, because rx-warnings.ts derives the warning identity from it and the
 *  sign route validates against that same identity. */
const RX = {
  prescriptions: [
    { lineNumber: 1, drug: 'Ibuprofen', strength: '400 mg', form: 'tablet', sig: '400 mg PO TID PRN', quantity: '30', refills: '0', action: 'continue' },
  ],
  warnings: [
    {
      severity: 'critical',
      rxLineNumber: 1,
      headline: 'NSAID with heart failure — may worsen fluid retention',
      detail: 'Prefer acetaminophen in a patient with CHF.',
    },
  ],
};

export interface SeededReviewDocVisit {
  visitId: string;
  claimCount: number;
}

/** Seed the visit. Returns null when the psql channel is unavailable, so the
 *  spec can skip cleanly rather than fail for an environment reason. */
export function seedReviewDocVisit(email: string): SeededReviewDocVisit | null {
  let userId: string;
  let practiceId: string;
  try {
    const row = psql(
      `select id || '|' || "practiceId" from users where email = '${email}' limit 1`,
    );
    if (!row) return null;
    [userId, practiceId] = row.split('|');
  } catch {
    return null;
  }

  const stamp = Date.now().toString(36);
  const visitId = `rdoc_${stamp}`.padEnd(25, '0').slice(0, 25);
  const patientId = `rdocp_${stamp}`.padEnd(25, '0').slice(0, 25);
  const j = (v: unknown) => JSON.stringify(v).replace(/'/g, "''");

  try {
    psql(
      `insert into transcribe_md_patients (id, "practiceId", name, "createdAt", "updatedAt")
       values ('${patientId}', '${practiceId}', 'E2E Review Doc', now(), now())
       on conflict (id) do nothing`,
    );
    psql(
      `insert into transcribe_visits
         (id, "userId", "patientId", specialty, "inputMode", status,
          "transcriptText", "soapFinal", "soapVersion",
          "suggestedClaims", "rxDrafts", "emPendingChange",
          "createdAt", "updatedAt")
       values
         ('${visitId}', '${userId}', '${patientId}', 'primary-care', 'text_notes', 'READY',
          'Asthma review. Continue current medications.',
          '${NOTE.replace(/'/g, "''")}', 1,
          '${j(CLAIMS)}'::jsonb, '${j(RX)}'::jsonb,
          '${j({ from: '99213', to: '99214' })}'::jsonb,
          now(), now())
       on conflict (id) do nothing`,
    );
  } catch {
    return null;
  }
  return { visitId, claimCount: CLAIMS.length };
}

export function cleanupReviewDocVisit(visitId: string): void {
  try {
    psql(`delete from transcribe_visits where id = '${visitId}'`);
    psql(`delete from transcribe_md_patients where name = 'E2E Review Doc'`);
  } catch {
    /* best effort — the suite's own cleanup sweeps the user anyway */
  }
}
