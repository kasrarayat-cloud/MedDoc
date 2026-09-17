import { describe, it, expect } from 'vitest';

import { transferFromTwin, numberedListConcepts, type TwinApprovedField } from '../transfer-from-twin';
import type { FormField } from '../types';

// Ruling #326 Slice D — transfer-by-identity from a certified twin. Invariants
// (all four hardened after an adversarial pass):
//   • the TWIN's own label→concept is the sole source — the registry never overrides it;
//   • numbered groups match the twin's lists by order WITH A COUNT GUARD (refuse on
//     any structural mismatch — the adjacency-collapse defense);
//   • a labeled box with no approved concept is left unmapped (caller refuses);
//   • an unlabeled box is excluded, never guessed.

function field(id: string, label: string, multiline = false): FormField {
  return { id, label, page: 0, boxes: [], multiline };
}

const TWIN: TwinApprovedField[] = [
  { originalLabel: 'PROCEDURE', concept: 'procedure.performed', displayOrder: 1 },
  { originalLabel: 'PATIENT NAME', concept: 'visit_metadata.patient_name', displayOrder: 2 },
  { originalLabel: 'Fill-in', concept: 'procedure.findings', displayOrder: 3 },
  { originalLabel: 'Fill-in', concept: 'procedure.findings', displayOrder: 4 },
  { originalLabel: 'CONSENT', concept: 'procedure.consent', displayOrder: 5 },
  { originalLabel: 'Fill-in', concept: 'procedure.recommendations', displayOrder: 6 },
  { originalLabel: 'Fill-in', concept: 'procedure.recommendations', displayOrder: 7 },
];

describe('numberedListConcepts', () => {
  it('extracts the twin numbered-list concepts in order, de-duped by run', () => {
    expect(numberedListConcepts(TWIN)).toEqual(['procedure.findings', 'procedure.recommendations']);
  });
});

describe('transferFromTwin', () => {
  it('transfers a section by label-match to the approved concept', () => {
    const { fields } = transferFromTwin([field('a', 'PROCEDURE:')], TWIN);
    expect(fields[0]!.concept).toBe('procedure.performed');
  });

  it('position-maps two SEPARATED numbered groups to the twin lists in order', () => {
    const grouped = [
      field('n1', '1.'), field('n2', '2.'),   // group 0 → findings
      field('mid', 'CONSENT'),                 // separator (approved section)
      field('n3', '1.'), field('n4', '2.'),   // group 1 → recommendations
    ];
    const { fields, unmappedLabeled } = transferFromTwin(grouped, TWIN);
    const c = (id: string) => fields.find((f) => f.id === id)?.concept;
    expect(c('n1')).toBe('procedure.findings');
    expect(c('n3')).toBe('procedure.recommendations');
    expect(unmappedLabeled).toHaveLength(0);
  });

  it('REFUSES all numbered slots when adjacent groups collapse (count guard — adv #1)', () => {
    // Two twin lists, but the detected slots are ADJACENT (no separator) → 1 run →
    // detectedGroups(1) != lists(2) → every numbered slot refused, never guessed.
    const grouped = [field('n1', '1.'), field('n2', '2.'), field('n3', '1.'), field('n4', '2.')];
    const { fields, unmappedLabeled } = transferFromTwin(grouped, TWIN);
    expect(fields.every((f) => f.concept === null)).toBe(true);
    expect(unmappedLabeled).toHaveLength(4);
  });

  it('treats paren-style numbered slots as numbered, not as unmapped labels (adv #2)', () => {
    const grouped = [field('n1', '1)'), field('n2', '(2)'), field('mid', 'CONSENT'), field('n3', '1)')];
    const { unmappedLabeled } = transferFromTwin(grouped, TWIN);
    // detectedGroups(2) == lists(2) → they map, so the only concern is they are NOT
    // treated as labels → no numbered slot appears as unmapped.
    expect(unmappedLabeled.filter((u) => /\d/.test(u.label))).toHaveLength(0);
  });

  it('the TWIN identity wins over the shared registry (adv #3)', () => {
    // The registry would map POST-OPERATIVE FINDINGS → procedure.findings, but the
    // doctor approved procedure.recommendations for that exact label. Identity wins.
    const twin: TwinApprovedField[] = [
      { originalLabel: 'POST-OPERATIVE FINDINGS', concept: 'procedure.recommendations', displayOrder: 1 },
    ];
    const { fields } = transferFromTwin([field('a', 'POST-OPERATIVE FINDINGS')], twin);
    expect(fields[0]!.concept).toBe('procedure.recommendations');
  });

  it('transfers a twin label whose concept the registry would NOT produce (adv #4)', () => {
    // The doctor mapped RECOMMENDATIONS → procedure.findings; the registry would say
    // procedure.recommendations. Identity-only means the twin concept transfers (not refused).
    const twin: TwinApprovedField[] = [
      { originalLabel: 'RECOMMENDATIONS', concept: 'procedure.findings', displayOrder: 1 },
    ];
    const { fields, unmappedLabeled } = transferFromTwin([field('a', 'RECOMMENDATIONS')], twin);
    expect(fields[0]!.concept).toBe('procedure.findings');
    expect(unmappedLabeled).toHaveLength(0);
  });

  it('a LABELED box the twin never mapped is left unmapped (caller refuses)', () => {
    const { fields, unmappedLabeled } = transferFromTwin([field('x', 'MYSTERY FIELD')], TWIN);
    expect(fields[0]!.concept).toBeNull();
    expect(unmappedLabeled.map((u) => u.label)).toContain('MYSTERY FIELD');
  });

  it('EXCLUDES an unlabeled box (never guessed, not a fillable field)', () => {
    const { fields, excludedUnlabeled } = transferFromTwin([field('e', '')], TWIN);
    expect(fields).toHaveLength(0);
    expect(excludedUnlabeled.map((u) => u.id)).toContain('e');
  });
});
