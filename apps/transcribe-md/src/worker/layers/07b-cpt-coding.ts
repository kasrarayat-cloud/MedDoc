// ============================================================================
// Layer 7b — CPT + E&M level (T-M6)
// ----------------------------------------------------------------------------
// Extracts the E&M code per 2021 AMA guidelines (Medical Decision Making
// OR total time, whichever is higher) plus any procedural CPT codes and
// modifiers. The model's reasoning is persisted so the UI can show
// "how we got 99214" alongside the code itself.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import prisma from '@meddoc/db';

const MODEL = 'claude-sonnet-4-6';

const EmReasoning = z.object({
  problems: z
    .array(
      z.object({
        description: z.string(),
        /** stable / unstable / new with uncertain prognosis */
        status: z.string(),
      })
    )
    .default([]),
  /** Free-text summary of labs/imaging/records reviewed. */
  data: z.string(),
  risk: z.enum(['minimal', 'low', 'moderate', 'high']),
});

export const EmCode = z.object({
  code: z.string().regex(/^[0-9]{5}$/, '5-digit CPT'),
  /** Optional human description ("Established patient, level 4"). */
  description: z.string(),
  reasoning: EmReasoning,
  evidence_quote: z.string().min(1),
});

export const ProcedureCpt = z.object({
  code: z.string().regex(/^[0-9]{5}$/, '5-digit CPT'),
  description: z.string(),
  evidence_quote: z.string().min(1),
});

export const Modifier = z.object({
  code: z.string().regex(/^[0-9]{2}$/, '2-digit modifier'),
  rationale: z.string().min(1),
});

export const CptResult = z.object({
  em: EmCode.nullable(),
  procedures: z.array(ProcedureCpt).default([]),
  modifiers: z.array(Modifier).default([]),
});
export type CptResult = z.infer<typeof CptResult>;

export interface Layer7bInput {
  visitId: string;
  practiceId: string;
  specialty: string;
  soapFinal: string;
  entitiesJson: string;
}

export async function runLayer7bCptCoding(
  input: Layer7bInput
): Promise<CptResult> {
  const system = [
    'You are a certified CPT coding specialist. From this SOAP note:',
    '',
    '1. Determine the E&M code under 2021 AMA guidelines. Level is the',
    '   HIGHER OF Medical Decision Making complexity OR total time',
    '   (including documentation).',
    '',
    '   Established patient (99212-99215):',
    '     99212 — Straightforward. 1 minor, self-limited problem.',
    '     99213 — Low. 2 minor OR 1 stable chronic; minimal data',
    '             review; minimal risk.',
    '     99214 — Moderate. 1+ chronic not at goal OR 2+ chronic',
    '             stable; moderate data review; moderate risk',
    '             (e.g. prescription-drug management).',
    '     99215 — High. 1+ chronic with severe exacerbation OR new',
    '             problem with uncertain prognosis; extensive data',
    '             review; high risk.',
    '',
    '   New patient (99202-99205) — parallel tiers. Default to',
    '   ESTABLISHED unless the SOAP explicitly says "new patient".',
    '',
    '2. List any procedural CPT codes performed during the visit',
    '   (injections, biopsies, EKG interpretation, etc.) — only those',
    '   the SOAP documents as performed at this encounter.',
    '',
    '3. Suggest CPT modifiers ONLY when clearly warranted:',
    '     -25 separately identifiable E&M on the same day as a',
    '         procedure',
    '     -59 distinct procedural service',
    '     -95 telehealth synchronous',
    '   Skip modifiers if none apply.',
    '',
    'Evidence rule: every code carries a specific SOAP quote. If you',
    'cannot cite evidence, omit the code.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{',
    '  "em": {',
    '    "code": "99214",',
    '    "description": "Established patient, moderate complexity",',
    '    "reasoning": {',
    '      "problems": [{ "description": "HTN not at goal", "status": "unstable" }],',
    '      "data": "reviewed last 3 months of BP log",',
    '      "risk": "moderate"',
    '    },',
    '    "evidence_quote": "…"',
    '  },',
    '  "procedures": [{ "code": "...", "description": "...", "evidence_quote": "..." }],',
    '  "modifiers": [{ "code": "25", "rationale": "..." }]',
    '}',
    '',
    'If the SOAP really describes no E&M encounter (rare — edge case',
    'for telephone-only encounters captured accidentally), return',
    '{ "em": null, "procedures": [], "modifiers": [] }.',
  ].join('\n');

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'Entities:',
    input.entitiesJson,
    '',
    'SOAP note:',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    purpose: 'tm_cpt_coding',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: CptResult,
    maxTokens: 3072,
    temperature: 0.1,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { cptCodes: result as unknown as object },
  });

  return result;
}
