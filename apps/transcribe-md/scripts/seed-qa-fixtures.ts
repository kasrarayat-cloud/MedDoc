// ============================================================================
// Seed Script — QA Interaction Auditor rich visit fixtures (v3.1)
// ----------------------------------------------------------------------------
// Builds the four sample visits documented in
// .claude/agents/qa-interaction-auditor/fixtures/sample-visits/README.md.
//
// Each visit is owned by `qa-auditor@synthetic.test` (seeded by
// scripts/seed-qa-user.ts) and attached to its "QA Test Patient"
// (DOB 2000-01-01, plus an extra pediatric patient for visit C).
//
// Visits:
//   A. bump-eligible primary care   — bump CTA renders + apply-additions
//   B. critical Rx warning          — sign blocks until override
//   C. pediatric overdose           — exercises validateRxDose mg/kg
//   D. non-clinical refusal         — L5 refusal + L6 banner SOAP
//
// Idempotent (like seed-qa-user.ts): each visit has a stable id derived
// from the fixture key so re-running the script upserts in place
// instead of creating four new rows every run. Audit rows are
// append-only per HIPAA; we never delete them.
//
// Run with:  pnpm tsx apps/transcribe-md/scripts/seed-qa-fixtures.ts
// ============================================================================

import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

import { assertNonProdDatabase } from '@meddoc/db/guard';

export const FIXTURE_USER_EMAIL = 'qa-auditor@synthetic.test';
export const FIXTURE_PRACTICE_ID = 'clinic_main';

/** Stable fixture visit ids — keyed for the agent's --scenario flag.
 *  Re-running the seed updates these rows in place. */
export const FIXTURE_VISIT_IDS = {
  bumpEligible: 'qa_fix_visit_bump_eligible',
  criticalRx: 'qa_fix_visit_critical_rx',
  pediatric: 'qa_fix_visit_pediatric',
  nonClinical: 'qa_fix_visit_nonclinical',
  // v3.3: a QUEUED, audio-less visit so the walker can land on
  // /visits/[id]/record without triggering the page's redirect-when-
  // not-QUEUED guard. See sweep-visit-record.mjs.
  recordDraft: 'qa_fix_visit_record_draft',
} as const;

const SEEDED_IDS_PATH = resolve(
  __dirname,
  '..',
  '..',
  '..',
  '.claude',
  'agents',
  'qa-interaction-auditor',
  'fixtures',
  'seeded-ids.json'
);

// ────────────────────────────────────────────────────────────────────────────
// SOAP + ICD + Rx + CPT payloads (no PHI; doctor-narrated synthetic content)
// ────────────────────────────────────────────────────────────────────────────

/** Visit A — rich enough that the L7b CPT scorer produces 99213 with
 *  bumpableTo: 99214 + at least one gap criterion. Walker exercises:
 *  bump CTA render, section pulse hints, sage edge-glow on click,
 *  bump modal apply-additions round-trip + EM_BUMP_APPLIED audit row. */
