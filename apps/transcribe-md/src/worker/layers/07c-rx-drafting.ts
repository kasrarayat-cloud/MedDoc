// ============================================================================
// Layer 7c — Rx drafts with safety warnings (T-M6)
// ----------------------------------------------------------------------------
// Safety-critical layer. The prompt explicitly refuses to silently fix
// ambiguous doses — actions stay 'unclear' and the issue shows up as a
// warning the doctor must acknowledge before signing. Better to
// interrupt the clinician than hand them a silently wrong prescription.
//
// Fix-Pack 1 / Finding 01.1 — pediatric framing. The layer now consumes
// patient context (DOB, weight, allergies) from the worker and adapts the
// prompt to the patient's age:
//   - ageYears < 18 + weightKg present → mg/kg/day computation required;
//     few-shot examples demonstrate the surfacing pattern
//   - ageYears < 18 + weightKg null    → refuse to draft a numeric dose;
//     emit action="unclear" + a critical warning
//   - ageYears >= 18 OR null DOB       → adult ceilings (status quo)
// ============================================================================

import { z } from 'zod';
import { modelClient, validateRxDose } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { RX_PEDIATRIC_FEWSHOT_EXAMPLES } from '@/worker/prompts/rx-pediatric-examples';
import { logAudit, type AuditAction } from '@/lib/audit';
import { parseRxToMgPerDay } from './rx-sig-parser';

const MODEL = 'claude-opus-4-8';

/** Round 3 PR-D + Fix-Pack 1 Q0-2: shared peds threshold. Mirrors the
 *  threshold in packages/ai/src/data/dose-ranges-validator.ts. Hoisting to a
 *  cross-package shared util is deferred — the constant is identical and a
 *  drift here would surface immediately in the SA1 validator integration. */
const PEDS_AGE_THRESHOLD_YEARS = 18;

// Q2 fix-pack §06.7 — RxAction enum expanded with clinically distinct
// scenarios that previously had to be encoded as discontinue+new pairs
// (switch) or were missing entirely (refill, hold, restart). Existing
// 'increase' / 'decrease' kept for granular dose changes — 'switch' is
// not a substitute for those. 'unclear' stays as the safety fallback
// for ambiguous plan language.
export const RxAction = z.enum([
  'new',
  'refill',
  'continue',
  'increase',
  'decrease',
  'switch',
  'hold',
  'restart',
  'discontinue',
  'unclear',
]);
export type RxAction = z.infer<typeof RxAction>;

export const Prescription = z.object({
  drug: z.string().min(1),
  strength: z.string().nullable().optional(),
  form: z.string().nullable().optional(),
  sig: z.string().nullable().optional(),
  quantity: z.string().nullable().optional(),
  refills: z.string().nullable().optional(),
  action: RxAction,
  evidence_quote: z.string().min(1),
});
export type Prescription = z.infer<typeof Prescription>;

export const RxWarning = z.object({
  severity: z.enum(['critical', 'major', 'minor']),
  // Q1 #19 follow-up: model returns null for general warnings (no
  // specific drug attribution; e.g. "no medications prescribed"
  // observations). 15 of 69 tm_rx_drafting calls SCHEMA_FAILed on
  // this in the 2026-05-10 baseline. Coerce null → "General" so the
  // wire-shape stays string (downstream pdf-generator, docx-generator,
  // ehr-formatters, rx-tab.tsx all treat this as a non-null string).
  rx_drug: z.preprocess(
    (value) => (value == null ? 'General' : value),
    z.string().min(1),
  ),
  message: z.string().min(1),
  evidence_quote: z.string().optional().nullable(),
});
export type RxWarning = z.infer<typeof RxWarning>;

export const RxResult = z.object({
  prescriptions: z.array(Prescription).default([]),
  warnings: z.array(RxWarning).default([]),
});
export type RxResult = z.infer<typeof RxResult>;

export interface Layer7cInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  soapFinal: string;
  entitiesJson: string;
  /** Fix-Pack 1 Q0-2 — patient demographic + safety context. Required so
   *  the prompt can frame mg/kg/day correctly for pediatrics and (in a
   *  follow-on Sub-Agent 1 PR) so validateRxDose can run. `allergies` is
   *  carried here even though L7c only references it indirectly today —
   *  the structure matches what the downstream validator expects so
   *  wiring SA1 is a pure additive change. */
  patient: {
    dateOfBirth: Date | string | null;
    weightKg: number | null;
    allergies: ReadonlyArray<string>;
  };
}

