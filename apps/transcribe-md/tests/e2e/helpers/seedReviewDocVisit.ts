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

/** R4.1 — the owner's fixture: an imaging visit whose plan orders
 *  anticoagulation without naming an agent. Reproduces BOTH advisory classes
 *  the walkthrough screenshot shows, and both are CORRECT clinical behaviour
 *  that must survive un-softened:
 *    · `unclear` — the agent is not specified, so nothing can be dispensed
 *    · a deterministic not-in-database check on the unnamed agent
 *  The shape matches what layer 7c persists, positional identity included; a
 *  seed that does not match production is a test of the seed. */
const IMAGING_RX = {
  prescriptions: [
    {
      lineNumber: 1,
      drug: 'Anticoagulation',
      strength: null,
      form: null,
      sig: 'Start anticoagulation per vascular service',
      quantity: null,
      refills: null,
      action: 'unclear',
    },
  ],
  warnings: [
    {
      severity: 'info',
      rx_drug: 'Anticoagulation',
      message:
        'Agent not specified — the plan orders anticoagulation without naming a drug, dose or duration.',
      evidence_quote: 'start anticoagulation',
    },
  ],
};

/** parseEmPendingChange is STRICT and fails closed: `{from,to}` alone is
 *  malformed and coerces to null, which renders "unknown" and tests nothing.
 *  `cause` and `at` are required. */
/** A fixed moment for the signature, so the trail's "overridden BEFORE signing"
 *  comparison is deterministic rather than racing wall-clock now(). */
const SIGNED_AT = '2026-07-30T12:00:00.000Z';
/** Strictly earlier — the Rx card only counts rows at or before the signature,
 *  because `recordOverride` guards ownership and not visit status, so a row CAN
 *  postdate a signature and "before signing" has to be checked, not assumed. */
const OVERRIDDEN_AT = '2026-07-30T11:00:00.000Z';

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

// ===========================================================================
// THE IMAGING FIXTURE — added 2026-07-28, and it exists because of a live bug.
// ---------------------------------------------------------------------------
// Every fixture in this file was primary-care. So when `emStale` was finally
// wired through to the view, an edited ULTRASOUND report started drawing
// "Documentation level needs re-checking" with the bar instructing the doctor to
// "Re-check the documentation level above" — pointing at a card that does not
// exist, for a level the same page correctly refuses to show. Nothing in CI
// could see it. It was found by hand, on production.
//
// A specialty-conditional surface needs a fixture per specialty class or the
// condition is only ever exercised in one direction.
//
// This one is a venous duplex on the doctor's OWN template (WM_IOV-class: an
// imaging report's headings, not S/O/A/P), because "custom template" and
// "imaging" are the combination the real bug lived in.
//
// IT CARRIES NO E/M FIELDS AT ALL — no `cptCodes.em`, no `emScoredCode`, no
// pending change. That is not tidiness, it is the invariant: an office E/M code
// on an imaging report is wrong as DATA and reaches the export and the signed
// record. `assertImagingHasNoEm` below enforces it after every seed.
// ===========================================================================

/** An imaging report reads as headings, not SOAP. Mirrors the shape the
 *  WM_IOV-class templates produce. */
/** EXPORTED so a parity test derives its markers from the FIXTURE rather than
 *  from a second hand-written copy of it. A parity assertion whose expected
 *  strings drift from what was actually seeded proves nothing about parity —
 *  it proves the two literals still match. */
export const IMAGING_NOTE_SOURCE = [
  '## EXAM TYPE',
  'Bilateral lower extremity venous duplex ultrasound.',
  '',
  '## INDICATION',
  'Screening for chronic venous insufficiency.',
  '',
  '## TECHNIQUE',
  'Grayscale, color and spectral Doppler imaging, supine and standing.',
  '',
  '## FINDINGS — RIGHT',
  'Common femoral, femoral and popliteal veins patent and compressible.',
  'No superficial reflux.',
  '',
  '## FINDINGS — LEFT',
  'Common femoral, femoral and popliteal veins patent and compressible.',
  'No superficial reflux.',
  '',
  '## IMPRESSION',
  '1. No evidence of deep venous thrombosis.',
  '2. No significant superficial venous reflux.',
  '',
  '## RECOMMENDATION',
  'Conservative management. Follow up as clinically indicated.',
];
const IMAGING_NOTE = IMAGING_NOTE_SOURCE.join('\n');