export const SOAP_BUMP_ELIGIBLE = `## Subjective

**Chief Complaint:** Follow-up for hypertension and chronic low back pain.

**HPI:** Patient is a 52-year-old established patient who returns for
ongoing management of hypertension. Symptom course: blood pressure
readings at home have been elevated (avg 148/92 over the last two
weeks). Symptom location: low back pain in the lumbar region radiating
to the left thigh. Symptom quality: dull constant ache with intermittent
sharp shooting episodes after prolonged sitting. Symptom timing:
present throughout the day, worse in the evening. Severity 5/10 today,
up from 3/10 at last visit.

**ROS:**
- Constitutional: denies fever, fatigue, weight loss.
- Cardiovascular: occasional palpitations, no chest pain.
- Respiratory: no cough, no shortness of breath.
- Gastrointestinal: no nausea, no abdominal pain.
- Musculoskeletal: low back pain as in HPI.

**PMH:** Hypertension (10 years), hyperlipidemia (5 years).
**PSH:** Cholecystectomy 2018.
**Social History:** Non-smoker, occasional alcohol, sedentary.

## Objective

**Vital Signs:** BP 152/94, HR 78, RR 16, T 98.4F, BMI 31.

**Cardiovascular:** Regular rate and rhythm, no murmurs / rubs / gallops.
**Respiratory:** Lungs clear to auscultation bilaterally, no wheezes.
**Musculoskeletal:** Lumbar paraspinal tenderness on the left;
straight-leg-raise negative bilaterally; range of motion mildly
reduced in flexion.

## Assessment

1. Hypertension, uncontrolled — readings consistently above target,
   likely requires medication adjustment.
2. Chronic low back pain with mild radicular features — stable course,
   conservative management.
3. Hyperlipidemia — followed; lipid panel due in 3 months.

## Plan

1. Increase lisinopril from 10 mg to 20 mg daily; recheck BP in 2 weeks.
2. Continue ibuprofen PRN for back pain; refer to physical therapy
   (3 sessions/wk × 4 wk).
3. Lipid panel + comprehensive metabolic panel ordered for next visit.
4. Reinforce DASH diet + 30 min brisk walking 5 days/wk.
5. Follow up in 4 weeks for BP recheck.`;

/** Visit B — same SOAP shape as A but with an Rx draft carrying a
 *  critical-severity warning that BLOCKS sign until overridden. */
export const SOAP_CRITICAL_RX = SOAP_BUMP_ELIGIBLE.replace(
  '**PMH:** Hypertension (10 years), hyperlipidemia (5 years).',
  '**PMH:** Hypertension (10 years), hyperlipidemia (5 years), atrial fibrillation on warfarin.'
);

/** Visit C — pediatric. Short SOAP; the interesting part is the Rx
 *  draft (amoxicillin 500 mg TID for a 16 kg child = 93.75 mg/kg/day,
 *  exceeds the 90 mg/kg/day pediatric ceiling for amoxicillin). */
export const SOAP_PEDIATRIC = `## Subjective

**Chief Complaint:** Acute otitis media in a 4-year-old.

**HPI:** 4-year-old previously healthy patient brought in with 3 days
of right ear pain, low-grade fever (max 100.8F), and decreased appetite.
No vomiting, no rash. Tugging at right ear since yesterday. Sleeping
poorly.

**PMH:** None significant. Vaccinations up to date.
**Allergies:** No known drug allergies.

## Objective

**Vital Signs:** T 100.6F, HR 110, RR 22, weight 16 kg.

**HEENT:** Right tympanic membrane erythematous, bulging, opacified.
Left TM normal. Pharynx clear. No cervical lymphadenopathy.
**Lungs:** Clear bilaterally.

## Assessment

1. Acute otitis media, right.

## Plan

1. Amoxicillin 500 mg PO TID × 10 days.
2. Symptomatic care with acetaminophen for fever / pain.
3. Return precautions reviewed with parent.
4. Follow up in 10 days or sooner if not improving.`;

/** Visit D — non-clinical input. L5 critique refuses the SOAP and L6
 *  polish writes a banner instead of canonical S/O/A/P. The renderer
 *  must show the banner, NOT four "Subjective section is empty" empty-
 *  state messages (the original Pattern C bug from the smoke-test
 *  visit). */
export const SOAP_NON_CLINICAL = `## Abstraction of Third-Party Witness Statement

> This input was identified by the clinical-intake review as a
> non-clinical document and was not written into a SOAP note.
> The source material describes a meeting between a solicitor and a
> witness on the topic of a property-line dispute — there is no
> doctor-patient encounter present.
>
> If this input was submitted in error (e.g. wrong audio file
> attached to the wrong visit), please re-attach the correct
> recording from the visit-detail page and re-run the pipeline.
>
> See \`docs/critique-policy.md\` §3 for the refusal taxonomy.

**Document type:** witness statement.
**Topic:** property-line / boundary dispute.
**Speakers identified:** solicitor (James Hartwell, MR), witness
(non-clinical narrator).
**Recommendation:** none — non-clinical content is not eligible for
SOAP-shape rendering.`;

