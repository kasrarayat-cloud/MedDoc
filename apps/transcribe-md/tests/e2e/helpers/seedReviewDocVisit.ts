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
    {
      lineNumber: 1,
      drug: 'Ibuprofen',
      strength: '400 mg',
      form: 'tablet',
      sig: '400 mg PO TID PRN',
      quantity: '30',
      refills: '0',
      action: 'continue',
    },
  ],
  // THE SHAPE LAYER 7c ACTUALLY PERSISTS — `{severity, rx_drug, message,
  // evidence_quote}`, with identity POSITIONAL (warningIdForIndex). Inventing
  // fields here produced a warning that rendered "undefined" and an override
  // the server would not record: a seed that does not match production is a
  // test of the seed.
  warnings: [
    {
      severity: 'critical',
      rx_drug: 'Ibuprofen',
      message: 'NSAID with heart failure — may worsen fluid retention; prefer acetaminophen.',
      evidence_quote: null,
    },
  ],
};

/** parseEmPendingChange is STRICT and fails closed: `{from,to}` alone is
 *  malformed and coerces to null, which renders "unknown" and tests nothing.
 *  `cause` and `at` are required. */
const EM_PENDING = {
  from: '99213',
  to: '99214',
  cause: 'suggestion_adopted',
  at: new Date().toISOString(),
};

/** Codes, so the collapsed CODES · BILLING row exists at all — with none, the
 *  product correctly renders no row and there is nothing to expand. */
const ICD = [
  { code: 'J45.909', description: 'Unspecified asthma, uncomplicated' },
  { code: 'I10', description: 'Essential (primary) hypertension' },
];
/** THE DISPLAYED LEVEL MUST BE DETERMINISTIC, or a test cannot assert it.
 *
 *  The level a doctor sees is `override?.code ?? engineProjection` — and the
 *  engine projection is computed from the note at render time, so with no
 *  override the fixture's level is whatever the rubric makes of the seeded
 *  prose. A spec then has to READ the level and adapt to it, which is how the
 *  adjust test came to pass whether or not the row agreed with the confirm card
 *  it had just cleared.
 *
 *  Seeding an override pins it at 99214 and makes the fixture coherent with
 *  EM_PENDING (99213 → 99214): the level moved to 99214 and awaits confirming,
 *  which is exactly the state the pending record describes. */
const CPT = {
  em: {
    code: '99213',
    description: 'Office visit, established patient, low complexity',
    reasoning: { problems: [{ description: 'Asthma', status: 'stable' }] },
    override: {
      code: '99214',
      reason: 'Seeded doctor-set level so the displayed code is deterministic.',
      overriddenAt: new Date().toISOString(),
    },
  },
};

/** The level the fixture displays — exported so specs assert against the seed
 *  rather than against whatever the page happened to render. */
export const SEEDED_EM_LEVEL = '99214';

export interface SeededReviewDocVisit {
  visitId: string;
  claimCount: number;
}

/** Seed the visit. Returns null when the psql channel is unavailable, so the
 *  spec can skip cleanly rather than fail for an environment reason. */
export function seedReviewDocVisit(
  email: string,
  /** `emStale: true` seeds the note-changed state, so a spec that needs the
   *  "Re-check level" control can REQUIRE it instead of skipping when it is
   *  absent — a conditional assertion is a test that reports success for having
   *  found nothing to check.
   *
   *  `emPending: false` omits the unacknowledged level change. Needed WITH
   *  emStale, because the stale gate renders only `emStale && !emPendingChange`
   *  — with both seeded the pending card takes the slot and folds the staleness
   *  into its own badge, so the "Re-check level" button never appears. Stale and
   *  not-yet-moved is also the truthful state for a note edited since scoring. */
  opts: { emStale?: boolean; emPending?: boolean } = {},
): SeededReviewDocVisit | null {
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
          "icdCodes", "cptCodes", "emStale",
          "createdAt", "updatedAt")
       values
         ('${visitId}', '${userId}', '${patientId}', 'primary-care', 'text_notes', 'READY',
          'Asthma review. Continue current medications.',
          '${NOTE.replace(/'/g, "''")}', 1,
          '${j(CLAIMS)}'::jsonb, '${j(RX)}'::jsonb,
          ${opts.emPending === false ? 'null' : `'${j(EM_PENDING)}'::jsonb`},
          '${j(ICD)}'::jsonb, '${j(CPT)}'::jsonb, ${opts.emStale ? 'true' : 'false'},
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