/** The doctor's own form — imaging headings. */
const IMAGING_TEMPLATE_SECTIONS = [
  { label: 'EXAM TYPE', order: 1 },
  { label: 'INDICATION', order: 2 },
  { label: 'TECHNIQUE', order: 3 },
  { label: 'FINDINGS — RIGHT', order: 4 },
  { label: 'FINDINGS — LEFT', order: 5 },
  { label: 'IMPRESSION', order: 6 },
  { label: 'RECOMMENDATION', order: 7 },
];

/** ICD is legitimate on an imaging report; CPT-E/M is not. Seeded so the
 *  "no billing worksheet" assertions mean something — absence has to be the
 *  product's decision, not an empty column. */
const IMAGING_ICD = [
  { code: 'I87.2', description: 'Venous insufficiency (chronic) (peripheral)' },
];

/** The office-E/M blob an imaging visit must never carry — seeded deliberately by
 *  `imagingEmArtifact` so the export guard has something to suppress. Mirrors the
 *  shape of prod row cms3k19d2001801mkyarrlq57 plus a raw code and a signedCode,
 *  so `override ?? code` and `signedCode ?? …` both have a value to leak. */
const IMAGING_EM_ARTIFACT = {
  em: {
    code: '99213',
    description: 'Office visit, established patient, low complexity',
    reasoning: { problems: [], data: '', risk: '' },
    evidence_quote: '',
    override: { code: '99212', overriddenAt: '2026-07-27T20:48:15.183Z' },
    signedCode: '99214',
  },
};

/** The specialty classes the review-doc pack runs across. `emApplies` is the
 *  single switch every specialty-conditional expectation reads. */
export const REVIEW_DOC_CLASSES = [
  {
    key: 'primary-care' as const,
    /** How the spec name reads. */
    label: 'an office visit',
    /** E/M applies: level row, Adjust, confirm gate and stale gate all exist. */
    emApplies: true,
    /** ⚠️ `hasRxGate` WAS REMOVED FROM THIS MATRIX — owner ruling #109. The
     *  fixture still carries a critical Rx interaction (extraction was not in
     *  scope); it simply no longer gates anything, so there is no per-specialty
     *  arm left to switch on. */
  },
  {
    key: 'imaging' as const,
    label: 'an imaging report',
    emApplies: false,
  },
] as const;

export type ReviewDocClass = (typeof REVIEW_DOC_CLASSES)[number]['key'];

export interface SeededReviewDocVisit {
  visitId: string;
  claimCount: number;
  /** The class this fixture was seeded as, so a spec cannot drift from it. */
  specialtyClass: ReviewDocClass;
  /** R3 — the patient row this visit hangs off, so a caller can walk
   *  `/patients/[id]`. It was already generated here and simply not returned;
   *  the legacy-island census needs that route and had no way to reach it. */
  patientId: string;
}

/** THE GUARD. Read the row back and refuse to hand a spec an imaging fixture
 *  that carries office-E/M state.
 *
 *  It runs on the seeded row rather than on the INSERT text on purpose: the
 *  residue this exists to stop was not written by a seeder at all. Two fixtures
 *  in the QA database acquired `emScoredCode` / `cptCodes.em` from a page render
 *  made BEFORE the label-vs-id fix, months after their seeder was written — and
 *  then sat there, being read by walks and specs as though it were the truth.
 *
 *  Throws rather than returning null: a missing fixture is an environment
 *  problem and skips, but an imaging visit with a billing level is a wrong
 *  fixture, and a spec that runs against it proves the opposite of what it says.
 */