const ICD_BUMP_ELIGIBLE = {
  codes: [
    {
      code: 'I10',
      confidence: 0.95,
      description: 'Essential (primary) hypertension',
      evidence_quote:
        'Hypertension, uncontrolled — readings consistently above target',
    },
    {
      code: 'M54.50',
      confidence: 0.88,
      description: 'Low back pain, unspecified',
      evidence_quote:
        'Chronic low back pain with mild radicular features',
    },
    {
      code: 'E78.5',
      confidence: 0.84,
      description: 'Hyperlipidemia, unspecified',
      evidence_quote: 'Hyperlipidemia — followed; lipid panel due',
    },
  ],
};

const ICD_PEDIATRIC = {
  codes: [
    {
      code: 'H66.91',
      confidence: 0.95,
      description: 'Otitis media, unspecified, right ear',
      evidence_quote:
        'Right tympanic membrane erythematous, bulging, opacified',
    },
  ],
};

const RX_BUMP_ELIGIBLE = {
  warnings: [
    {
      rx_drug: 'Lisinopril',
      severity: 'minor',
      message:
        'Patient on lisinopril increase from 10 → 20 mg daily; monitor potassium + creatinine in 2 weeks.',
      evidence_quote: 'Increase lisinopril from 10 mg to 20 mg daily',
    },
  ],
  prescriptions: [
    {
      drug: 'Lisinopril',
      strength: '20mg',
      sig: '20mg PO daily',
      action: 'increase',
      refills: 5,
    },
  ],
};

const RX_CRITICAL = {
  warnings: [
    {
      rx_drug: 'Ibuprofen',
      severity: 'critical',
      message:
        'Patient on warfarin per PMH — concurrent NSAID significantly increases major bleeding risk. Document override + monitor INR before signing.',
      evidence_quote: 'PMH: atrial fibrillation on warfarin',
    },
    {
      rx_drug: 'Ibuprofen',
      severity: 'minor',
      message: 'Allergies not documented for this patient.',
      evidence_quote: 'Allergies: none documented',
    },
  ],
  prescriptions: [
    {
      drug: 'Ibuprofen',
      strength: '600mg',
      sig: '600mg PO q8h PRN pain',
      action: 'new',
    },
  ],
};

const RX_PEDIATRIC = {
  warnings: [
    {
      rx_drug: 'Amoxicillin',
      severity: 'critical',
      message:
        'Pediatric overdose — 500 mg TID = 1500 mg/day for a 16 kg patient is 93.75 mg/kg/day, exceeds AAP ceiling of 90 mg/kg/day for acute otitis media.',
      evidence_quote: 'Amoxicillin 500 mg PO TID × 10 days; weight 16 kg',
    },
  ],
  prescriptions: [
    {
      drug: 'Amoxicillin',
      strength: '500mg',
      sig: '500mg PO TID × 10 days',
      action: 'new',
    },
  ],
};

// ────────────────────────────────────────────────────────────────────────────
// Seed entry-point
// ────────────────────────────────────────────────────────────────────────────

interface SeededIds {
  seededAt?: string;
  userId?: string;
  userEmail?: string;
  patientId?: string;
  patientName?: string;
  practiceId?: string;
  visitIds?: Partial<Record<keyof typeof FIXTURE_VISIT_IDS, string>>;
}

