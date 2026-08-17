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
  it('REFUSES an unanchored laterality field, and names why', () => {
    const d = decideAutoConfirm({
      ...base,
      originalLabel: 'SIDE OF EXAM: Choose an item.',
      criticality: 'laterality',
      sourceType: 'verified_note_selection',
    });
    expect(d.confirm).toBe(false);
    expect(d.provenance).toBeNull();
    expect(d.reason).toMatch(/which side/i);
  });

  it('⚠️ a laterality field can NEVER reach model provenance', () => {
    // Everything else about this candidate is ordinary and would confirm.
    const d = decideAutoConfirm({
      ...base,
      originalLabel: 'SIDE OF EXAM',
      criticality: 'laterality',
    });
    expect(d.provenance).not.toBe('model');
    expect(d.confirm).toBe(false);
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

  it('resolves 6 of 7 structurally and names the 7th', () => {
    const decided = REAL.map(([label]) =>
      decideAutoConfirm({
        ...base,
        originalLabel: label,
        criticality: 'laterality',
        sourceType: 'verified_note_selection',
      }),
    );
    expect(decided.filter((d) => d.confirm).length).toBe(6);
    const refused = decided.filter((d) => !d.confirm);
    expect(refused).toHaveLength(1);
    expect(refused[0].reason).toMatch(/which side/i);
  });

  it('⚠️ NON-VACUITY: the fixture actually contains both outcomes', () => {
    expect(new Set(REAL.map(([, v]) => v)).size).toBe(2);
  });
});
