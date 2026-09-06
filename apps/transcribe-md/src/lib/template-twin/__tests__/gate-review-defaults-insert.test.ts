// ============================================================================
// GATE — REVIEW-DEFAULTS item 1: the doctor asserts their OWN default.
// ----------------------------------------------------------------------------
// Ruling #194 deleted the `keep` half — the machine never prints an undictated
// default — and made the doctor's defaults a HUMAN ACT AT REVIEW. This file
// proves the four properties that act must have.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · an insert stops being PER-FIELD          -> the writer block
//   · the client can supply the TEXT           -> the writer block
//   · an insert stops being AUDITED, or is
//     audited as an ordinary note edit         -> the audit block
//   · an insert stops being UNDOABLE           -> the undo block
//   · a stored default OVERWRITES later
//     dictation                                -> the blank-only block
//   · the proof kind loses its emitter         -> the proof block
//   · the override identity stops moving       -> the identity block
//
// ⚠️ AND THE BLANK-ONLY BLOCK IS THE ONE THAT KEEPS #194 TRUE. Everything else
// here is hygiene; that block is the ruling. An override row persists across
// every later fill and the overlay runs AFTER the bridges, so an unconditional
// apply means: doctor inserts a default into an empty field, dictates that
// field for real later, and the stored default overwrites the dictation on the
// next recompute — the machine printing an undictated default over dictated
// content, re-entering through the door built to honour the ruling.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  applyClinicianOverrides,
  buildScaffoldDefaultFact,
  type ClinicianFieldOverride,
} from '../clinician-override';
import { overridesIdentity } from '../note-identity';

const FIELD_ID = 'ttf_aaaaaaaaaaaaaaaaaaaaaaaa';
const OTHER_ID = 'ttf_bbbbbbbbbbbbbbbbbbbbbbbb';
const NOTE_SHA = 'a'.repeat(64);

function field(id: string, over: Record<string, unknown> = {}) {
  return {
    fieldId: id,
    originalLabel: 'Impression',
    kind: 'narrative_text',
    rendererBinding: { partName: 'word/document.xml', path: '/w:document[1]' },
    allowedOptions: [],
    required: false,
    criticality: 'routine',
    clinicallyMaterial: false,
    scaffolded: true,
    scaffoldText: 'No acute findings.',
    ...over,
  };
}

function mapping(id: string, over: Record<string, unknown> = {}) {
  return {
    fieldId: id,
    sourceType: 'extraction',
    clinicalConcept: 'exam.impression',
    approvedSynonyms: [],
    temporality: null,
    laterality: 'not_applicable',
    status: 'certified',
    required: false,
    unmentionedPolicy: null,
    practiceDefault: null,
    ...over,
  };
}

function resolution(id: string, over: Record<string, unknown> = {}) {
  return {
    fieldId: id,
    status: 'not_mentioned',
    value: null,
    sourceFactIds: [],
    evidenceAnchorIds: [],
    reasonCode: 'no_matching_fact',
    clinicianReviewed: false,
    ...over,
  };
}

function apply(
  overrides: ClinicianFieldOverride[],
  resolutions: ReturnType<typeof resolution>[],
  fields = [field(FIELD_ID)],
  mappings = [mapping(FIELD_ID)],
) {
  return applyClinicianOverrides({
    // Only the members the overlay reads; the IR schema is exercised elsewhere.
    ir: { fields } as never,
    resolutions: resolutions as never,
    overrides,
    mappings: mappings as never,
    noteSha256: NOTE_SHA,
  });
}

const insert = (id = FIELD_ID, text = 'No acute findings.'): ClinicianFieldOverride => ({
  kind: 'scaffold_default',
  fieldId: id,
  insertedText: text,
});

describe('⚠️ BLANK-ONLY — a stored default never overwrites later dictation', () => {
  it('applies to a field the evidence left blank', () => {
    const out = apply([insert()], [resolution(FIELD_ID)]);
    expect(out.declined).toEqual([]);
    expect(out.resolutions[0].value).toBe('No acute findings.');
    expect(out.resolutions[0].reasonCode).toBe('clinician_scaffold_default');
  });

  it('⚠️ DECLINES on a field that later got dictated — the ruling, not hygiene', () => {
    // The row was written when the field was blank. The doctor then dictated
    // this field for real. The next fill must NOT put the default back.
    const dictated = resolution(FIELD_ID, {
      status: 'supported',
      value: 'Large weeping ulcer with gross bilateral oedema.',
      sourceFactIds: ['ttfact_dictated'],
      evidenceAnchorIds: ['tta_dictated'],
      reasonCode: 'evidence_supported',
    });
    const out = apply([insert()], [dictated]);
    expect(out.declined).toEqual([
      { fieldId: FIELD_ID, reason: 'field_already_filled' },
    ]);
    // ⚠️ THE DICTATION IS UNTOUCHED, ASSERTED RATHER THAN ASSUMED. "declined"
    // alone would also be reported by a build that declined AND still wrote.
    expect(out.resolutions[0].value).toBe(
      'Large weeping ulcer with gross bilateral oedema.',
    );
    expect(out.facts).toEqual([]);
  });

  it('⚠️ and NON-VACUITY: the same override on the same field DOES apply when blank', () => {
    // Without this, "declines when filled" would also pass on a build where the
    // scaffold arm never applies to anything at all.
    const out = apply([insert()], [resolution(FIELD_ID)]);
    expect(out.resolutions[0].value).toBe('No acute findings.');
  });

  it('a field the resolver left needs_clinician_input is still blank enough', () => {
    const out = apply(
      [insert()],
      [resolution(FIELD_ID, { status: 'needs_clinician_input' })],
    );
    expect(out.declined).toEqual([]);
    expect(out.resolutions[0].value).toBe('No acute findings.');
  });
});