async function main() {
  await import('dotenv/config').catch(() => null);

  // FAIL-CLOSED: never seed prod (see packages/db/src/db-guard.ts).
  assertNonProdDatabase();

  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { PrismaClient } = require('@prisma/client');
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { PrismaPg } = require('@prisma/adapter-pg');

  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  try {
    // Verify the test user is seeded — fixtures are nothing without
    // an owner.
    const user = await prisma.user.findUnique({
      where: { email: FIXTURE_USER_EMAIL },
      select: { id: true, role: true, isActive: true },
    });
    if (!user) {
      console.error(
        `${FIXTURE_USER_EMAIL} not found.\n` +
          'Run apps/transcribe-md/scripts/seed-qa-user.ts first.'
      );
      process.exit(2);
    }

    // Primary patient (adult — used by visits A, B, D).
    const adultPatient = await prisma.transcribeMdPatient.findFirst({
      where: { practiceId: FIXTURE_PRACTICE_ID, name: 'QA Test Patient' },
      select: { id: true },
    });
    if (!adultPatient) {
      console.error(
        'QA Test Patient row missing. Run seed-qa-user.ts to create it.'
      );
      process.exit(2);
    }

    // Pediatric patient — created here, idempotent by stable id.
    const pediatricPatientId = 'qa_fix_patient_pediatric';
    await prisma.transcribeMdPatient.upsert({
      where: { id: pediatricPatientId },
      update: {
        practiceId: FIXTURE_PRACTICE_ID,
        name: 'QA Pediatric Test',
        dateOfBirth: new Date('2022-01-01T00:00:00.000Z'),
      },
      create: {
        id: pediatricPatientId,
        practiceId: FIXTURE_PRACTICE_ID,
        name: 'QA Pediatric Test',
        dateOfBirth: new Date('2022-01-01T00:00:00.000Z'),
      },
    });

    const baseVisitFields = {
      userId: user.id,
      status: 'READY' as const,
      inputMode: 'text_notes' as const,
      soapVersion: 1,
      audioDurationSec: null,
      dictationDurationSec: null,
      needsReview: false,
      reviewReason: null,
      processingCostCents: 0,
      processingStartedAt: new Date(Date.now() - 5 * 60 * 1000),
      processingFinishedAt: new Date(Date.now() - 60 * 1000),
      confidenceScores: {
        referrals: { status: 'ok' },
        cpt_coding: { status: 'ok' },
        icd_coding: { status: 'ok' },
        rx_drafting: { status: 'ok' },
      },
      referrals: { referrals: [] },
    };

    // Helper: visit upsert keyed by stable fixture id.
    async function upsertVisit(opts: {
      id: string;
      patientId: string;
      patientName: string;
      specialty: string;
      soap: string;
      rawTextInput: string;
      icd: unknown;
      rx: unknown;
    }) {
      await prisma.transcribeVisit.upsert({
        where: { id: opts.id },
        update: {
          ...baseVisitFields,
          patientId: opts.patientId,
          patientName: opts.patientName,
          specialty: opts.specialty,
          soapDraft: opts.soap,
          soapFinal: opts.soap,
          rawTextInput: opts.rawTextInput,
          icdCodes: opts.icd ?? null,
          cptCodes: null,
          rxDrafts: opts.rx ?? null,
        },
        create: {
          id: opts.id,
          ...baseVisitFields,
          patientId: opts.patientId,
          patientName: opts.patientName,
          specialty: opts.specialty,
          soapDraft: opts.soap,
          soapFinal: opts.soap,
          rawTextInput: opts.rawTextInput,
          icdCodes: opts.icd ?? null,
          rxDrafts: opts.rx ?? null,
        },
      });
    }

    await upsertVisit({
      id: FIXTURE_VISIT_IDS.bumpEligible,
      patientId: adultPatient.id,
      patientName: 'QA Test Patient',
      specialty: 'primary-care',
      soap: SOAP_BUMP_ELIGIBLE,
      rawTextInput: 'follow up hypertension low back pain',
      icd: ICD_BUMP_ELIGIBLE,
      rx: RX_BUMP_ELIGIBLE,
    });

    await upsertVisit({
      id: FIXTURE_VISIT_IDS.criticalRx,
      patientId: adultPatient.id,
      patientName: 'QA Test Patient',
      specialty: 'primary-care',
      soap: SOAP_CRITICAL_RX,
      rawTextInput: 'follow up hypertension a fib warfarin',
      icd: ICD_BUMP_ELIGIBLE,
      rx: RX_CRITICAL,
    });

    await upsertVisit({
      id: FIXTURE_VISIT_IDS.pediatric,
      patientId: pediatricPatientId,
      patientName: 'QA Pediatric Test',
      specialty: 'primary-care',
      soap: SOAP_PEDIATRIC,
      rawTextInput: 'pediatric otitis media 4yo amoxicillin',
      icd: ICD_PEDIATRIC,
      rx: RX_PEDIATRIC,
    });

    await upsertVisit({
      id: FIXTURE_VISIT_IDS.nonClinical,
      patientId: adultPatient.id,
      patientName: 'QA Test Patient',
      specialty: 'primary-care',
      soap: SOAP_NON_CLINICAL,
      rawTextInput:
        'recording of meeting between solicitor and witness regarding property line dispute',
      icd: { codes: [] },
      rx: null,
    });

    // v3.3 — record-draft fixture. The /visits/[id]/record page only
    // renders when status === 'QUEUED' (else redirects to /visits/[id]).
    // No SOAP, no transcript, no audio — same shape a freshly-created
    // voice_dictation visit has the moment a doctor lands on it.
    await prisma.transcribeVisit.upsert({
      where: { id: FIXTURE_VISIT_IDS.recordDraft },
      update: {
        userId: user.id,
        status: 'QUEUED' as const,
        inputMode: 'voice_dictation' as const,
        patientId: adultPatient.id,
        patientName: 'QA Test Patient',
        specialty: 'primary-care',
        audioKey: null,
        audioMimeType: null,
        audioDurationSec: null,
        dictationDurationSec: null,
        transcriptText: null,
        transcriptRaw: undefined,
        soapDraft: null,
        soapFinal: null,
        rawTextInput: null,
        icdCodes: undefined,
        cptCodes: undefined,
        rxDrafts: undefined,
        confidenceScores: undefined,
        referrals: undefined,
        needsReview: false,
        reviewReason: null,
        processingCostCents: 0,
        processingStartedAt: null,
        processingFinishedAt: null,
        soapVersion: 1,
      },
      create: {
        id: FIXTURE_VISIT_IDS.recordDraft,
        userId: user.id,
        status: 'QUEUED' as const,
        inputMode: 'voice_dictation' as const,
        patientId: adultPatient.id,
        patientName: 'QA Test Patient',
        specialty: 'primary-care',
        soapVersion: 1,
        needsReview: false,
        processingCostCents: 0,
      },
    });

    // Update seeded-ids.json with the new visit ids.
    let seeded: SeededIds = {};
    if (existsSync(SEEDED_IDS_PATH)) {
      try {
        seeded = JSON.parse(readFileSync(SEEDED_IDS_PATH, 'utf-8'));
      } catch {
        seeded = {};
      }
    }
    seeded.visitIds = { ...seeded.visitIds, ...FIXTURE_VISIT_IDS };
    seeded.seededAt = new Date().toISOString();
    mkdirSync(dirname(SEEDED_IDS_PATH), { recursive: true });
    writeFileSync(SEEDED_IDS_PATH, JSON.stringify(seeded, null, 2) + '\n');

    console.log('\n  QA fixture visits seeded.');
    for (const [scenario, vid] of Object.entries(FIXTURE_VISIT_IDS)) {
      console.log(`  ${scenario.padEnd(14)} → ${vid}`);
    }
    console.log(`  Pediatric patient: ${pediatricPatientId}`);
    console.log(`  Ids file:          ${SEEDED_IDS_PATH}\n`);
  } finally {
    await prisma.$disconnect();
  }
}

const isCli = typeof require !== 'undefined' && require.main === module;
if (isCli) {
  main().catch((err) => {
    console.error('Seed-fixtures failed:', err);
    process.exit(1);
  });
}
