// ============================================================================
// Layer 7c — Rx drafts with safety warnings (T-M6)
// ----------------------------------------------------------------------------
// Safety-critical layer. The prompt explicitly refuses to silently fix
// ambiguous doses — actions stay 'unclear' and the issue shows up as a
// warning the doctor must acknowledge before signing. Better to
// interrupt the clinician than hand them a silently wrong prescription.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';

const MODEL = 'claude-sonnet-4-6';

export const RxAction = z.enum([
  'new',
  'continue',
  'increase',
  'decrease',
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
  rx_drug: z.string().min(1),
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
  soapFinal: string;
  entitiesJson: string;
}

export async function runLayer7cRxDrafting(
  input: Layer7cInput
): Promise<RxResult> {
  const system = [
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
    '- action: one of new | continue | increase | decrease | discontinue',
    '  | unclear. Use "unclear" WHEN YOU ARE NOT SURE rather than',
    '  guessing.',
    '- evidence_quote: verbatim SOAP snippet supporting the Rx',
    '',
    'SAFETY WARNINGS — surface, don\'t silently fix. For each concern,',
    'emit a warning object with severity and a human-readable message:',
    '',
    '  critical — likely patient harm if unaddressed:',
    '    - Drug matches a documented allergy / known cross-reactivity',
    '    - Dose appears out of the adult (or pediatric if applicable)',
    '      therapeutic range',
    '    - Contraindication with a condition documented in the SOAP',
    '      PMH/entities',
    '',
    '  major — almost certainly needs clarification:',
    '    - Known drug-drug interaction with the patient\'s current',
    '      medication list (from entities)',
    '    - Duplicate-therapy (two drugs in the same class without',
    '      rationale in the plan)',
    '',
    '  minor — worth a glance:',
    '    - Missing or ambiguous information (no dose, no frequency,',
    '      "increase lisinopril" with no target dose)',
    '    - Unusual but plausible choice for the documented indication',
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
  ].join('\n');

  const user = [
    'Extracted entities (includes current medications + allergies):',
    input.entitiesJson,
    '',
    'SOAP note (plan section is where Rx changes live):',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_rx_drafting',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: RxResult,
    maxTokens: 3072,
    temperature: 0.1,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { rxDrafts: result as unknown as object },
  });

  return result;
}
