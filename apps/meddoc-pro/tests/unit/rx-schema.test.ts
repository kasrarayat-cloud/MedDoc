// ============================================================================
// RxOutputSchema — prescription draft output (M4)
// ----------------------------------------------------------------------------
// Locks the RxDraft shape, the RxWarning variants, and the D2 guarantee
// that the schema rejects an OutputError sentinel.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { RxOutputSchema, type RxOutput } from '@meddoc/types';

const base: RxOutput = {
  confidence: 'medium',
  prescriptions: [
    {
      drug: 'Amoxicillin',
      dose: '500 mg',
      route: 'PO',
      frequency: 'TID',
      duration: '10 days',
      quantity: '#30 capsules',
      refills: 0,
      sig: 'Take 1 capsule by mouth 3 times daily for 10 days.',
      is_controlled: false,
      clinician_requested: true,
      evidence_quote: "Start amoxicillin five hundred milligrams three times a day for ten days",
      warnings: [
        {
          kind: 'allergy',
          severity: 'critical',
          message: 'Patient has listed penicillin allergy — consider macrolide.',
          related_drugs: ['Penicillin V'],
        },
      ],
      confidence: 'high',
    },
  ],
  ambiguities: [],
};

describe('RxOutputSchema', () => {
  it('accepts a well-formed single prescription', () => {
    expect(RxOutputSchema.safeParse(base).success).toBe(true);
  });

  it('accepts empty prescriptions array (e.g. no meds prescribed)', () => {
    expect(RxOutputSchema.safeParse({ ...base, prescriptions: [] }).success).toBe(true);
  });

  it('rejects refills outside 0–11', () => {
    expect(
      RxOutputSchema.safeParse({
        ...base,
        prescriptions: [{ ...base.prescriptions[0], refills: 12 }],
      }).success
    ).toBe(false);
    expect(
      RxOutputSchema.safeParse({
        ...base,
        prescriptions: [{ ...base.prescriptions[0], refills: -1 }],
      }).success
    ).toBe(false);
  });

  it('rejects unknown warning kinds', () => {
    expect(
      RxOutputSchema.safeParse({
        ...base,
        prescriptions: [
          {
            ...base.prescriptions[0],
            warnings: [
              {
                kind: 'typo-not-allowed',
                severity: 'warning',
                message: 'x',
                related_drugs: [],
              },
            ],
          },
        ],
      }).success
    ).toBe(false);
  });

  it('REJECTS OutputError-shaped payloads (D2)', () => {
    expect(
      RxOutputSchema.safeParse({
        _error: {
          code: 'SCHEMA_FAIL',
          message: 'bad',
          attempts: 2,
          occurredAt: new Date().toISOString(),
        },
      }).success
    ).toBe(false);
  });

  it('rejects unknown top-level keys (strict)', () => {
    expect(RxOutputSchema.safeParse({ ...base, foo: 1 }).success).toBe(false);
  });
});
