// ============================================================================
// ReferralOutputSchema — referral-letter output (M4)
// ----------------------------------------------------------------------------
// One Claude call returns an array of letters (D5). Schema locks the
// urgency enum and the evidence-quote requirement, plus the D2 OutputError
// rejection.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { ReferralOutputSchema, type ReferralOutput } from '@meddoc/types';

const base: ReferralOutput = {
  confidence: 'medium',
  referrals: [
    {
      specialty: 'Cardiology',
      urgency: 'routine',
      clinical_summary:
        'Established hypertension with stable BP on lisinopril 20mg daily; ordering echo for LVH evaluation.',
      reason_for_referral: 'Evaluate for left ventricular hypertrophy given long-standing HTN.',
      relevant_history:
        'HTN diagnosed 2022; current meds lisinopril 20mg; no known cardiac history; NKDA.',
      evidence_quote: 'let me send you over to cardiology for an echo',
      confidence: 'high',
    },
  ],
  ambiguities: [],
};

describe('ReferralOutputSchema', () => {
  it('accepts a valid single-letter output', () => {
    expect(ReferralOutputSchema.safeParse(base).success).toBe(true);
  });

  it('accepts empty referrals (no referrals made this visit)', () => {
    expect(ReferralOutputSchema.safeParse({ ...base, referrals: [] }).success).toBe(true);
  });

  it('rejects invalid urgency', () => {
    expect(
      ReferralOutputSchema.safeParse({
        ...base,
        referrals: [
          // @ts-expect-error — intentional bad enum
          { ...base.referrals[0], urgency: 'tomorrow-ish' },
        ],
      }).success
    ).toBe(false);
  });

  it('requires evidence_quote on every referral', () => {
    expect(
      ReferralOutputSchema.safeParse({
        ...base,
        referrals: [{ ...base.referrals[0], evidence_quote: '' }],
      }).success
    ).toBe(false);
  });

  it('REJECTS OutputError-shaped payloads (D2)', () => {
    expect(
      ReferralOutputSchema.safeParse({
        _error: {
          code: 'PROVIDER_ERROR',
          message: 'claude returned empty',
          attempts: 2,
          occurredAt: new Date().toISOString(),
        },
      }).success
    ).toBe(false);
  });

  it('rejects unknown top-level keys (strict)', () => {
    expect(ReferralOutputSchema.safeParse({ ...base, notes: 'x' }).success).toBe(false);
  });
});