export function assertImagingHasNoEm(visitId: string): void {
  const row = psql(
    `select coalesce("emScoredCode",'-') || '|' ||
            coalesce("cptCodes"->'em'->>'code','-') || '|' ||
            coalesce("cptCodes"->'em'->>'signedCode','-') || '|' ||
            coalesce("cptCodes"->'em'->'override'->>'code','-') || '|' ||
            case when "emPendingChange" is null then '-' else 'pending' end
       from transcribe_visits where id = '${visitId}'`,
  );
  if (!row) throw new Error(`assertImagingHasNoEm: visit ${visitId} not found`);
  const [scored, code, signedCode, overrideCode, pending] = row.split('|');
  const offenders: string[] = [];
  if (scored !== '-') offenders.push(`emScoredCode=${scored}`);
  if (code !== '-') offenders.push(`cptCodes.em.code=${code}`);
  if (signedCode !== '-') offenders.push(`cptCodes.em.signedCode=${signedCode}`);
  if (overrideCode !== '-') offenders.push(`cptCodes.em.override.code=${overrideCode}`);
  if (pending !== '-') offenders.push('emPendingChange is set');
  if (offenders.length) {
    throw new Error(
      `IMAGING FIXTURE CARRIES OFFICE E/M STATE — ${visitId}: ${offenders.join(', ')}. ` +
        'An imaging report has no office-visit level; this is wrong as data and ' +
        'reaches the export and the signed record. Either the seed regressed or ' +
        'a pre-label-fix page render wrote it back. Do not assert against it.',
    );
  }
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
  opts: {
    emStale?: boolean;
    emPending?: boolean;
    /** Which specialty class to seed. Defaults to the office visit, so every
     *  existing caller keeps the fixture it was written against. */
    specialtyClass?: ReviewDocClass;
    /** SEED AN IMAGING VISIT THAT WRONGLY CARRIES AN OFFICE E/M BLOB, on purpose.
     *
     *  Everything else in this file exists to keep that state OUT of a fixture.
     *  This one puts it in, because the export-layer guard's whole claim is
     *  "an imaging report prints no office level EVEN IF the row holds one", and
     *  a clean row cannot test that claim — it would pass against no guard at all.
     *
     *  Reproduces the real production row: `code` AND `override.code` AND
     *  `signedCode`, so every branch of the projection has something to return.
     *  Skips `assertImagingHasNoEm` (this fixture is the exception it exists to
     *  make impossible everywhere else) — hence the explicit, ugly opt-in name. */
    imagingEmArtifact?: boolean;
    /** DISTINGUISH TWO SEEDS MADE IN THE SAME MILLISECOND.
     *
     *  The ids below are keyed on `Date.now().toString(36)` alone, and the
     *  insert is `on conflict do nothing` — so two seeds inside one millisecond
     *  silently produce ONE visit and the second call returns the first one's
     *  row. A queue spec seeds three and would then assert "1 of 1" against a
     *  fixture it believes is three, with nothing erroring. */
    idSalt?: string;
    /** ⚠️ R4.1 — SEED AN IMAGING VISIT THAT DOES CARRY PRESCRIPTIONS.
     *
     *  The imaging fixture writes `rxDrafts: null` by default, on the sound
     *  reasoning that an ultrasound report usually orders no medication. The
     *  owner's defect was found on exactly the case that reasoning excludes: an
     *  ultrasound whose PLAN orders anticoagulation. No fixture could express
     *  that combination, so no walk could render the panel, and the census
     *  reported the surface clean because it was never on screen.
     *
     *  This is the "surface that only exists after a live pipeline run" class —
     *  now two members, with the processing card. The cure for that class is a
     *  fixture that RENDERS the state, not a route walk. */
    imagingWithRx?: boolean;
    /** The reason line on the Rounds identity header. Not written otherwise. */
    chiefComplaint?: string;
    /** Fields the identity header's MRN / age cells read. Omitted by default so
     *  every existing caller's fixture stays byte-identical. */
    patient?: { dob?: string; externalId?: string };
    /** SEED A SIGNED VISIT — status SIGNED, signedSoap frozen, signedAt set.
     *  Screen 4 exists only for these, and nothing else in the E2E helpers
     *  produces one with the review-doc fixture's Rx/EM shape. */
    signed?: boolean;
    /** Record a REAL critical RxWarningOverride row, timestamped BEFORE the
     *  signature, so the safety trail's Rx card has a persisted fact behind it
     *  rather than an inference from "the visit is signed". */
    withCriticalOverride?: boolean;
    /** Stamp `emPendingChange.acknowledgedAt`, which is what the sign route
     *  itself writes on the winning READY→SIGNED transition. */
    emAcknowledged?: boolean;
    /** SEED AN IMAGING VISIT CARRYING AN UNACKNOWLEDGED OFFICE E/M CHANGE.
     *
     *  Like `imagingEmArtifact`, this deliberately creates the state everything
     *  else exists to prevent — and for the same reason: the anomaly path
     *  CANNOT BE TESTED WITHOUT IT.
     *
     *  `emArtifact` is set only when `emAppliesToSpecialty` is false AND
     *  `emPendingChange` is non-null. Every imaging fixture hard-nulls that
     *  column, so an assertion that the anomaly banner is ABSENT on a normal
     *  imaging visit passes against a build with the anomaly deleted. It proves
     *  nothing. This option is what turns those assertions into real ones.
     *
     *  Reproduces the shape found in production: five imaging visits acquired
     *  office E/M state and sat there two days. Skips `assertImagingHasNoEm`,
     *  hence the explicit opt-in name. */
    imagingEmPending?: boolean;
  } = {},
): SeededReviewDocVisit | null {
  const cls: ReviewDocClass = opts.specialtyClass ?? 'primary-care';
  const imaging = cls === 'imaging';

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

  const stamp = `${Date.now().toString(36)}${opts.idSalt ?? ''}`;
  const visitId = `rdoc_${stamp}`.padEnd(25, '0').slice(0, 25);
  const patientId = `rdocp_${stamp}`.padEnd(25, '0').slice(0, 25);
  const templateId = `rdoct_${stamp}`.padEnd(25, '0').slice(0, 25);
  const j = (v: unknown) => JSON.stringify(v).replace(/'/g, "''");
  const q = (s: string) => s.replace(/'/g, "''");

  try {
    psql(
      `insert into transcribe_md_patients
         (id, "practiceId", name, "dateOfBirth", "externalId", "createdAt", "updatedAt")
       values ('${patientId}', '${practiceId}', 'E2E Review Doc',
               ${opts.patient?.dob ? `'${q(opts.patient.dob)}'::timestamp` : 'null'},
               ${opts.patient?.externalId ? `'${q(opts.patient.externalId)}'` : 'null'},
               now(), now())
       on conflict (id) do nothing`,
    );

    // THE DOCTOR'S OWN FORM, imaging only. "Custom template" and "imaging" is
    // the combination the live bug lived in, so the fixture reproduces both
    // rather than testing imaging on the built-in SOAP structure.
    if (imaging) {
      psql(
        `insert into note_templates
           (id, "doctorId", "practiceId", name, sections, version, status, "isSystemDefault",
            "createdAt", "updatedAt")
         values
           ('${templateId}', '${userId}',
            (select "practiceId" from users where id = '${userId}'),
            'E2E Venous Duplex Report',
            '${j(IMAGING_TEMPLATE_SECTIONS)}'::jsonb, 1, 'active', false,
            now(), now())
         on conflict (id) do nothing`,
      );
    }

    psql(
      // ⚠️ T3 — `practiceId` DERIVED FROM THE PATIENT in SQL. Raw INSERT, so
      // Prisma's types never see it and a required column is invisible here
      // until the database refuses the row. The subselect cannot drift from the
      // patient, which is what the composite FK enforces anyway.
      `insert into transcribe_visits
         (id, "userId", "patientId", "practiceId", "createdBy", "signedBy", specialty, "inputMode", status,
          "signedAt", "signedSoap",
          "chiefComplaint",
          "transcriptText", "soapFinal", "soapVersion",
          "suggestedClaims", "rxDrafts", "emPendingChange",
          "icdCodes", "cptCodes", "emStale",
          "noteTemplateId", "noteTemplateVersion",
          "createdAt", "updatedAt")
       values
         ('${visitId}', '${userId}', '${patientId}',
          (select "practiceId" from transcribe_md_patients where id = '${patientId}'),
          '${userId}',
          -- T4: signedBy tracks signedAt EXACTLY. This seeder's signature is
          -- conditional on opts.signed, so the signer must be too. A signer on
          -- an unsigned visit is a lie; a signature with no signer is refused
          -- by transcribe_visits_signed_requires_signer.
          -- (No backticks here: this text lives inside a JS template literal,
          --  and a backtick would close it. That cost two tsc errors.)
          ${opts.signed ? `'${userId}'` : 'null'},
          '${imaging ? 'ultrasound' : 'primary-care'}', 'text_notes',
          '${opts.signed ? 'SIGNED' : 'READY'}',
          ${opts.signed ? `'${SIGNED_AT}'::timestamptz` : 'null'},
          ${opts.signed ? `'${q(imaging ? IMAGING_NOTE : NOTE)}'` : 'null'},
          ${opts.chiefComplaint ? `'${q(opts.chiefComplaint)}'` : 'null'},
          '${imaging ? 'Bilateral venous duplex, screening study.' : 'Asthma review. Continue current medications.'}',
          '${q(imaging ? IMAGING_NOTE : NOTE)}', 1,
          '${j(CLAIMS)}'::jsonb,
          -- No medications on an imaging report, so no Rx gate. Its ABSENCE is
          -- asserted; the office fixture keeps the critical interaction.
          ${imaging && !opts.imagingWithRx ? 'null' : `'${j(imaging ? IMAGING_RX : RX)}'::jsonb`},
          -- AND NO PENDING E/M CHANGE, ever, on imaging: there is no level to
          -- have moved. Seeding one would be seeding the bug.
          ${
            (imaging && !opts.imagingEmPending) || opts.emPending === false
              ? 'null'
              : `'${j(opts.emAcknowledged ? { ...EM_PENDING, acknowledgedAt: SIGNED_AT } : EM_PENDING)}'::jsonb`
          },
          '${j(imaging ? IMAGING_ICD : ICD)}'::jsonb,
          -- The whole point of the imaging fixture: NO office E/M blob …
          -- …EXCEPT when a spec is testing the export guard, which needs one.
          ${imaging ? (opts.imagingEmArtifact ? `'${j(IMAGING_EM_ARTIFACT)}'::jsonb` : 'null') : `'${j(CPT)}'::jsonb`},
          ${opts.emStale ? 'true' : 'false'},
          ${imaging ? `'${templateId}'` : 'null'}, ${imaging ? '1' : 'null'},
          now(), now())
       on conflict (id) do nothing`,
    );
  } catch {
    return null;
  }

  // Read it back. A seed that says the right thing and wrote the wrong thing is
  // the failure mode this whole fixture exists to answer for.
  // The artifact fixture is the ONE case that must skip this — it seeds the very
  // state the guard rejects, deliberately, to prove the export suppresses it.
    // A REAL override row — the same shape recordOverride writes, with a
    // server-validated-length reason and a timestamp strictly before the
    // signature. Screen 4's Rx card counts THESE; it does not infer from the
    // visit being signed.
    if (opts.withCriticalOverride) {
      psql(
        `insert into rx_warning_overrides
           (id, "visitId", "practiceId", "rxLineNumber", "warningId", severity, headline,
            reason, "overriddenBy", "overriddenAt")
         values
           ('${`ovr_${stamp}`.padEnd(25, '0').slice(0, 25)}', '${visitId}',
            (select "practiceId" from transcribe_visits where id = '${visitId}'),
            1, 'rx-warning-0',
            'critical', 'NSAID with heart failure',
            'Benefit outweighs risk; monitoring renal function weekly and patient counselled.',
            '${userId}', '${OVERRIDDEN_AT}'::timestamptz)
         on conflict do nothing`,
      );
    }

  if (imaging && !opts.imagingEmArtifact && !opts.imagingEmPending)
    assertImagingHasNoEm(visitId);

  return { visitId, patientId, claimCount: CLAIMS.length, specialtyClass: cls };
}

/** THE DATABASE-WIDE NET, for artifacts that arrive from outside any seeder.
 *
 *  `assertImagingHasNoEm` guards the row a spec just seeded. This guards the
 *  ones it did not: two long-lived QA fixtures acquired office-E/M state from a
 *  page render made by a PRE-LABEL-FIX build — `qa_visitdoc_twin.emScoredCode =
 *  99212` and `qa_twin_donor.cptCodes.em.code = 99213`. No seeder wrote either.
 *  They simply sat in the database being read as truth, including by the walker.
 *
 *  Run at pack start. Returns the offenders rather than throwing, so the caller
 *  decides whether a dirty database is a skip or a failure — and reports WHICH
 *  rows, because "some fixture is wrong" is not actionable at 2am. */
export function findImagingEmArtifacts(): string[] {
  try {
    const out = psql(
      `select id || ' -> ' ||
              concat_ws(', ',
                nullif('emScoredCode=' || coalesce("emScoredCode",''), 'emScoredCode='),
                case when "cptCodes" ? 'em' then 'cptCodes.em present' end,
                case when "emPendingChange" is not null then 'emPendingChange set' end)
         from transcribe_visits
        where specialty = 'ultrasound'
          and ("emScoredCode" is not null
               or "cptCodes" ? 'em'
               or "emPendingChange" is not null)`,
    );
    return out ? out.split('\n').map((l) => l.trim()).filter(Boolean) : [];
  } catch {
    // No psql channel — the caller is already skipping for that reason.
    return [];
  }
}

/** One read-only value from the QA database. Exported so a spec can assert the
 *  fixture is in the state it claims to be — an "artifact suppressed" test proves
 *  nothing unless the artifact was demonstrably there. */
/**
 * How many prescriptions the seeded visit's `rxDrafts` actually carries.
 *
 * ⚠️ EXISTS AS A NON-VACUITY CONTROL, not as a feature check. Owner ruling #109
 * deleted the prescription-safety SURFACE and deliberately kept extraction, so
 * the R5 stage test asserts a page full of ABSENCES — and a fixture that
 * quietly stopped writing `rxDrafts` would satisfy every one of them while
 * proving nothing. This is the assertion that the state under test exists.
 */
export function seededRxDraftCount(visitId: string): number {
  const out = psql(
    `select coalesce(jsonb_array_length("rxDrafts"->'prescriptions'), 0) ` +
      `from transcribe_visits where id = '${visitId}'`,
  );
  return Number.parseInt(out, 10) || 0;
}

/** The raw `rxDrafts` json, for asserting the EXTRACTED content survives the
 *  surface's deletion (ruling #109 kept the data). */
export function seededRxDraftJson(visitId: string): string {
  return psql(`select coalesce("rxDrafts"::text, '') from transcribe_visits where id = '${visitId}'`);
}

export function psqlOne(sql: string): string {
  return psql(sql);
}

export function cleanupReviewDocVisit(visitId: string): void {
  try {
    psql(`delete from transcribe_visits where id = '${visitId}'`);
    psql(`delete from transcribe_md_patients where name = 'E2E Review Doc'`);
    // The imaging fixture owns a template row. Left behind it would accumulate
    // one per run and, worse, become an ACTIVE custom format on the seeded
    // doctor — changing what a later visit renders as.
    psql(`delete from note_templates where name = 'E2E Venous Duplex Report'`);
  } catch {
    /* best effort — the suite's own cleanup sweeps the user anyway */
  }
}