/**
 * Compute age in completed years from a DOB. Returns null if DOB is
 * missing/invalid. Mirrors `computeAgeYears` in
 * packages/ai/src/data/dose-ranges-validator.ts:69 — kept inlined here
 * because the validator's helper is not exported. If a third caller appears
 * we'll hoist into a shared util.
 */
function computeAgeYears(dob: Date | string | null): number | null {
  if (!dob) return null;
  const d = dob instanceof Date ? dob : new Date(dob);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age;
}

/**
 * Build the pediatric-context block appended to the user message. The
 * three branches are externally observable (the test suite asserts on
 * the header text), so message tweaks should keep "PEDIATRIC PATIENT",
 * "weight required", and "ADULT PATIENT" as stable substrings.
 */
function buildPediatricContext(
  ageYears: number | null,
  weightKg: number | null
): string {
  if (ageYears !== null && ageYears < PEDS_AGE_THRESHOLD_YEARS) {
    if (weightKg === null) {
      return [
        'PEDIATRIC PATIENT WITH UNKNOWN WEIGHT.',
        `Patient age: ${ageYears} years. Weight: not recorded.`,
        'Refuse to draft a numeric dose; emit action="unclear" for every',
        'Rx and a critical warning "weight required for pediatric dosing".',
        'Do NOT guess a weight from age, do NOT default to adult dosing,',
        'do NOT compute mg/kg without a recorded weight.',
      ].join('\n');
    }
    return [
      `PEDIATRIC PATIENT, age ${ageYears} years, weight ${weightKg} kg.`,
      'Compute every dose as mg/kg/day. Use peds ceilings:',
      '  - acetaminophen: 75 mg/kg/day max OR 4000 mg/day, whichever is lower',
      '  - amoxicillin: 80-90 mg/kg/day (high-dose); 40-50 mg/kg/day (standard)',
      '  - ibuprofen: 30-40 mg/kg/day max',
      '  - other drugs: cite peds source range when known; emit a minor',
      '    warning if the prescribed mg/kg/day appears outside it.',
      'Include the mg/kg/day calculation in the evidence_quote AND in any',
      'warning message. If the dose is at-or-near the peds ceiling, emit',
      'a minor or major warning with the computed mg/kg/day in the message.',
      'For neonates (< 28 days old), default action="unclear" and emit a',
      'critical warning unless the SOAP cites a neonate-specific protocol.',
    ].join('\n');
  }
  return 'ADULT PATIENT. Use adult dose ceilings.';
}

