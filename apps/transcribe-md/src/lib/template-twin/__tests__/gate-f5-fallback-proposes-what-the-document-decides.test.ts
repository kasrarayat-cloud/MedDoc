// ============================================================================
// F5 GATE — the fallback proposes what the DOCUMENT decides, and nothing more.
// ----------------------------------------------------------------------------
// `fallbackSemanticMappings` runs when the semantic provider is unavailable
// (`create-draft.ts:257-272`). It used to hard-code `clinicalConcept: null` for
// EVERY field, so a physician confirming the real customer form had to supply
// 75 concepts by hand — including the 53 that the form's own structure and
// labels determine with no model, no network and no ambiguity.
//
// ⚠️ THAT IS THE `sourceType` DEFECT ONE FIELD OVER, AND THE COMMENT EXPLAINING
// THE `sourceType` FIX SAT DIRECTLY ABOVE THE LINE THAT STILL SAID `null`:
// "One classifier, two callers. A second implementation would drift from the
// first the day either is fixed." The classifier was shared; the CONCEPT was
// not.
//
// WHAT THIS GATE DOES NOT CLAIM, said here so the name is not read wider than
// the measurement:
//   · it does not claim the 53 concepts are CLINICALLY right for their fields.
//     That is a physician's judgement and is exactly what confirmation is for.
//     It claims they are the ones the compiler already decides in the MODEL
//     path, now also available when the model is down.
//   · it does not weaken `MAPPINGS_NOT_READY` by one field. Every mapping the
//     fallback emits is still `needs_confirmation`, and the arm below fails if
//     that ever stops being true.
// ============================================================================

import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { ingestDocxTemplateSource } from '../ingest-docx-source';
import {
  compilerDecidedConcept,
  fallbackSemanticMappings,
  tableCellsByRow,
} from '../semantic-mapping';
import {
  compilerDecidableConcepts,
  isRegisteredConcept,
  VEIN_GRID_CONCEPTS,
} from '../concept-registry';
import type { TemplateDocIR } from '../ir';

const REPO_ROOT = path.resolve(process.cwd(), '../..');
const WM_IOV_PATH = path.join(REPO_ROOT, 'WM IOV Template.docx');

/** The real customer form — the only real-world template this work has. */
async function realForm(): Promise<TemplateDocIR> {
  const bytes = new Uint8Array(readFileSync(WM_IOV_PATH));
  return (await ingestDocxTemplateSource(bytes)).ir;
}

