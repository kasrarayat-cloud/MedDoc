// ============================================================================
// PatientSummarySchema — patient-facing summary (M4)
// ----------------------------------------------------------------------------
// Structured JSON form (D6). Client-side Flesch-Kincaid (user-added M4
// requirement) scores the concatenated body for 6th-grade reading level —
// that logic is a separate test against the calculator util.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { PatientSummarySchema, type PatientSummary } from '@meddoc/types';

const base: PatientSummary = {
  confidence: 'medium',
  greeting: "Hi Jane, here's a quick recap of today's visit.",
  what_we_talked_about: ['Your cough and runny nose.', 'How long you have been sick.'],
  your_plan: ['Rest a lot.', 'Drink plenty of water.', 'Use a decongestant if you need it.'],
  medications: ['No new medicines today.'],
  follow_up: 'Call us if you are not better in 7 to 10 days.',
  when_to_call_us: [
    'Fever over 101 degrees.',
    'Trouble breathing.',
    'Chest pain.',
  ],
  reading_level_target: '6th_grade',
  ambiguities: [],
};

describe('PatientSummarySchema', () => {
  it('accepts a valid summary', () => {
    expect(PatientSummarySchema.safeParse(base).success).toBe(true);
  });

  it('requires greeting to be non-empty', () => {
    expect(PatientSummarySchema.safeParse({ ...base, greeting: '' }).success).toBe(false);
  });

  it('allows empty medications list (no Rx this visit)', () => {
    expect(PatientSummarySchema.safeParse({ ...base, medications: [] }).success).toBe(true);
  });

  it('allows empty follow_up string (nothing scheduled)', () => {
    expect(PatientSummarySchema.safeParse({ ...base, follow_up: '' }).success).toBe(true);
  });

  it('rejects reading_level_target other than 6th_grade', () => {
    expect(
      PatientSummarySchema.safeParse({ ...base, reading_level_target: '8th_grade' }).success
    ).toBe(false);
  });

  it('REJECTS OutputError-shaped payloads (D2)', () => {
    expect(
      PatientSummarySchema.safeParse({
        _error: {
          code: 'SCHEMA_FAIL',
          message: 'x',
          attempts: 2,
          occurredAt: new Date().toISOString(),
        },
      }).success
    ).toBe(false);
  });

  it('rejects unknown top-level keys (strict)', () => {
    expect(PatientSummarySchema.safeParse({ ...base, tone: 'warm' }).success).toBe(false);
  });
});