export async function runLayer7cRxDrafting(
  input: Layer7cInput
): Promise<RxResult> {
  // Fix-Pack 1 Q0-2 — derive age once at the top so prompt assembly +
  // (future) validator calls share the same number.
  const ageYears = computeAgeYears(input.patient.dateOfBirth);
  const isPediatric =
    ageYears !== null && ageYears < PEDS_AGE_THRESHOLD_YEARS;

  const systemSections: string[] = [
    [
      'You are a clinical pharmacist drafting prescriptions from a SOAP',
      'plan. For each medication the doctor wants to prescribe, change,',
      'or stop, produce a structured prescription object.',
      '',
      'Prescription fields:',
      '- drug: generic name preferred, proper case (e.g. "Lisinopril")',
      '- strength: e.g. "20 mg"; null when dose is not specified',
      '- form: tablet, capsule, solution, inhaler, injection, etc.',
      '  (null if not stated)',
      '- sig: patient instructions — e.g. "Take 1 tablet by mouth daily"',
      '  (null if not stated)',
      '- quantity: e.g. "90" or "30 mL" (null if not stated)',
      '- refills: as a string, e.g. "3" or "0" (null if not stated)',
      '- action: one of:',
      '    new          — first-time start; full sig required',
      '    refill       — same drug, same dose; new fill cycle',
      '    continue     — keep on current drug/dose with no change',
      '    increase     — same drug, higher dose',
      '    decrease     — same drug, lower dose',
      '    switch       — replacing one drug with another (single decision)',
      '    hold         — temporary pause (peri-op, illness, lab abnormality)',
      '    restart      — resuming a previously held drug',
      '    discontinue  — stopping the drug',
      '    unclear      — plan is ambiguous; do NOT guess',
      '  Use "unclear" WHEN YOU ARE NOT SURE rather than guessing.',
      '- evidence_quote: verbatim SOAP snippet supporting the Rx',
      '',
      'SAFETY WARNINGS — surface, don\'t silently fix. For each concern,',
      'emit a warning object with severity and a human-readable message:',
      '',
      '  critical — likely patient harm if unaddressed:',
      '    - Drug matches a documented allergy / known cross-reactivity',
      '    - Dose appears out of the therapeutic range for this patient',
      '      (adult OR pediatric — see PEDIATRIC AWARENESS section below',
      '       for how to handle peds)',
      '    - Contraindication with a condition documented in the SOAP',
      '      PMH/entities',
      '    - Pediatric patient with no recorded weight (do NOT guess)',
      '    - Neonatal (< 28 days) without a neonate-specific protocol cited',
      '',
      '  major — almost certainly needs clarification:',
      '    - Known drug-drug interaction with the patient\'s current',
      '      medication list (from entities)',
      '    - Duplicate-therapy (two drugs in the same class without',
      '      rationale in the plan)',
      '    - Pediatric dose at-or-above the published mg/kg/day ceiling',
      '',
      '  minor — worth a glance:',
      '    - Missing or ambiguous information (no dose, no frequency,',
      '      "increase lisinopril" with no target dose)',
      '    - Unusual but plausible choice for the documented indication',
      '    - Pediatric dose near (within ~10% of) the mg/kg/day ceiling',
      '',
      'PEDIATRIC AWARENESS:',
      '- "Pediatric" = patient age < 18 years.',
      '- For pediatric patients, the dose ceiling is the LOWER of:',
      '    (a) the adult max',
      '    (b) the peds mg/kg/day × patient weight (kg)',
      '- ALWAYS compute mg/kg/day from the prescribed dose and the',
      '  patient\'s weight, and surface the calculation in BOTH the',
      '  evidence_quote (e.g. "amoxicillin 250 mg TID — 47 mg/kg/day at',
      '  16 kg") AND any warning message that fires for that Rx.',
      '- If the SOAP names a pediatric dose that\'s at-or-near the adult',
      '  ceiling for a peds patient, emit a major or minor warning with',
      '  the mg/kg/day calculation so the doctor can verify against',
      '  references before signing.',
      '- For neonatal patients (< 28 days old), default action="unclear"',
      '  and emit a critical warning UNLESS the SOAP cites a neonate-',
      '  specific protocol — neonate dosing is highly drug-specific and',
      '  should not be inferred from older-pediatric ranges.',
      '- If the patient is pediatric AND no weight is recorded:',
      '    DO NOT draft a numeric dose. Emit action="unclear" for every',
      '    Rx and a CRITICAL warning "weight required for pediatric',
      '    dosing — please record the patient\'s weight before signing."',
      '    Pediatric dose-by-age guesses are unsafe — refuse rather than',
      '    estimate.',
      '',
      'CRITICAL RULES:',
      '1. Never silently assume a dose. If the plan says "increase',
      '   lisinopril" without a target, action="unclear" and emit a',
      '   minor warning asking for the target dose.',
      '2. When the plan says "continue current meds", pull doses from',
      '   the entities.medications list rather than inventing.',
      '3. For discontinuations, still emit the prescription object',
      '   (action="discontinue") so the doctor sees what was stopped.',
      '4. Do not suggest drugs the doctor did NOT mention. You are',
      '   transcribing the plan, not prescribing.',
      '5. Pediatric without a weight = refuse to draft numeric doses.',
      '   Action="unclear" + critical warning. (See PEDIATRIC AWARENESS.)',
      '',
      'Respond with VALID JSON ONLY, no markdown fences:',
      '{',
      '  "prescriptions": [{',
      '    "drug": "Lisinopril",',
      '    "strength": "20 mg",',
      '    "form": "tablet",',
      '    "sig": "Take 1 tablet by mouth once daily",',
      '    "quantity": "90",',
      '    "refills": "3",',
      '    "action": "increase",',
      '    "evidence_quote": "Increased lisinopril to 20 mg daily"',
      '  }],',
      '  "warnings": [{',
      '    "severity": "major",',
      '    "rx_drug": "Lisinopril",',
      '    "message": "Patient reported ACE inhibitor cough previously — verify tolerance before increasing dose.",',
      '    "evidence_quote": "reports dry cough with prior lisinopril"',
      '  }]',
      '}',
    ].join('\n'),
  ];

  // Append peds few-shot examples ONLY when the patient is pediatric.
  // Adult visits don't need the extra tokens, and the examples would
  // anchor the model on weight-based dosing inappropriately.
  if (isPediatric) {
    systemSections.push('', RX_PEDIATRIC_FEWSHOT_EXAMPLES);
  }

  const system = systemSections.join('\n');

  const pediatricContext = buildPediatricContext(
    ageYears,
    input.patient.weightKg
  );

  const user = [
    pediatricContext,
    '',
    'Extracted entities (includes current medications + allergies):',
    input.entitiesJson,
    '',
    'SOAP note (plan section is where Rx changes live):',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_rx_drafting',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: RxResult,
    maxTokens: 3072,
    temperature: 0.1,
  });

  // Fix-Pack 1 Q0-1 (audit Finding 06.1) — deterministic safety floor.
  // Round 3 PR-D shipped `validateRxDose` but never wired it into L7c;
  // the model output flowed straight to the DB with only the model's
  // training-time pharmacology backstopping it. Now every prescription
  // is run through the verified dose-ranges table and any warnings the
  // validator emits are appended to result.warnings + audit-logged.
  //
  // The validator is fail-closed for unknown drugs (emits
  // RX_DRUG_NOT_IN_VERIFIED_DATABASE) and always-on for the
  // contraindication check (allergy substring match) — those run even
  // when the (strength, sig) → mg/day parse fails.
  for (const rx of result.prescriptions) {
    const doseMgPerDay = parseRxToMgPerDay(
      rx.strength ?? null,
      rx.sig ?? null
    );
    const validation = validateRxDose({
      drug: rx.drug,
      doseMgPerDay,
      patient: {
        dateOfBirth: input.patient.dateOfBirth ?? null,
        weightKg: input.patient.weightKg ?? null,
        allergies: input.patient.allergies ?? [],
      },
    });

    for (const w of validation.warnings) {
      // Severity mapping mirrors the prompt's severity ladder. Dose-
      // exceeds-range and explicit allergy/contraindication matches are
      // patient-harm risks — critical. "Drug not in verified DB" is a
      // major (verify-against-reference) signal, not critical, because
      // the model's pharmacology may still be correct; we just lack a
      // deterministic check. Complex-dosing is minor — it's a "verify
      // individually" nudge, not a hard block.
      const severity: 'critical' | 'major' | 'minor' =
        w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE' ||
        w.code === 'RX_CONTRAINDICATION_MATCH'
          ? 'critical'
          : w.code === 'RX_DRUG_NOT_IN_VERIFIED_DATABASE'
            ? 'major'
            : 'minor';

      result.warnings.push({
        severity,
        rx_drug: rx.drug,
        // [deterministic] prefix lets the Rx panel + audit reviewer
        // distinguish validator-emitted warnings from model-emitted
        // ones, in case both fire on the same drug.
        message: `[deterministic] ${w.message}`,
        evidence_quote: rx.evidence_quote ?? null,
      });

      // PR-D shipped three of the four warning codes as audit-action
      // enum values. RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY is NOT in
      // the AuditAction enum (Prisma) nor in the TS union — adding it
      // would require a Prisma migration that's out of scope for this
      // PR. We still surface the warning to the doctor (above), but
      // skip the audit row. Follow-up: extend the enum + write a
      // migration so the complex-dosing nudge is auditable.
      const isAuditable =
        w.code === 'RX_DOSE_EXCEEDS_VERIFIED_RANGE' ||
        w.code === 'RX_CONTRAINDICATION_MATCH' ||
        w.code === 'RX_DRUG_NOT_IN_VERIFIED_DATABASE';

      if (isAuditable) {
        void logAudit({
          action: w.code as AuditAction,
          targetId: input.visitId,
          targetType: 'TranscribeVisit',
          userId: input.userId,
          practiceId: input.practiceId,
          success: false,
          metadata: w.metadata as Record<string, unknown>,
        });
      }
    }
  }

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { rxDrafts: result as unknown as object },
  });

  return result;
}
