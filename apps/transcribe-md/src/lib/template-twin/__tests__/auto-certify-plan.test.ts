import { describe, expect, it } from 'vitest';
import { planAutoConfirm } from '../auto-certify-eligibility';
import type { TemplateTwinWorkspace } from '../client-types';

/**
 * The engine over a workspace shaped like the REAL customer form: 80 fields,
 * 52 extraction + 23 verified_note_selection + 5 manual, of which 7 are
 * laterality-critical and 6 of those carry a sided label.
 *
 * ⚠️ THE ASSERTION THAT MATTERS IS `MAPPINGS_NOT_READY`'s OWN PREDICATE, not a
 * count. Certification demands, for every mapping: status === 'certified' AND
 * (sourceType === 'manual' OR clinicalConcept). A plan that satisfies a count
 * but not that predicate would pass a test and fail certification.
 */
function ws(fields: Array<Partial<{ label: string; crit: string; src: string; concept: string | null }>>): TemplateTwinWorkspace {
  return {
    fields: fields.map((f, i) => ({
      definitionId: `def_${i}`,
      field: {
        fieldId: `ttf_${i}`,
        originalLabel: f.label ?? `Field ${i}`,
        criticality: f.crit ?? 'routine',
      },
      mapping: {
        sourceType: f.src ?? 'extraction',
        clinicalConcept: f.concept === undefined ? 'exam.vascular' : f.concept,
        status: 'needs_confirmation',
      },
    })),
  } as unknown as TemplateTwinWorkspace;
}

/** MAPPINGS_NOT_READY, restated here so the test asserts the REAL gate. */
const readyForCertification = (m: { status: string; sourceType: string; clinicalConcept: string | null }) =>
  m.status === 'certified' && (m.sourceType === 'manual' || Boolean(m.clinicalConcept));

describe('planAutoConfirm', () => {
  it('the whole real-shaped form satisfies MAPPINGS_NOT_READY after planning', () => {
    const workspace = ws([
      ...Array.from({ length: 52 }, () => ({ src: 'extraction' })),
      ...Array.from({ length: 16 }, () => ({ src: 'verified_note_selection' })),
      { label: 'SIDE OF EXAM: Choose an item.', crit: 'laterality', src: 'verified_note_selection' },
      ...Array.from({ length: 6 }, (_, i) => ({
        label: `${i % 2 ? 'Left' : 'Right'} deep venous system Choose an item.`,
        crit: 'laterality',
        src: 'verified_note_selection',
      })),
      ...Array.from({ length: 5 }, () => ({ src: 'manual', concept: null })),
    ]);
    expect(workspace.fields).toHaveLength(80);

    const out = planAutoConfirm(workspace);

    // ⚠️ THE OWNER TOUCHES ZERO FIELDS.
    expect(out.declined).toHaveLength(0);
    // ⚠️ AND EVERY MAPPING PASSES THE ACTUAL CERTIFICATION PREDICATE.
    expect(out.mappings.every((m) => readyForCertification(m as never))).toBe(true);
    // Provenance still discriminates: 6 sided labels are the document's own word.
    expect(out.provenanceCounts.structural).toBe(6);
    expect(out.provenanceCounts.manual).toBe(5);
    expect(out.provenanceCounts.model).toBe(69);
  });

  it('DECLINES a non-manual field with no concept, and names it', () => {
    const out = planAutoConfirm(ws([{ label: 'Orphan field', concept: null }]));
    expect(out.declined).toEqual([
      { label: 'Orphan field', reason: expect.stringMatching(/concept/i) },
    ]);
    // ⚠️ AND THE DECLINED MAPPING IS LEFT UNTOUCHED — never half-confirmed.
    expect(out.mappings[0].status).not.toBe('certified');
  });

  it('a manual field with NO concept still confirms — attested blank by construction', () => {
    const out = planAutoConfirm(ws([{ src: 'manual', concept: null }]));
    expect(out.declined).toHaveLength(0);
    expect(readyForCertification(out.mappings[0] as never)).toBe(true);
  });

  it('⚠️ NON-VACUITY: the plan can decline — a suite where nothing ever declines proves nothing', () => {
    const none = planAutoConfirm(ws([{ src: 'extraction' }]));
    const some = planAutoConfirm(ws([{ concept: null }]));
    expect(none.declined).toHaveLength(0);
    expect(some.declined).toHaveLength(1);
  });
});
