// ============================================================================
// CodingOutputSchema — ICD-10 + CPT extraction output (M4)
// ----------------------------------------------------------------------------
// Spec §11 item 3: every code must have an evidence_quote. The schema
// doesn't substring-check against a transcript (that's the hallucination
// detector's job in eval-scribe); this test locks the shape + proves the
// schema rejects the OutputError sentinel (D2).
// ============================================================================

import { describe, it, expect } from 'vitest';
import { CodingOutputSchema, type CodingOutput } from '@meddoc/types';

const base: CodingOutput = {
  confidence: 'medium',
  icd10: [
    {
      code: 'J06.9',
      description: 'Acute upper respiratory infection, unspecified.',
      evidence_quote: "I've had this cough and runny nose for about four days",
      confidence: 'high',
    },
  ],
  cpt: [
    {
      code: '99213',
      description: 'Office visit — established patient, low complexity.',
      evidence_quote: "What brings you in today?",
      confidence: 'medium',
    },
  ],
  ambiguities: [],
};

describe('CodingOutputSchema', () => {
  it('accepts a well-formed coding output', () => {
    expect(CodingOutputSchema.safeParse(base).success).toBe(true);
  });

  it('allows empty icd10 / cpt arrays (nothing codable)', () => {
    expect(
      CodingOutputSchema.safeParse({ ...base, icd10: [], cpt: [] }).success
    ).toBe(true);
  });

  it('requires non-empty evidence_quote on every code', () => {
    const bad = {
      ...base,
      icd10: [{ ...base.icd10[0], evidence_quote: '' }],
    };
    expect(CodingOutputSchema.safeParse(bad).success).toBe(false);
  });

  it('REJECTS OutputError-shaped payloads so a corrupt blob can\'t be saved as success', () => {
    const errorShape = {
      _error: {
        code: 'SCHEMA_FAIL',
        message: 'bad',
        attempts: 2,
        occurredAt: new Date().toISOString(),
      },
    };
    expect(CodingOutputSchema.safeParse(errorShape).success).toBe(false);
  });

  it('rejects unknown top-level keys (strict)', () => {
    expect(
      CodingOutputSchema.safeParse({ ...base, extra_field: 'surprise' }).success
    ).toBe(false);
  });
});
