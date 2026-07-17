// ============================================================================
// Layer 7d — Referral letter drafts (T-M6)
// ----------------------------------------------------------------------------
// Short referral notes, one per referral the SOAP plan mentions. Returns
// an empty array when no referrals are documented — the UI renders an
// empty state rather than inventing one.
// ============================================================================

import { z } from 'zod';
import { modelClient } from '@meddoc/ai';
import { updateTemplateTwinSyntheticQaClaimBoundVisit } from '@/worker/staging-qa-mutation-fence';

const MODEL = 'claude-sonnet-4-6';

export const Referral = z.object({
  to: z.string().min(1),
  reason: z.string().min(1),
  relevant_history: z.string().min(1),
  urgency: z.enum(['routine', 'urgent', 'stat']),
  evidence_quote: z.string().min(1),
});
export type Referral = z.infer<typeof Referral>;

export const ReferralsResult = z.object({
  referrals: z.array(Referral).default([]),
});
export type ReferralsResult = z.infer<typeof ReferralsResult>;

export interface Layer7dInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  soapFinal: string;
  entitiesJson: string;
}

export async function runLayer7dReferrals(
  input: Layer7dInput,
): Promise<ReferralsResult> {
  const system = [
    'Review the SOAP plan for referrals (to specialists, imaging, labs,',
    'therapy, etc.). Draft a brief referral note for each referral the',
    'plan mentions. Return an empty array when the plan does not mention',
    'any referrals — do not invent them.',
    '',
    'Fields per referral:',
    '- to: specialty, or specific provider/service if the plan names one',
    '  (e.g. "Cardiology", "Dr. Chen — Cardiology", "Orthopedic MRI of',
    '  the right knee")',
    '- reason: 1-2 sentences on the clinical indication',
    '- relevant_history: 2-3 sentences summarising pertinent PMH /',
    '  current meds / exam/labs that the recipient needs to triage.',
    '  Patient demographics (age/sex): include ONLY when explicitly',
    '  stated in the SOAP or entities. NEVER infer, estimate, or',
    '  annotate an age — if no age is stated, omit it entirely',
    '  (no "(age inferred)", no approximate ages).',
    '- urgency: routine | urgent | stat',
    '    stat    — same-day or needs ED-level care',
    '    urgent  — within 1-2 weeks',
    '    routine — anything else',
    '- evidence_quote: verbatim SOAP snippet documenting the referral',
    '',
    'Respond with VALID JSON ONLY:',
    '{ "referrals": [{ "to": "...", "reason": "...",',
    '                  "relevant_history": "...",',
    '                  "urgency": "routine",',
    '                  "evidence_quote": "..." }] }',
  ].join('\n');

  const user = [
    'Entities:',
    input.entitiesJson,
    '',
    'SOAP note:',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_referrals',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: ReferralsResult,
    maxTokens: 2048,
    // Q2 fix-pack §01.11 + §08.3 — referral letters are billing-adjacent
    // (some payers gate specialty visits on a structured referral).
    // Tightened from 0.3 to 0.1 so re-runs on the same SOAP produce
    // the same referral phrasing.
    temperature: 0.1,
  });

  await updateTemplateTwinSyntheticQaClaimBoundVisit({
    visitId: input.visitId,
    userId: input.userId ?? '',
    practiceId: input.practiceId,
    data: { referrals: result as unknown as object },
  });

  return result;
}
