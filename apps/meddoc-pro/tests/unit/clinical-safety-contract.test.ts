// ============================================================================
// ClinicalSafetyResponseSchema — shared contract for GET /clinical-safety
// ----------------------------------------------------------------------------
// Scribe → MedDoc Pro internal API (D3). Fields mirror Prisma's Medication
// + Allergy models, without the audit-trail + FK noise. This test is a
// contract lock so a Prisma migration that changes the shape breaks CI
// before it hits the Rx pipeline.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  ClinicalSafetyResponseSchema,
  type ClinicalSafetyResponse,
} from '@meddoc/types';

const base: ClinicalSafetyResponse = {
  patientId: 'p_abc123',
  medications: [
    {
      name: 'Lisinopril',
      dosage: '20 mg',
      frequency: 'once daily',
      isActive: true,
      notes: null,
    },
  ],
  allergies: [
    {
      allergen: 'Penicillin',
      reaction: 'hives',
      severity: 'MODERATE',
      notes: null,
    },
  ],
};

describe('ClinicalSafetyResponseSchema', () => {
  it('accepts a valid response', () => {
    expect(ClinicalSafetyResponseSchema.safeParse(base).success).toBe(true);
  });

  it('allows empty medications + allergies (patient with no safety data)', () => {
    expect(
      ClinicalSafetyResponseSchema.safeParse({ ...base, medications: [], allergies: [] }).success
    ).toBe(true);
  });

  it('permits nullable dosage / frequency / notes on medications', () => {
    expect(
      ClinicalSafetyResponseSchema.safeParse({
        ...base,
        medications: [
          { name: 'Aspirin', dosage: null, frequency: null, isActive: true, notes: null },
        ],
      }).success
    ).toBe(true);
  });

  it('rejects severity values outside the Prisma enum', () => {
    expect(
      ClinicalSafetyResponseSchema.safeParse({
        ...base,
        allergies: [
          // @ts-expect-error — intentional bad enum
          { ...base.allergies[0], severity: 'ANAPHYLACTIC' },
        ],
      }).success
    ).toBe(false);
  });

  it('requires non-empty medication names', () => {
    expect(
      ClinicalSafetyResponseSchema.safeParse({
        ...base,
        medications: [{ ...base.medications[0], name: '' }],
      }).success
    ).toBe(false);
  });
});
