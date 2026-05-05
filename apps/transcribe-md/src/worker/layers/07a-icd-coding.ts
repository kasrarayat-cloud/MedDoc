// ============================================================================
// Layer 7a — ICD-10-CM coding (T-M6)
// ----------------------------------------------------------------------------
// Reads the polished SOAP + extracted entities and returns a list of
// evidence-backed ICD-10 codes for billing. No code is included unless
// it can be supported by a verbatim quote from the SOAP, and confidence
// is emitted per-code so the UI can surface uncertainty visually.
// ============================================================================

import { z } from 'zod';
import { modelClient, isValidIcd10 } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { logAudit } from '@/lib/audit';

const MODEL = 'claude-sonnet-4-6';

export const IcdCode = z.object({
  code: z
    .string()
    .regex(/^[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?$/i, 'ICD-10-CM format'),
  description: z.string().min(1),
  evidence_quote: z.string().min(1),
  /** 0-1 confidence — the UI maps <0.5 red, 0.5-0.8 amber, >0.8 green. */
  confidence: z.number().min(0).max(1),
  /** Q2 fix-pack §06.6 — categorical companion to the numeric
   *  confidence. Derived from the number (>=0.8 = high, 0.5-0.8 =
   *  medium, <0.5 = low). The dual representation lets the UI render
   *  the gradient AND the post-processor flag low-confidence codes
   *  for `needsReview` without re-deriving thresholds. */
  confidenceLevel: z.enum(['high', 'medium', 'low']),
});
export type IcdCode = z.infer<typeof IcdCode>;

export const IcdResult = z.object({
  codes: z.array(IcdCode).default([]),
});
export type IcdResult = z.infer<typeof IcdResult>;

export interface Layer7aInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
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
    '- confidenceLevel: categorical view of confidence (Q2 fix-pack):',
    '    "high"   → confidence >= 0.8',
    '    "medium" → 0.5 <= confidence < 0.8',
    '    "low"    → confidence < 0.5',
    '  Always set; downstream UI flags low-confidence codes for review.',
    '',
    'CRITICAL: If you cannot cite a specific evidence_quote for a code,',
    'OMIT the code. Hallucinating ICD codes can constitute billing fraud.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{ "codes": [{ "code": "...", "description": "...",',
    '              "evidence_quote": "...", "confidence": 0.0,',
    '              "confidenceLevel": "high" }] }',
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
    userId: input.userId,
    purpose: 'tm_icd_coding',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: IcdResult,
    maxTokens: 3072,
    // Q2 fix-pack — billing codes are deterministic; tightened from
    // 0.1 to 0 so the same SOAP produces the same code list every time.
    temperature: 0,
  });

  // Round 3 PR-D — A06-P0-002 deterministic ICD-10 allowlist floor.
  // Filter Claude's output through the canonical starter set; drop any
  // code that doesn't match. Each rejection emits an audit row so the
  // admin dashboard can reason about how often the model emits invalid
  // codes (signal for prompt-tightening or expanding the allowlist).
  const accepted: typeof result.codes = [];
  const rejected: Array<{ code: string; description: string }> = [];
  for (const c of result.codes) {
    if (isValidIcd10(c.code)) {
      // Q2 fix-pack §06.6 — defensive re-derivation of confidenceLevel
      // from the numeric confidence. The model is asked to emit both
      // and they should agree; if the model drifted on the categorical
      // rule, the numeric value is the source of truth. Prevents a
      // "high" badge over a 0.4-confidence code.
      const derivedLevel: 'high' | 'medium' | 'low' =
        c.confidence >= 0.8 ? 'high' :
        c.confidence >= 0.5 ? 'medium' : 'low';
      accepted.push({ ...c, confidenceLevel: derivedLevel });
    } else {
      rejected.push({ code: c.code, description: c.description });
    }
  }
  if (rejected.length > 0) {
    void logAudit({
      action: 'CODING_COACH_REJECTED_INVALID_ICD',
      targetId: input.visitId,
      targetType: 'TranscribeVisit',
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      metadata: {
        rejectedCount: rejected.length,
        // Only the codes (NOT the AI-emitted descriptions which can
        // include patient context). Codes alone are non-PHI structured
        // billing data.
        rejectedCodes: rejected.map((r) => r.code),
      },
    });
  }
  const filtered: typeof result = { codes: accepted };

  // Q2 fix-pack §06.6 — surface low-confidence codes via needsReview
  // when one or more accepted codes land at confidenceLevel='low'.
  // Doctor sees the warning before signing rather than auto-attaching
  // a speculative code to billing.
  const lowConfCodes = accepted.filter((c) => c.confidenceLevel === 'low');
  if (lowConfCodes.length > 0) {
    await prisma.transcribeVisit.update({
      where: { id: input.visitId },
      data: {
        needsReview: true,
        reviewReason: `${lowConfCodes.length} ICD code${lowConfCodes.length === 1 ? '' : 's'} at low confidence — verify before billing: ${lowConfCodes.map((c) => c.code).join(', ')}.`,
      },
    });
  }

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { icdCodes: filtered as unknown as object },
  });

  return filtered;
}
