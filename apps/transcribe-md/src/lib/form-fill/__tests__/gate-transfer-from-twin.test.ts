import { describe, it, expect } from 'vitest';

import { transferFromTwin, numberedListConcepts, type TwinApprovedField } from '../transfer-from-twin';
import type { FormField } from '../types';

// Ruling #326 Slice D — transfer-by-identity from a certified twin. The invariant:
// every transferred concept is one the twin approved; a labeled box with no approved
// concept is left unmapped (caller refuses); an unlabeled box is excluded, never guessed.

function field(id: string, label: string, multiline = false): FormField {
  return { id, label, page: 0, boxes: [], multiline };
}

// A minimal colon-shaped twin: a section, a metadata field, and two numbered lists.
const TWIN: TwinApprovedField[] = [
  { originalLabel: 'PROCEDURE', concept: 'procedure.performed', displayOrder: 1 },
  { originalLabel: 'PATIENT NAME', concept: 'visit_metadata.patient_name', displayOrder: 2 },
  { originalLabel: 'Fill-in', concept: 'procedure.findings', displayOrder: 3 },
  { originalLabel: 'Fill-in', concept: 'procedure.findings', displayOrder: 4 },
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

  it('position-maps numbered groups to the Nth twin numbered-list concept', () => {
    const grouped = [
      field('s1', 'PROCEDURE:'),
      field('n1', '1.'), field('n2', '2.'),        // group 0 → findings
      field('mid', 'CONSENT'),                      // breaks the run (unmapped labeled)
      field('n3', '1.'), field('n4', '2.'),        // group 1 → recommendations
    ];
    const { fields } = transferFromTwin(grouped, TWIN);
    const c = (id: string) => fields.find((f) => f.id === id)?.concept;
    expect(c('n1')).toBe('procedure.findings');
    expect(c('n2')).toBe('procedure.findings');
    expect(c('n3')).toBe('procedure.recommendations');
    expect(c('n4')).toBe('procedure.recommendations');
  });

  it('REFUSES a concept the twin did not approve — labeled box left unmapped', () => {
    // CONSENT is not in this twin's approved set → no concept, reported as a gap.
    const { fields, unmappedLabeled } = transferFromTwin([field('c', 'CONSENT')], TWIN);
    expect(fields[0]!.concept).toBeNull();
    expect(unmappedLabeled.map((u) => u.label)).toContain('CONSENT');
  });

  it('EXCLUDES an unlabeled box (never guessed, not a fillable field)', () => {
    const { fields, excludedUnlabeled } = transferFromTwin([field('e', '')], TWIN);
    expect(fields).toHaveLength(0); // not in the fillable set
    expect(excludedUnlabeled.map((u) => u.id)).toContain('e');
  });

  it('never assigns a concept outside the approved set (deterministic hit must also be approved)', () => {
    // A twin that does NOT approve patient_name; a deterministic PATIENT NAME hit must be refused.
    const twinNoName = TWIN.filter((t) => t.concept !== 'visit_metadata.patient_name');
    const { fields, unmappedLabeled } = transferFromTwin([field('p', 'PATIENT NAME:')], twinNoName);
    expect(fields[0]!.concept).toBeNull();
    expect(unmappedLabeled).toHaveLength(1);
  });
});
