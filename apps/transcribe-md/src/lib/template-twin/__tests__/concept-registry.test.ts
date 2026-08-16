// ============================================================================
// STAGE 4 — one vocabulary, both sides.
// ----------------------------------------------------------------------------
// The proposer invented a concept per field (test.venous_duplex.gsv_sfj_diameter).
// L3 never emits strings like that, and factSatisfiesMapping demands the fact's
// concept BE the mapping's concept or an approved synonym — so no fact could
// match any cell, permanently. That is how filledCount=0 survived four sessions
// of downstream fixes.
//
// Intersection is now true BY CONSTRUCTION rather than by loosening anything:
// the proposer may only select concepts the extractor actually emits.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  conceptOverrideFor,
  veinGridCellConcept,
  isRegisteredConcept,
  synonymsFor,
  REGISTRY_CONCEPTS,
} from '../concept-registry';
import { compilerDecidedConcept } from '../semantic-mapping';

describe('registry membership', () => {
  it('accepts every concept observed in a real extraction run', () => {
    // Verbatim from the vocabulary dump.
    for (const c of [
      'measurement.diameter',
      'measurement.reflux_time',
      'assessment',
      'exam.vascular',
      'test.name',
      'test.bilateral_lower_extremity_venous_duplex_reflux_study.result',
    ]) {
      expect(isRegisteredConcept(c), `${c} should be registered`).toBe(true);
    }
  });

  it('REJECTS the invented per-field concepts that caused the outage', () => {
    for (const c of [
      'test.venous_duplex.gsv_sfj_diameter',
      'test.venous_duplex.gsv_sfj_reflux_time',
      'test.venous_duplex.gsv_sfj.reflux_time_ms',
    ]) {
      expect(isRegisteredConcept(c), `${c} must NOT be registered`).toBe(false);
    }
  });

  it('holds no anatomy in any concept — anatomy is fact data', () => {
    // One concept serves twenty-six template rows precisely because it does not
    // name a vein. If this ever fails, the outage is being recreated.
    for (const c of REGISTRY_CONCEPTS) {
      expect(c, `${c} bakes anatomy into a concept`).not.toMatch(
        /gsv|ssv|aagsv|pagsv|sfj|spj|thigh|knee|calf/,
      );
    }
  });

  it('supplies synonyms from the registry, not the model', () => {
    expect(synonymsFor('measurement.reflux_time')).toContain('measurement.reflux');
    expect(synonymsFor('measurement.diameter').length).toBeGreaterThan(0);
    expect(synonymsFor('not.a.concept')).toEqual([]);
  });
});

describe('proposer wiring', () => {
  const src = () => {
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    return readFileSync(join(__dirname, '..', 'semantic-mapping', 'index.ts'), 'utf-8');
  };

  it('nulls an off-registry concept instead of persisting it', () => {
    // Whatever the concept's origin — model proposal or compiler override — it
    // reaches the mapping only through the registry check.
    expect(src()).toMatch(
      /const proposedConcept = candidate && isRegisteredConcept\(candidate\) \? candidate : null/,
    );
    expect(src()).toMatch(/clinicalConcept: proposedConcept,/);
  });

  it('an off-registry mapping cannot come back as recognised', () => {
    expect(src()).toMatch(/status:\s*\n?\s*proposedConcept === null \|\|/);
  });

  it('a compiler concept override still has to be in the registry', () => {
    // The override is the compiler's label talking, not an exemption: an
    // override naming an unregistered concept nulls exactly like a bad proposal.
    //
    // ⚠️ THIS USED TO PIN THE INLINE EXPRESSION BY SOURCE TEXT. The precedence
    // now lives in `compilerDecidedConcept`, so it is asserted by BEHAVIOUR —
    // which is what the arm was always trying to say, and it survives the next
    // refactor instead of reddening on it. The one remaining source pin is the
    // line where the compiler's answer meets the model's, because no function
    // exposes that junction.
    expect(src()).toMatch(
      /compilerDecidedConcept\(field, rowCells\) \?\? mapping\.clinicalConcept/,
    );
    expect(conceptOverrideFor('SIDE OF EXAM: Choose an item.')).toBe('test.name');
    expect(isRegisteredConcept(conceptOverrideFor('SIDE OF EXAM: Choose an item.')!)).toBe(true);
    expect(conceptOverrideFor('GSV at the SFJ')).toBeNull();
  });

  it('reports off-registry proposals visibly at PROPOSAL time', () => {
    // Not discovered later at certification, where it looked like missing evidence.
    expect(src()).toContain('off-registry or unconcepted');
  });
});

