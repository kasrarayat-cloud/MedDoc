// ============================================================================
// sourceType must survive write -> read. THE TEST THAT WOULD HAVE CAUGHT IT.
// ----------------------------------------------------------------------------
// sourceType was added to the Zod schema and the proposer, but there was no
// COLUMN. Every mapping round-tripped through the database and came back as
// 'extraction', so the manual carve-outs in the certification gate were inert
// code — and two ten-minute certification runs were burned before anyone
// checked the persistence path.
//
// These assertions trace the field end-to-end statically: schema -> persisted
// column -> update payload -> read projection. A break anywhere in that chain
// makes the carve-outs silently dead again, which looks exactly like a
// certification bug and is not one.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { SemanticMappingSchema } from '../ir';
import { classifyFieldSource } from '../concept-registry';
import { fallbackSemanticMappings } from '../semantic-mapping';

const read = (rel: string) => {
  const { readFileSync } = require('node:fs') as typeof import('node:fs');
  const { join } = require('node:path') as typeof import('node:path');
  return readFileSync(join(__dirname, '..', rel), 'utf-8');
};
const readRepo = (rel: string) => {
  const { readFileSync } = require('node:fs') as typeof import('node:fs');
  const { join } = require('node:path') as typeof import('node:path');
  return readFileSync(join(__dirname, '..', '..', '..', '..', '..', '..', rel), 'utf-8');
};

const BASE = {
  fieldId: `ttf_${'a'.repeat(24)}`,
  clinicalConcept: null,
  expectedDataType: 'single_select' as const,
  polarityBehavior: 'value_only' as const,
  temporality: 'current' as const,
  laterality: 'optional' as const,
  unitPolicy: 'not_applicable' as const,
  approvedSynonyms: [],
  required: false,
  blankPolicy: 'blank' as const,
  unknownPolicy: 'blank' as const,
  practiceDefault: null,
  status: 'certified' as const,
};

describe('schema', () => {
  it('accepts and preserves a manual classification', () => {
    const parsed = SemanticMappingSchema.parse({ ...BASE, sourceType: 'manual' });
    expect(parsed.sourceType).toBe('manual');
  });

  it('defaults to extraction when absent', () => {
    // ⚠️ THE DEFAULT IS A SAFETY NET FOR THE FILL PATH'S RE-PARSES, NOT A
    // CLASSIFICATION. Removing it was evaluated on 2026-08-15 and declined on
    // evidence — the reason is written at the default in `ir.ts`. What changed
    // instead: every CONSTRUCTING site now classifies explicitly, guarded by
    // `gate-source-type-explicit.test.ts`. This arm pins the net, not a policy.
    const parsed = SemanticMappingSchema.parse({ ...BASE });
    expect(parsed.sourceType).toBe('extraction');
  });

  it('a manual mapping is valid with a NULL concept', () => {
    // The whole point: nothing can know the technologist on shift, so there is
    // no evidence to cite and no concept to carry.
    const parsed = SemanticMappingSchema.parse({
      ...BASE,
      sourceType: 'manual',
      clinicalConcept: null,
    });
    expect(parsed.clinicalConcept).toBeNull();
  });
});

describe('classification', () => {
  it.each([
    ['ULTRASOUND TECHNOLOGIST: Choose an item.', 'manual'],
    // ⚠️ #247 — WAS 'manual', AND THE CHANGE IS THE RULING. The referring
    // clinician is DICTATED ("referred by Dr. Ramirez"), so it is an ordinary
    // extraction with an L3 concept behind it rather than a blank a human
    // types. `MANUAL_LABEL_PATTERNS` keeps machine / location / address, which
    // nobody says aloud.
    ['REFERRING PHYSICIAN: Choose an item.', 'extraction'],
    // The owner's ACTUAL label, which the old `/referring\s+physician/i`
    // pattern never matched — the rule missed the one field it was written for.
    ['Referring MD', 'extraction'],
    // #247 — record-derived, decided by the label, first arm in the classifier.
    ['Patient', 'visit_metadata'],
    ['Age', 'visit_metadata'],
    // ⚠️ NON-VACUITY for the two above: neither pattern may reach into prose.
    ['Age of onset', 'extraction'],
    ['Patient reports intermittent heartburn', 'extraction'],
    ['MACHINE: Choose an item.', 'manual'],
    ['LOCATION: Choose an item.', 'manual'],
    ['Address', 'manual'],
    ['GSV at the SFJ', 'extraction'],
    ['SIDE OF EXAM: Choose an item.', 'extraction'],
    ['CLINICAL INDICATIONS: Choose an item.', 'extraction'],
  ])('%s -> %s', (label, want) => {
    expect(classifyFieldSource(label)).toBe(want);
  });
});

