// ============================================================================
// VERIFIED NOTE SELECTION — the provenance class, and its strict checks.
// ----------------------------------------------------------------------------
// A dropdown cannot cite an extracted fact. The template's options are protocol
// language — "Bilateral Detailed", "Swelling, Heaviness" — and no extractor
// emits facts that read like that, so requiring entailment left fourteen
// dropdowns blank on every real visit and the native export refused the document
// as incomplete, while the note had already selected every one of them
// correctly.
//
// So picks are routed to their own provenance class, the same move already made
// for manual fields. Its evidence is the product's existing chain — transcript
// -> constrained CHOICE_SLOT fill -> anchored-verifier grounding -> the doctor
// adopting the note — and this file pins the checks that make citing that chain
// safe. NOT ONE of them is a relaxation: each removes a way for a value to reach
// the document.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { EMPTY_SECTION_PLACEHOLDER } from '@/lib/soap-format';

import { bridgeChoiceSlotPicks } from '../picks-bridge';
import {
  buildVerifiedNoteSelectionFact,
  verifiedNoteSelectionFactId,
} from '../verified-note-selection';
import {
  EncounterFactSchema,
  type SemanticMapping,
  type TemplateDocIR,
} from '../ir';

const FIELD_ID = `ttf_${'a'.repeat(24)}`;

const MAPPING: SemanticMapping = {
  fieldId: FIELD_ID,
  sourceType: 'verified_note_selection',
  clinicalConcept: 'exam.vascular',
  expectedDataType: 'single_select',
  polarityBehavior: 'value_only',
  temporality: 'current',
  laterality: 'optional',
  unitPolicy: 'not_applicable',
  approvedSynonyms: [],
  required: false,
  blankPolicy: 'blank',
  unknownPolicy: 'blank',
  practiceDefault: null,
  status: 'certified',
} as SemanticMapping;

const OPTIONS = [
  { ordinal: 0, value: 'Bilateral Detailed', displayText: 'Bilateral Detailed' },
  { ordinal: 1, value: 'Bilateral Screening', displayText: 'Bilateral Screening' },
];

// The picks bridge reads ir.fields and nothing else, so this is the whole
// document as far as it is concerned. Parsing a full TemplateDocIR here would
// mean hand-building parts/nodes/tables/stats that no assertion looks at.
function ir(overrides: Record<string, unknown> = {}): TemplateDocIR {
  return {
    fields: [
      {
        fieldId: FIELD_ID,
        displayOrder: 0,
        originalLabel: 'SIDE OF EXAM',
        labelSource: 'preceding_text',
        kind: 'single_select',
        allowedOptions: OPTIONS,
        required: false,
        unknownPolicy: 'blank',
        detectionStatus: 'recognized',
        clinicallyMaterial: true,
        criticality: 'routine',
        rowPrototype: false,
        tableId: null,
        rendererBinding: {
          partName: 'word/document.xml',
          bindingType: 'content_control',
          path: '/w:document[1]/w:body[1]/w:sdt[1]',
          ordinal: 0,
          sdtId: '1',
          tag: null,
          alias: null,
          legacyName: null,
          tableIndex: null,
          rowIndex: null,
          cellIndex: null,
          rowLaterality: 'unknown',
        },
        ...overrides,
      },
    ],
  } as unknown as TemplateDocIR;
}

const MARKER = 'SIDE OF EXAM: {{one of: Bilateral Detailed | Bilateral Screening}}';

const run = (filledNote: string, mappings: SemanticMapping[] = [MAPPING]) =>
  bridgeChoiceSlotPicks({ ir: ir(), facts: [], mappings, markerText: MARKER, filledNote });

