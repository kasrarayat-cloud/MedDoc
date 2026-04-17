// ============================================================================
// SoapNoteSchema — requires_immediate_follow_up (M5 safety flag)
// ----------------------------------------------------------------------------
// The flag is optional so ScribeOutput rows written by M2/M3/M4 still
// parse cleanly after the schema bump. Psychiatry's template instructs
// the generator to set it when risk surfaces; patient-summary reads it
// to append crisis resources.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { SoapNoteSchema, type SoapNote } from '@meddoc/types';

const base: SoapNote = {
  confidence: 'medium',
  subjective: { chief_complaint: 'Follow-up for anxiety.' },
  objective: { mental_status_exam: 'Alert, oriented, cooperative.' },
  assessment: [
    {
      icd10_candidate: 'F41.1',
      description: 'Generalized anxiety disorder.',
      evidence_quote: 'Follow-up for anxiety.',
      confidence: 'medium',
    },
  ],
  plan: { medications: 'Continue sertraline 50 mg daily.' },
  missing_required_elements: [],
  ambiguities: [],
};

describe('SoapNoteSchema requires_immediate_follow_up', () => {
  it('accepts a SOAP without the field (M2/M3/M4 backward compat)', () => {
    expect(SoapNoteSchema.safeParse(base).success).toBe(true);
  });

  it('accepts requires_immediate_follow_up=true', () => {
    const withFlag = { ...base, requires_immediate_follow_up: true };
    const parsed = SoapNoteSchema.safeParse(withFlag);
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data.requires_immediate_follow_up).toBe(true);
  });

  it('accepts requires_immediate_follow_up=false', () => {
    expect(
      SoapNoteSchema.safeParse({ ...base, requires_immediate_follow_up: false }).success
    ).toBe(true);
  });

  it('rejects non-boolean values', () => {
    expect(
      SoapNoteSchema.safeParse({ ...base, requires_immediate_follow_up: 'yes' }).success
    ).toBe(false);
    expect(
      SoapNoteSchema.safeParse({ ...base, requires_immediate_follow_up: 1 }).success
    ).toBe(false);
  });
});
