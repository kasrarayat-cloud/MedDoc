// ============================================================================
// Layer 7a — ICD-10-CM coding (T-M6)
// ----------------------------------------------------------------------------
// Reads the polished SOAP + extracted entities and returns a list of
// evidence-backed ICD-10 codes for billing. No code is included unless
// it can be supported by a verbatim quote from the SOAP, and confidence
// is emitted per-code so the UI can surface uncertainty visually.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';

const MODEL = 'claude-sonnet-4-6';

export const IcdCode = z.object({
  code: z
    .string()
    .regex(/^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$/i, 'ICD-10-CM format'),
  description: z.string().min(1),
  evidence_quote: z.string().min(1),
  /** 0-1 confidence — the UI maps <0.5 red, 0.5-0.8 amber, >0.8 green. */
  confidence: z.number().min(0).max(1),
});
export type IcdCode = z.infer<typeof IcdCode>;

export const IcdResult = z.object({
  codes: z.array(IcdCode).default([]),
});
export type IcdResult = z.infer<typeof IcdResult>;

export interface Layer7aInput {
  visitId: string;
  practiceId: string;
  specialty: string;
  soapFinal: string;
  entitiesJson: string;
}

export async function runLayer7aIcdCoding(
  input: Layer7aInput
): Promise<IcdResult> {
  const system = [
    'You are a certified medical coding specialist. Extract ICD-10-CM',
    '(2025) codes from this clinician SOAP note for billing purposes.',
    '',
    'Principles:',
    '- Primary diagnosis first, then comorbidities that were addressed',
    '  in the plan.',
    '- Code ONLY active problems the clinician addressed at THIS visit.',
    '- Do NOT code "rule out" diagnoses or historical conditions that',
    '  did not affect today\'s plan.',
    '- Use the most specific code possible (e.g. I11.0 over I15.9 when',
    '  hypertensive heart failure is clearly documented).',
    '- Include Z codes for preventive or screening encounters when the',
    '  SOAP explicitly documents them.',
    '',
    'For EACH code, include:',
    '- code: valid ICD-10-CM, letter + 2-7 alphanumerics, e.g. "E11.9"',
    '- description: the ICD-10-CM official title',
    '- evidence_quote: verbatim snippet from the SOAP note supporting',
    '  this code',
    '- confidence: 0.0-1.0 based on how directly the SOAP documents it',
    '    >=0.9 explicit diagnosis statement',
    '    0.7-0.9 strongly implied by findings + plan',
    '    0.5-0.7 reasonable inference, worth doctor review',
    '    <0.5   speculative — include only if you would back it in',
    '            a billing audit',
    '',
    'CRITICAL: If you cannot cite a specific evidence_quote for a code,',
    'OMIT the code. Hallucinating ICD codes can constitute billing fraud.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{ "codes": [{ "code": "...", "description": "...",',
    '              "evidence_quote": "...", "confidence": 0.0 }] }',
  ].join('\n');

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'Entities (structured extract from the visit):',
    input.entitiesJson,
    '',
    'SOAP note (the authoritative source for codes):',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_icd_coding',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: IcdResult,
    maxTokens: 3072,
    temperature: 0.1,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { icdCodes: result as unknown as object },
  });

  return result;
}
