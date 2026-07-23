// ============================================================================
// prescriptionOneLine — route/form-word de-duplication.
// Regression for the KUK bariatric visit (2026-07-23): the drafter emitted
// drug "Cyanocobalamin (Vitamin B12) sublingual" + form "sublingual tablet",
// which rendered "…sublingual sublingual tablet" on every export surface.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { prescriptionOneLine, type Prescription } from '../visit-export';

function rx(overrides: Partial<Prescription> = {}): Prescription {
  return {
    drug: 'Drug',
    strength: null,
    form: null,
    sig: null,
    quantity: null,
    refills: null,
    action: 'new',
    evidence_quote: 'e',
    ...overrides,
  };
}

describe('prescriptionOneLine — route/form dedup', () => {
  it('drops the form\'s leading word when the drug name already carries it (the KUK B12 bug)', () => {
    const line = prescriptionOneLine(
      rx({
        drug: 'Cyanocobalamin (Vitamin B12) sublingual',
        form: 'sublingual tablet',
        sig: 'Take once weekly sublingually',
      })
    );
    expect(line).toBe(
      'Cyanocobalamin (Vitamin B12) sublingual tablet – Take once weekly sublingually'
    );
    expect(line).not.toMatch(/sublingual\s+sublingual/i);
  });

  it('is case-insensitive and collapses a fully-redundant single-word form', () => {
    // drug carries "Sublingual", form is exactly "sublingual" → nothing left to add.
    const line = prescriptionOneLine(rx({ drug: 'Nitroglycerin Sublingual', form: 'sublingual' }));
    expect(line).toBe('Nitroglycerin Sublingual');
  });

  it('leaves a normal drug/form pair untouched (no false dedup)', () => {
    expect(prescriptionOneLine(rx({ drug: 'Lisinopril', strength: '10 mg', form: 'tablet' }))).toBe(
      'Lisinopril 10 mg tablet'
    );
    expect(prescriptionOneLine(rx({ drug: 'Omeprazole', form: 'capsule' }))).toBe(
      'Omeprazole capsule'
    );
  });

  it('only the LEADING form word is de-duped, not a later coincidental match', () => {
    // "tablet" appears in the drug string but is NOT the form's leading word → form intact.
    const line = prescriptionOneLine(rx({ drug: 'Chewable tablet vitamin', form: 'oral tablet' }));
    expect(line).toBe('Chewable tablet vitamin oral tablet');
  });

  // Adversarial defect 1 — leading/trailing whitespace must not skip the dedup.
  it('dedups even when the form has leading/trailing whitespace', () => {
    expect(prescriptionOneLine(rx({ drug: 'B12 sublingual', form: '  sublingual tablet ' }))).toBe(
      'B12 sublingual tablet'
    );
  });

  // Adversarial defect 2 — a multi-word FORM DESCRIPTOR must not be garbled: only
  // known ROUTE words are stripped, so "extended release" survives intact.
  it('never garbles a multi-word form descriptor (extended-release is not a route)', () => {
    const line = prescriptionOneLine(
      rx({ drug: 'Diltiazem Extended-Release', form: 'extended release capsule' })
    );
    expect(line).toBe('Diltiazem Extended-Release extended release capsule');
  });

  // Adversarial defect 3 — punctuation on the leading route word must not defeat it.
  it('dedups when the leading route word carries trailing punctuation', () => {
    expect(prescriptionOneLine(rx({ drug: 'Nitroglycerin sublingual', form: 'sublingual, tablet' }))).toBe(
      'Nitroglycerin sublingual tablet'
    );
  });

  it('a form word that is NOT a known route is never stripped even if it appears in the drug', () => {
    // "tablet" is a form, not a route → not in the whitelist → left intact.
    expect(prescriptionOneLine(rx({ drug: 'Tablet X', form: 'tablet' }))).toBe('Tablet X tablet');
  });
});