// ============================================================================
// THE GRID DEFINES ITS OWN COLUMNS — the half-mapped table.
// ----------------------------------------------------------------------------
// The reflux cell names itself; the diameter cell is labelled with the VEIN, so
// it is not self-describing and the model chose per field. It chose
// measurement.diameter for the right leg and test.vascular_ultrasound.result
// for the left — both registry-valid, so nothing rejected it. Every right
// diameter filled and every left diameter came back "no supporting fact", from
// an encounter that dictated both legs equally, with nothing to show that the
// two halves of one grid had been read as different kinds of thing.
// ============================================================================

describe('vein grid columns', () => {
  const row = (over: Partial<Parameters<typeof veinGridCellConcept>[0]> = {}) =>
    veinGridCellConcept({
      originalLabel: 'GSV at the SFJ',
      isReflux: false,
      rowHasRefluxCell: true,
      isRowLabelCell: true,
      ...over,
    });

  it('the reflux cell is reflux time', () => {
    expect(row({ originalLabel: 'REFLUX TIME (ms)', isReflux: true, isRowLabelCell: false })).toBe(
      'measurement.reflux_time',
    );
  });

  it('the vein-labelled cell in the same row is the diameter', () => {
    expect(row()).toBe('measurement.diameter');
  });

  it('says nothing about a row that has no reflux cell', () => {
    // A different table shape gets no opinion from here; the model proposes.
    expect(row({ rowHasRefluxCell: false })).toBeNull();
  });

  it('says nothing about a third cell in a vein row', () => {
    expect(row({ isRowLabelCell: false })).toBeNull();
  });

  it('both concepts are in the registry', () => {
    expect(isRegisteredConcept('measurement.diameter')).toBe(true);
    expect(isRegisteredConcept('measurement.reflux_time')).toBe(true);
  });

  it('the STRUCTURE outranks the label override, by behaviour', () => {
    // Asserted through `compilerDecidedConcept` rather than by grepping the
    // expression: a reflux cell whose label ALSO matches an override pattern
    // still resolves as reflux time, which is the precedence claim itself.
    const refluxCell = {
      originalLabel: 'SIDE OF EXAM REFLUX TIME (ms)',
      labelSource: 'left_cell',
      tableId: 't1',
      rendererBinding: { bindingType: 'table_cell', rowIndex: 0 },
    } as unknown as Parameters<typeof compilerDecidedConcept>[0];
    // The same label through the OVERRIDE alone would say `test.name` …
    expect(conceptOverrideFor('SIDE OF EXAM REFLUX TIME (ms)')).toBe('test.name');
    // … and the structure wins, because the row carries a reflux cell.
    expect(compilerDecidedConcept(refluxCell, [refluxCell])).toBe('measurement.reflux_time');
  });

  it('says nothing when the document decides nothing — the model still proposes', () => {
    const plain = {
      originalLabel: 'Some free-text field nobody recognises',
      labelSource: 'paragraph',
      rendererBinding: { bindingType: 'paragraph' },
    } as unknown as Parameters<typeof compilerDecidedConcept>[0];
    expect(compilerDecidedConcept(plain, [])).toBeNull();
  });
});