describe('the citation', () => {
  it('is the selection itself, with the note version in its identity', () => {
    const fact = buildVerifiedNoteSelectionFact({
      field: { fieldId: FIELD_ID },
      mapping: MAPPING,
      optionValue: 'Bilateral Detailed',
      markerOrdinal: 0,
      noteSha256: 'c'.repeat(64),
    });
    expect(fact.sourceType).toBe('verified_note_selection');
    expect(fact.value).toBe('Bilateral Detailed');
    expect(fact.concept).toBe('exam.vascular');
    expect(fact.evidenceAnchorIds).toHaveLength(1);
    // Parses as a real EncounterFact — the validator checks it like any other.
    expect(() => EncounterFactSchema.parse(fact)).not.toThrow();
  });

  it('a DIFFERENT note is a different selection — provenance never carries over', () => {
    const a = verifiedNoteSelectionFactId({
      fieldId: FIELD_ID, optionValue: 'Bilateral Detailed', markerOrdinal: 0,
      noteSha256: 'c'.repeat(64),
    });
    const b = verifiedNoteSelectionFactId({
      fieldId: FIELD_ID, optionValue: 'Bilateral Detailed', markerOrdinal: 0,
      noteSha256: 'd'.repeat(64),
    });
    expect(a).not.toBe(b);
  });

  it('a DIFFERENT pick is a different fact', () => {
    const a = verifiedNoteSelectionFactId({
      fieldId: FIELD_ID, optionValue: 'Bilateral Detailed', markerOrdinal: 0,
      noteSha256: 'c'.repeat(64),
    });
    const b = verifiedNoteSelectionFactId({
      fieldId: FIELD_ID, optionValue: 'Bilateral Screening', markerOrdinal: 0,
      noteSha256: 'c'.repeat(64),
    });
    expect(a).not.toBe(b);
  });

  it('records the marker and the note version, PHI-free', () => {
    const fact = buildVerifiedNoteSelectionFact({
      field: { fieldId: FIELD_ID }, mapping: MAPPING,
      optionValue: 'Bilateral Detailed', markerOrdinal: 3, noteSha256: 'c'.repeat(64),
    });
    expect(fact.evidenceQuote).toContain('marker #3');
    expect(fact.evidenceQuote).toContain('cccccccccccc');
    // The quote is the template's own language plus identifiers — never
    // narrative, so an audit row can carry it.
    expect(fact.evidenceQuote).not.toContain('patient');
  });
});

describe('the strict checks — none waived', () => {
  it('(a) fills on a VERBATIM option, and cites it', () => {
    const out = run('SIDE OF EXAM: Bilateral Detailed');
    const r = out.resolutions.find((x) => x.fieldId === FIELD_ID)!;
    expect(r.status).toBe('supported');
    expect(r.value).toBe('Bilateral Detailed');
    expect(r.selectedOptionOrdinal).toBe(0);
    expect(out.facts).toHaveLength(1);
    expect(r.sourceFactIds).toEqual([out.facts[0].factId]);
    expect(r.evidenceAnchorIds).toEqual([...out.facts[0].evidenceAnchorIds]);
  });

  it('(a) CANARY: a near-miss is not a selection', () => {
    // "Bilateral, detailed" is not an option. Fuzzy would be a value the doctor
    // never chose appearing in a signed document.
    const out = run('SIDE OF EXAM: Bilateral, detailed study');
    expect(out.resolutions.find((x) => x.fieldId === FIELD_ID)!.status).toBe('not_mentioned');
    expect(out.facts).toHaveLength(0);
  });

  it('(b) an omitted carrier line stays blank — nothing is invented', () => {
    const out = run('FINDINGS\n\nNothing about the side of exam here.');
    expect(out.resolutions.find((x) => x.fieldId === FIELD_ID)!.status).toBe('not_mentioned');
    expect(out.facts).toHaveLength(0);
  });

  it('(c) a pick inside a SET-ASIDE section is not adopted, so it does not fill', () => {
    const note = ['## Exam Metadata', EMPTY_SECTION_PLACEHOLDER, 'SIDE OF EXAM: Bilateral Detailed'].join('\n');
    const out = run(note);
    expect(out.resolutions.find((x) => x.fieldId === FIELD_ID)!.status).toBe('not_mentioned');
    expect(out.facts).toHaveLength(0);
  });

  it('(c) and the set-aside lane ENDS at the next heading', () => {
    // Otherwise one demoted section would silently suppress the whole rest of
    // the note — a different kind of wrong answer.
    const note = [
      '## Assessment', EMPTY_SECTION_PLACEHOLDER, 'demoted content',
      '## Exam Metadata', 'SIDE OF EXAM: Bilateral Detailed',
    ].join('\n');
    expect(run(note).resolutions.find((x) => x.fieldId === FIELD_ID)!.status).toBe('supported');
  });

  it('(d) no approved concept -> no citation -> blank', () => {
    const out = run('SIDE OF EXAM: Bilateral Detailed', [
      { ...MAPPING, clinicalConcept: null } as SemanticMapping,
    ]);
    expect(out.resolutions.find((x) => x.fieldId === FIELD_ID)!.status).toBe('not_mentioned');
    expect(out.facts).toHaveLength(0);
  });
});

describe('the resolver defers to the note', () => {
  it('a verified_note_selection field is not resolved from raw facts', () => {
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    const src = readFileSync(join(__dirname, '..', 'resolver', 'index.ts'), 'utf-8');
    expect(src).toContain("if (mapping.sourceType === 'verified_note_selection')");
    expect(src).toContain('awaiting_note_selection');
  });
});