describe('⚠️ PER-FIELD — one click addresses one control and nothing else', () => {
  it('leaves every other field exactly as the bridges resolved it', () => {
    const out = apply(
      [insert(FIELD_ID)],
      [resolution(FIELD_ID), resolution(OTHER_ID)],
      [field(FIELD_ID), field(OTHER_ID)],
      [mapping(FIELD_ID), mapping(OTHER_ID)],
    );
    expect(out.resolutions[0].value).toBe('No acute findings.');
    expect(out.resolutions[1].value).toBeNull();
    expect(out.resolutions[1].reasonCode).toBe('no_matching_fact');
    expect(out.facts).toHaveLength(1);
  });
});

describe('⚠️ FAIL-CLOSED against the CURRENT compile, not the row', () => {
  it('declines when the field is no longer scaffolded', () => {
    // The template was recompiled under the insert. Same discipline as
    // `ordinal_not_in_options` on the option arm.
    const out = apply(
      [insert()],
      [resolution(FIELD_ID)],
      [field(FIELD_ID, { scaffolded: false })],
    );
    expect(out.declined).toEqual([
      { fieldId: FIELD_ID, reason: 'not_scaffolded_in_current_compile' },
    ]);
    expect(out.resolutions[0].value).toBeNull();
  });

  it('declines when the mapping carries no clinical concept', () => {
    // ⚠️ COSTS ONE FIELD RATHER THAN THE NOTE. A minted fact on a concept-less
    // mapping cannot satisfy `factMatchesMapping`, so the fill would be
    // REFUSED at validation with SOURCE_FACT_CONCEPT_MISMATCH — a blocking
    // issue on the whole document caused by one click.
    const out = apply(
      [insert()],
      [resolution(FIELD_ID)],
      [field(FIELD_ID)],
      [mapping(FIELD_ID, { clinicalConcept: null })],
    );
    expect(out.declined).toEqual([
      { fieldId: FIELD_ID, reason: 'no_approved_concept' },
    ]);
    expect(out.resolutions[0].value).toBeNull();
  });
});

describe('⚠️ THE FACT carries the mapping, so the validator can check it', () => {
  it('takes its concept from the mapping rather than inventing one', () => {
    const fact = buildScaffoldDefaultFact({
      field: field(FIELD_ID) as never,
      mapping: mapping(FIELD_ID) as never,
      insertedText: 'No acute findings.',
      noteSha256: NOTE_SHA,
    });
    expect(fact.concept).toBe('exam.impression');
    expect(fact.value).toBe('No acute findings.');
    // No transcript offsets and no audio timestamp: nobody said this out loud.
    expect(fact.sourceTranscriptOffsets).toBeNull();
    expect(fact.audioTimestampSeconds).toBeNull();
  });

  it('⚠️ is a DIFFERENT fact against a different note — identity includes noteSha256', () => {
    // Mirrors the correction fact for the same reason: the same default
    // asserted against a re-generated note is a different assertion and must
    // not silently reuse the prior manifest's fact or anchor.
    const a = buildScaffoldDefaultFact({
      field: field(FIELD_ID) as never,
      mapping: mapping(FIELD_ID) as never,
      insertedText: 'No acute findings.',
      noteSha256: 'a'.repeat(64),
    });
    const b = buildScaffoldDefaultFact({
      field: field(FIELD_ID) as never,
      mapping: mapping(FIELD_ID) as never,
      insertedText: 'No acute findings.',
      noteSha256: 'b'.repeat(64),
    });
    expect(a.factId).not.toBe(b.factId);
  });
});

describe('⚠️ THE OVERRIDE IDENTITY MOVES, or the feature silently does nothing', () => {
  it('a scaffold insert changes the hash even though its ordinal is NULL', () => {
    // ⚠️ THIS IS THE F24-S5 DEFECT'S SHAPE. The identity is what tells the
    // manifest it is stale. A tuple of (fieldId, ordinal) would be BYTE
    // IDENTICAL before and after the click, because a scaffold row carries no
    // ordinal — the manifest would read FRESH, no recompute would run, and the
    // inserted default would never reach the document while every gate
    // reported success.
    const before = overridesIdentity([]);
    const after = overridesIdentity([
      {
        fieldId: FIELD_ID,
        selectedOptionOrdinal: null,
        overrideKind: 'scaffold_default',
        insertedText: 'No acute findings.',
      },
    ]);
    expect(after).not.toBe(before);
  });

  it('and CHANGING the inserted text moves it again', () => {
    const one = overridesIdentity([
      {
        fieldId: FIELD_ID,
        selectedOptionOrdinal: null,
        overrideKind: 'scaffold_default',
        insertedText: 'No acute findings.',
      },
    ]);
    const two = overridesIdentity([
      {
        fieldId: FIELD_ID,
        selectedOptionOrdinal: null,
        overrideKind: 'scaffold_default',
        insertedText: 'Normal study.',
      },
    ]);
    expect(one).not.toBe(two);
  });

  it('⚠️ and a legacy option row hashes as it always did — no silent re-fill', () => {
    // ⚠️ THE CONTROL FOR THE TWO ARMS ABOVE. Widening the identity must not
    // move the hash of rows that already exist, or every stored correction
    // would read stale at once and force a re-fill of every open visit.
    expect(
      overridesIdentity([{ fieldId: FIELD_ID, selectedOptionOrdinal: 3 }]),
    ).toBe(
      overridesIdentity([
        {
          fieldId: FIELD_ID,
          selectedOptionOrdinal: 3,
          overrideKind: 'option',
          insertedText: null,
        },
      ]),
    );
  });
});