describe('the persistence chain — every link', () => {
  it('1. the COLUMN exists in the prisma model', () => {
    const schema = readRepo('packages/db/prisma/schema.prisma');
    const model = /model TemplateTwinSemanticMapping \{[\s\S]*?\n\}/.exec(schema)?.[0] ?? '';
    expect(model, 'no sourceType column — classification is lost on write').toMatch(
      /sourceType\s+String\s+@default\("extraction"\)/,
    );
  });

  it('2a. the CREATE payload writes it', () => {
    // The link this test originally missed. Classification happens at proposal
    // time; if the first write drops it, every row is born 'extraction' and the
    // carve-outs never fire no matter how correct the update path is.
    const src = read('create-draft.ts');
    expect(src, 'draft creation does not persist sourceType').toContain(
      'sourceType: mapping.sourceType,',
    );
  });

  it('2b. the UPDATE payload writes it', () => {
    const src = read('certification-lifecycle.ts');
    expect(src, 'updateTemplateTwinMappings does not persist sourceType').toContain(
      'sourceType: mapping.sourceType,',
    );
  });

  it('3. the READ projection selects and parses it', () => {
    const src = read('certification-lifecycle.ts');
    expect(src).toContain('sourceType: true,');
    expect(src, 'fromPersistedMapping drops sourceType — it reads back as extraction').toContain(
      'sourceType: row.sourceType,',
    );
  });

  it('4. the WORKSPACE projection carries it to the review surface', () => {
    const src = read('workspace-read.ts');
    expect(src).toContain('sourceType: true,');
    expect(src).toContain('sourceType: row.sourceType,');
  });

  it('4b. EVERY mapping projection carries it', () => {
    // Projections are the failure mode. Each module selects its own mapping
    // columns, and one that omits sourceType silently reads every row back as
    // 'extraction'. Two of them did, and the second surfaced as
    // "Mappings changed after the page loaded" — the two projections hashed to
    // different shas because one of them was reading a field that wasn't there.
    for (const file of [
      'certification-lifecycle.ts',
      'workspace-read.ts',
      'synthetic-test.ts',
      'fill-engine.ts',
      // 'signing-gate.ts' removed 2026-07-28 with the module: it had zero
      // production callers, so the projection it carried guarded nothing.
    ]) {
      const src = read(file);
      const selects = src.split('polarityBehavior: true').length - 1;
      const carried = src.split('sourceType: true,').length - 1;
      expect(carried, `${file} has ${selects} mapping select(s) but only ${carried} carry sourceType`).toBe(
        selects,
      );
    }
  });

  it('5. both gate checks honour the manual carve-out', () => {
    const src = read('certification-lifecycle.ts');
    // fieldsReady, and the mapping-update validation.
    expect(src).toContain("mapping.sourceType === 'manual'");
    expect(src).toContain("mapping.sourceType !== 'manual'");
  });
});

// ============================================================================
// ⚠️ THE FALLBACK PATH CLASSIFIES TOO — ATTEMPT-PROVED, NOT ASSUMED.
//
// `classifyFieldSource` was called ONLY by the model proposer. When the vendor
// is unreachable — which is the QA stack's PERMANENT state, and any production
// outage — `fallbackSemanticMappings` ran instead and omitted the field, so the
// schema default labelled EVERY field `extraction`.
//
// Measured on a real compiled twin of the customer form (QA, 2026-08-15):
// 80 of 80 mappings came back `extraction`, on a document whose dropdowns
// should be `verified_note_selection`. `MAPPINGS_NOT_READY` demands a concept
// for every non-manual field, so that mislabel makes certification
// unsatisfiable for fields that never needed a concept at all.
//
// These arms run the FALLBACK — the path that was wrong — not the classifier
// in isolation. A unit test of `classifyFieldSource` alone was already green
// throughout the defect.
// ============================================================================
describe('fallbackSemanticMappings classifies like the model path', () => {
  const field = (over: Record<string, unknown> = {}) => ({
    fieldId: `ttf_${'b'.repeat(24)}`,
    originalLabel: 'Study Type',
    labelSource: 'content_control',
    kind: 'single_select',
    allowedOptions: [
      { ordinal: 0, displayText: 'Bilateral Detailed', value: 'bilateral_detailed' },
      { ordinal: 1, displayText: 'Unilateral', value: 'unilateral' },
    ],
    required: false,
    unknownPolicy: 'blank',
    displayOrder: 0,
    ...over,
  });

  it('AN ENUMERATED DROPDOWN IS verified_note_selection, THROUGH THE FALLBACK', () => {
    const [mapping] = fallbackSemanticMappings({ fields: [field()] as never });
    expect(
      mapping!.sourceType,
      'the fallback labelled an enumerated dropdown `extraction` — its value comes ' +
        'from the note\'s constrained pick, and classifying it as extraction is what ' +
        '"left fourteen of them permanently blank on every real visit"',
    ).toBe('verified_note_selection');
  });

  it('A MANUAL LABEL IS manual, THROUGH THE FALLBACK — and manual needs NO concept', () => {
    const [mapping] = fallbackSemanticMappings({
      fields: [field({ originalLabel: 'Ultrasound Technologist', kind: 'narrative_text', allowedOptions: [] })] as never,
    });
    expect(mapping!.sourceType).toBe('manual');
    // The gate's carve-out: a manual field is ready when CONFIRMED, with a null
    // concept, because nothing dictates who was on shift. Mislabelled
    // `extraction`, it would demand a concept that cannot exist.
    expect(mapping!.clinicalConcept).toBeNull();
  });

  it('a plain free-text field is still extraction — the fix is not a blanket relabel', () => {
    const [mapping] = fallbackSemanticMappings({
      fields: [field({ originalLabel: 'Findings', kind: 'narrative_text', allowedOptions: [] })] as never,
    });
    expect(mapping!.sourceType).toBe('extraction');
  });

  it('the fallback and the classifier AGREE — one classifier, two callers', () => {
    // If the two ever diverge, one of them grew its own copy.
    for (const f of [
      field(),
      field({ originalLabel: 'Ultrasound Technologist', kind: 'narrative_text', allowedOptions: [] }),
      field({ originalLabel: 'Findings', kind: 'narrative_text', allowedOptions: [] }),
    ]) {
      const [mapping] = fallbackSemanticMappings({ fields: [f] as never });
      expect(mapping!.sourceType).toBe(classifyFieldSource(f.originalLabel, f as never));
    }
  });
});