describe('F5 — the fallback carries the compiler-decided concepts', () => {
  it('POSITIVE CONTROL: the instrument discriminates before any count is read', async () => {
    const ir = await realForm();
    // Non-vacuity: a form that compiled to nothing would satisfy every filter
    // below while checking nothing at all.
    expect(ir.fields.length).toBe(80);
    expect(isRegisteredConcept('measurement.diameter')).toBe(true);
    expect(isRegisteredConcept('not.a.real.concept')).toBe(false);
  });

  it('partitions the real form into 5 manual / 53 proposed / 22 still-unproposed', async () => {
    const ir = await realForm();
    const mappings = fallbackSemanticMappings(ir);
    expect(mappings.length).toBe(ir.fields.length);

    // EVERY bucket named, and the total reconciled — anything that does not fit
    // a named bucket is the finding.
    const buckets = { manual: 0, proposed: 0, unproposed: 0 } as Record<string, number>;
    for (const m of mappings) {
      if (m.sourceType === 'manual') buckets.manual += 1;
      else if (m.clinicalConcept !== null) buckets.proposed += 1;
      else buckets.unproposed += 1;
    }
    expect(buckets).toEqual({ manual: 5, proposed: 53, unproposed: 22 });
    expect(buckets.manual + buckets.proposed + buckets.unproposed).toBe(80);
  });

  it('BOTH DIRECTIONS: it proposes the 53 and it does NOT invent the 22', async () => {
    // A change that concepted every field would satisfy a one-sided
    // "concepts are proposed" assertion and be strictly worse than the defect:
    // it would put a guessed concept on a dropdown whose answer only the
    // physician knows. The unproposed side is pinned for that reason.
    const ir = await realForm();
    const mappings = fallbackSemanticMappings(ir);
    const withConcept = mappings.filter((m) => m.clinicalConcept !== null);
    const withoutConcept = mappings.filter(
      (m) => m.clinicalConcept === null && m.sourceType !== 'manual',
    );
    expect(withConcept.length).toBeGreaterThan(0);
    expect(withoutConcept.length).toBeGreaterThan(0);
    // The unproposed remainder is exactly the enumerated-dropdown class whose
    // options are protocol language no extractor emits.
    for (const m of withoutConcept) {
      expect(m.sourceType, `${m.fieldId} should be an enumerated pick`).toBe(
        'verified_note_selection',
      );
    }
  });

  it('every proposed concept is in the registry — asserted THROUGH the function', async () => {
    // Text presence is not membership: this reads the emitted mapping objects
    // and asks the registry, never the source file.
    const ir = await realForm();
    for (const m of fallbackSemanticMappings(ir)) {
      if (m.clinicalConcept === null) continue;
      expect(
        isRegisteredConcept(m.clinicalConcept),
        `${m.fieldId} carries off-registry concept ${m.clinicalConcept}`,
      ).toBe(true);
    }
  });

  it('ONE IMPLEMENTATION: the fallback agrees with the shared classifier field-for-field', async () => {
    const ir = await realForm();
    const cellsByRow = tableCellsByRow(ir.fields);
    const byId = new Map(fallbackSemanticMappings(ir).map((m) => [m.fieldId, m]));
    let agreed = 0;
    for (const field of ir.fields) {
      const rowKey = `${field.tableId ?? ''}#${field.rendererBinding?.rowIndex ?? -1}`;
      const decided = compilerDecidedConcept(field, cellsByRow.get(rowKey) ?? []);
      const expected = decided && isRegisteredConcept(decided) ? decided : null;
      expect(byId.get(field.fieldId)?.clinicalConcept, field.fieldId).toBe(expected);
      agreed += 1;
    }
    // A loop that iterated nothing would pass every assertion inside it.
    expect(agreed).toBe(80);
  });

  it('THE GATE DOES NOT MOVE: every fallback mapping is still needs_confirmation', async () => {
    // This is the arm that makes the change safe. A proposed concept is a
    // PROPOSAL. If a future edit copies the model path's conditional status
    // into the fallback, a compiler-decided field would arrive `recognized`
    // and `MAPPINGS_NOT_READY` would stop being the wall it is meant to be.
    const ir = await realForm();
    const mappings = fallbackSemanticMappings(ir);
    for (const m of mappings) {
      expect(m.status, `${m.fieldId} must stay unconfirmed`).toBe('needs_confirmation');
    }
    expect(mappings.filter((m) => m.status === 'needs_confirmation').length).toBe(80);
    // And nothing may carry a practice default — the practice-default law.
    expect(mappings.filter((m) => m.practiceDefault !== null).length).toBe(0);
  });

  it('AUTHOR-TIME INVARIANT: every concept the compiler can decide is registry-legal', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE A MUTATION PROOF FOUND ITS OWN BLIND SPOT.
    // Removing the fallback's registry check left all seven arms green: every
    // value `compilerDecidedConcept` can return is already registry-legal, so
    // the runtime check is unreachable on any fixture. The invariant that makes
    // it unreachable is therefore asserted directly. Add a `CONCEPT_LABEL_OVERRIDES`
    // entry naming a concept the extractor never emits and this reddens at
    // author time — instead of that field going permanently unfillable, which
    // is precisely the failure the registry was built for.
    const decidable = compilerDecidableConcepts();
    expect(decidable.length).toBeGreaterThan(0); // non-vacuity
    for (const concept of decidable) {
      expect(
        isRegisteredConcept(concept),
        `the compiler can decide "${concept}", which is NOT in the extractor's registry — ` +
          'any field it lands on would be permanently unfillable',
      ).toBe(true);
    }
    // And the enumeration must actually cover what the grid emits, not a stale copy.
    expect(decidable).toContain(VEIN_GRID_CONCEPTS.reflux);
    expect(decidable).toContain(VEIN_GRID_CONCEPTS.diameter);
  });

  it('a field whose concept is proposed also carries that concept’s registry synonyms', async () => {
    const ir = await realForm();
    const mappings = fallbackSemanticMappings(ir);
    const diameter = mappings.find((m) => m.clinicalConcept === 'measurement.diameter');
    expect(diameter, 'the real form has diameter cells').toBeDefined();
    expect(diameter!.approvedSynonyms.length).toBeGreaterThan(0);
    // A field with no concept must carry no synonyms — synonyms without a
    // concept are a matcher with nothing to match against.
    for (const m of mappings) {
      if (m.clinicalConcept === null) {
        expect(m.approvedSynonyms, `${m.fieldId}`).toEqual([]);
      }
    }
  });
});
