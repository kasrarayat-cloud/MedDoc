// ============================================================================
// Layer 7e — Patient-facing summary (T-M6)
// ----------------------------------------------------------------------------
// Plain-English summary the patient can read at home. The Claude call
// produces the prose; we measure the Flesch-Kincaid grade locally and
// record the number on the visit so the UI can surface it. We do NOT
// regenerate when the grade is too high — flagging is the job of this
// layer, rewriting is the doctor's (or a future T-M6.5 auto-rewrite pass).
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { fleschKincaidGrade } from './readability';

const MODEL = 'claude-sonnet-4-6';

/** Threshold above which we emit a readability warning. 10 is a soft
 *  ceiling — at 8 the summary is solidly middle-school; at 10+ it's
 *  starting to read like a consent form. */
export const HIGH_GRADE_THRESHOLD = 10;

const PatientSummaryResult = z.object({
  summary: z.string().min(1),
});
type PatientSummaryResult = z.infer<typeof PatientSummaryResult>;

export interface Layer7eInput {
  visitId: string;
  practiceId: string;
  specialty: string;
  soapFinal: string;
  entitiesJson: string;
}

export interface Layer7eOutput {
  summary: string;
  fleschKincaid: number;
  flagged: boolean;
}

export async function runLayer7ePatientSummary(
  input: Layer7eInput
): Promise<Layer7eOutput> {
  const system = [
    'You are writing a visit summary for the patient to read at home.',
    'Use plain English — no medical jargon, no abbreviations, no ICD/',
    'CPT codes. Explain conditions in terms a non-medical person',
    'understands.',
    '',
    'Replacements to make:',
    '  "hypertension"   → "high blood pressure"',
    '  "lisinopril"     → "lisinopril (a blood pressure medicine)"',
    '  "HbA1c" / "A1c"  → "a blood test that shows your average sugar',
    '                     over the past three months"',
    '  "f/u 3 months"   → "See me again in three months"',
    '  "labs"           → "blood tests"',
    '  "ECG" / "EKG"    → "a heart-tracing test"',
    '',
    'Structure (use these exact headings, one blank line between):',
    '  What we talked about today',
    '  What we found',
    '  What we\'re doing about it',
    '  Your medications',
    '  Your next steps',
    '  When to call us',
    '',
    'Rules:',
    '- Use short sentences. Aim for 8th-grade reading level or lower.',
    '- Warm but professional tone.',
    '- "When to call us" should list concrete red-flag symptoms',
    '  relevant to the visit (e.g. for high blood pressure:',
    '  chest pain, severe headache, vision changes).',
    '- Do NOT invent information. If the SOAP is silent on medication',
    '  changes, say "Your medications are not changing today."',
    '- Sign off with "Take care," followed by the clinician\'s name',
    '  if it appears in the SOAP, otherwise just "Take care,".',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{ "summary": "What we talked about today\\n…" }',
  ].join('\n');

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'Entities (for medication names + conditions):',
    input.entitiesJson,
    '',
    'SOAP note (the authoritative source):',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete<PatientSummaryResult>({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_patient_summary',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: PatientSummaryResult,
    maxTokens: 2048,
  });

  const grade = fleschKincaidGrade(result.summary);
  const flagged = grade > HIGH_GRADE_THRESHOLD;

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { patientSummary: result.summary },
  });

  return { summary: result.summary, fleschKincaid: grade, flagged };
}
