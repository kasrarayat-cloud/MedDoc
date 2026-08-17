import { describe, expect, it } from 'vitest';
import {
  decideAutoConfirm,
  hasStructuralLateralityAnchor,
  type AutoConfirmCandidate,
} from '../auto-certify-eligibility';

const base: AutoConfirmCandidate = {
  originalLabel: 'Findings',
  criticality: 'routine',
  sourceType: 'extraction',
  hasClinicalConcept: true,
};

describe('structural laterality anchor', () => {
  it.each([
    ['Right deep venous system Choose an item.', true],
    ['Left Choose an item. is Choose an item.', true],
    ['Bilateral lower extremity', true],
    ['SIDE OF EXAM: Choose an item.', false],
    ['Findings', false],
    ['', false],
    [null, false],
  ])('%s -> %s', (label, expected) => {
    expect(hasStructuralLateralityAnchor(label as string | null)).toBe(expected);
  });

  it('⚠️ SUBSTRING TRAP: "cleft" must NOT anchor via "left"', () => {
    expect(hasStructuralLateralityAnchor('Cleft palate noted')).toBe(false);
  });

  it('⚠️ SUBSTRING TRAP: "copyright" must NOT anchor via "right"', () => {
    expect(hasStructuralLateralityAnchor('Copyright 2026 West Medical')).toBe(false);
  });

  it('a sided SECTION HEADING anchors a bare label', () => {
    expect(hasStructuralLateralityAnchor('Choose an item.', 'Right Leg:')).toBe(true);
  });
});

describe('decideAutoConfirm — the fail-closed direction', () => {
  /**
   * ⚠️ AMENDED, RULING #124. This arm used to assert the OPPOSITE — that an
   * unanchored laterality field is REFUSED. It is not, and the measurement is
   * why: certification never encodes a side, so refusing here bought nothing and
   * cost the doctor a field-touch. Fail-closed lives at fill and is asserted in
   * resolver.test.ts ('CONFLICTING sides…', 'required_laterality_missing') and
   * row-laterality.test.ts (CROSS-LEG CANARY, both directions).
   */
  it('CONFIRMS an unanchored laterality field — certification encodes no side', () => {
    const d = decideAutoConfirm({
      ...base,
      originalLabel: 'SIDE OF EXAM: Choose an item.',
      criticality: 'laterality',
      sourceType: 'verified_note_selection',
    });
    expect(d.confirm).toBe(true);
    expect(d.reason).toBeNull();
  });

  it('⚠️ but PROVENANCE still discriminates — unanchored is model, not structural', () => {
    const d = decideAutoConfirm({
      ...base,
      originalLabel: 'SIDE OF EXAM',
      criticality: 'laterality',
    });
    expect(d.provenance).toBe('model');
  });

  it('refuses any non-manual field with no concept', () => {
    const d = decideAutoConfirm({ ...base, hasClinicalConcept: false });
    expect(d.confirm).toBe(false);
    expect(d.reason).toMatch(/concept/i);
  });
});

describe('decideAutoConfirm — the confirming direction', () => {
  it('CONFIRMS a structurally-sided laterality field, with structural provenance', () => {
    const d = decideAutoConfirm({
      ...base,
      originalLabel: 'Right deep venous system Choose an item.',
      criticality: 'laterality',
      sourceType: 'verified_note_selection',
    });
    expect(d.confirm).toBe(true);
    expect(d.provenance).toBe('structural');
  });

  it('CONFIRMS an ordinary model proposal', () => {
    expect(decideAutoConfirm(base)).toMatchObject({ confirm: true, provenance: 'model' });
  });

  it('CONFIRMS a manual field with no concept — attested blank by construction', () => {
    const d = decideAutoConfirm({
      ...base,
      sourceType: 'manual',
      hasClinicalConcept: false,
    });
    expect(d).toMatchObject({ confirm: true, provenance: 'manual' });
  });
});

describe("the measured customer form — 7 laterality fields, both directions present", () => {
  // Labels taken verbatim from the compiled IR of the real uploaded template.
  const REAL: Array<[string, boolean]> = [
    ['SIDE OF EXAM: Choose an item.', false],
    ['Right Choose an item. is Choose an item.', true],
    ['Right Choose an item. is Choose an item.', true],
    ['Right deep venous system Choose an item.', true],
    ['Left Choose an item. is Choose an item.', true],
    ['Left Choose an item. is Choose an item.', true],
    ['Left deep venous system Choose an item.', true],
  ];

  it('all 7 confirm, and 6 of 7 carry STRUCTURAL provenance', () => {
    const decided = REAL.map(([label]) =>
      decideAutoConfirm({
        ...base,
        originalLabel: label,
        criticality: 'laterality',
        sourceType: 'verified_note_selection',
      }),
    );
    // Certification is not blocked — the owner touches ZERO fields.
    expect(decided.every((d) => d.confirm)).toBe(true);
    // But the audit trail still says which were the document's own assertion.
    expect(decided.filter((d) => d.provenance === 'structural')).toHaveLength(6);
    expect(decided.filter((d) => d.provenance === 'model')).toHaveLength(1);
  });

  it('⚠️ NON-VACUITY: the fixture actually contains both outcomes', () => {
    expect(new Set(REAL.map(([, v]) => v)).size).toBe(2);
  });
});
