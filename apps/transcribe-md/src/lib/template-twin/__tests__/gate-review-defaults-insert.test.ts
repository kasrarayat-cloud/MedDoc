// ============================================================================
// GATE — REVIEW-DEFAULTS item 1: the doctor asserts their OWN default.
// ----------------------------------------------------------------------------
// Ruling #194 deleted the `keep` half — the machine never prints an undictated
// default — and made the doctor's defaults a HUMAN ACT AT REVIEW. This file
// proves the four properties that act must have.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL, stated first:
//   · a stored default OVERWRITES later
//     dictation                                -> the blank-only block
//   · a WITHHELD DENIAL is treated as blank    -> the denial block
//   · free text enters a constrained control   -> the field-kind block
//   · the offer and the write disagree         -> the shared-predicate block
//   · an insert stops being PER-FIELD          -> the per-field block
//   · a recompiled template stops failing closed -> the fail-closed block
//   · the minted fact stops carrying the mapping -> the fact block
//   · the override identity stops moving, or
//     starts moving for legacy option rows     -> the identity block
//
// ⚠️ AND WHAT THIS FILE DOES *NOT* MEASURE, SAID PLAINLY BECAUSE AN EARLIER
// HEADER CLAIMED OTHERWISE AND AN ADVERSARIAL PASS CAUGHT IT:
//   · THE AUDIT ROW. `logAudit` is not exercised here at all. That the insert
//     writes DEFAULT_INSERTED_BY_DOCTOR and the undo writes
//     DEFAULT_INSERT_UNDONE is asserted NOWHERE executable — the enum values
//     are pinned only by the Prisma enum, the TS union and the migration
//     agreeing. Named as a gap rather than implied as covered.
//   · THE UNDO's server half. Its CLIENT half is measured in the panel gate.
//   · "the client cannot supply the TEXT" is a STRUCTURAL guarantee, not a
//     tested one: `insertScaffoldDefaultAction(visitId, fieldId)` takes no text
//     parameter, so the type system forbids it and there is no input to test.
//
// ⚠️ AND THE BLANK-ONLY BLOCK IS THE ONE THAT KEEPS #194 TRUE. Everything else
// here is hygiene; that block is the ruling. An override row persists across
// every later fill and the overlay runs AFTER the bridges, so an unconditional
// apply means: doctor inserts a default into an empty field, dictates that
// field for real later, and the stored default overwrites the dictation on the
// next recompute — the machine printing an undictated default over dictated
// content, re-entering through the door built to honour the ruling.
// ============================================================================

import { createHash } from 'node:crypto';

import { describe, expect, it } from 'vitest';

import {
  applyClinicianOverrides,
  buildScaffoldDefaultFact,
  scaffoldDefaultOfferable,
  type ClinicianFieldOverride,
} from '../clinician-override';
import { overridesIdentity } from '../note-identity';
import type { OmitFieldView, OmitMappingView } from '../unmentioned-policy';

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
    // ⚠️ THE OMIT PREDICATE READS THESE THREE AND THIS HELPER DID NOT SUPPLY
    // THEM. A fixture thinner than the real shape makes the predicate false for
    // the WRONG reason, and the arm then passes while proving nothing.
    unknownPolicy: 'blank',
    detectionStatus: 'certified',
    rowPrototype: false,
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
    // ⚠️ SAME REASON. `expectedDataType` in particular is guard ONE of the
    // reachability ladder — `expectedDataTypeForFieldKind('narrative_text')` is
    // `'text'`, and anything else here (including `undefined`) short-circuits
    // the whole ladder before any of the interesting guards run.
    expectedDataType: 'text',
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
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

describe('⚠️ A WITHHELD DENIAL IS NOT BLANK — the defect the pass reproduced', () => {
  it('⚠️ DECLINES on denial_withheld, where the encounter said the OPPOSITE', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE FIRST VERSION SHIPPED WITHOUT IT AND WAS
    // WRONG. `isBlank` tested `value === null` BEFORE the status allow-list,
    // and FieldResolutionSchema's superRefine FORCES value === null on every
    // denial_withheld resolution — so the allow-list never ran.
    //
    // Measured consequence: an encounter dictated "There are no varicose veins"
    // resolved denial_withheld; the stored default applied; the document
    // asserted "Varicosities present in the great saphenous distribution"; the
    // FIELD_DENIAL_WITHHELD warning vanished; needsReview went 1 -> 0;
    // validation returned CLEAN; and sign-freeze would have frozen it in.
    //
    // WITHHOLDING IS A DECISION; ABSENCE IS NOT.
    const denied = resolution(FIELD_ID, {
      status: 'denial_withheld',
      value: null, // forced by the schema — which is exactly why it fooled the test
      sourceFactIds: ['ttfact_denied'],
      evidenceAnchorIds: ['tta_denied'],
      reasonCode: 'denial_withheld_value_only',
    });
    const out = apply([insert()], [denied]);
    expect(out.declined).toEqual([
      { fieldId: FIELD_ID, reason: 'field_already_filled' },
    ]);
    expect(out.resolutions[0].value).toBeNull();
    expect(out.resolutions[0].status).toBe('denial_withheld');
    expect(out.resolutions[0].reasonCode).toBe('denial_withheld_value_only');
    expect(out.facts).toEqual([]);
  });

  it('⚠️ and NON-VACUITY: a not_mentioned field with the SAME null value DOES apply', () => {
    // The two differ only by status. Without this, the arm above would also
    // pass on a build that declined every null-valued field — which would break
    // the feature entirely while looking like a safety fix.
    const out = apply([insert()], [resolution(FIELD_ID, { value: null })]);
    expect(out.declined).toEqual([]);
    expect(out.resolutions[0].value).toBe('No acute findings.');
  });
});

describe('⚠️ FREE TEXT NEVER ENTERS A CONSTRAINED CONTROL', () => {
  it.each(['single_select', 'multi_select', 'checkbox', 'date', 'number', 'measurement'])(
    'declines on a scaffolded %s — writing one BLOCKS the whole document',
    (kind) => {
      // ⚠️ `isScaffolded` in the compiler is "no showingPlcHdr && visible text"
      // and never reads `kind`, so a dropdown shipping with default content
      // compiles as scaffolded exactly like a paragraph. Write a sentence into
      // one and validation raises a BLOCKING per-kind issue, fill-engine returns
      // render: null for the ENTIRE fill, the surface unmounts — and the panel
      // holding the UNDO button goes with it. For a date or checkbox there is
      // then no product path left to remove the row.
      const out = apply([insert()], [resolution(FIELD_ID)], [field(FIELD_ID, { kind })]);
      expect(out.declined).toEqual([
        { fieldId: FIELD_ID, reason: 'field_kind_not_insertable' },
      ]);
      expect(out.resolutions[0].value).toBeNull();
    },
  );

  it('⚠️ and narrative_text — the same fixture, the only kind that IS allowed', () => {
    const out = apply([insert()], [resolution(FIELD_ID)], [field(FIELD_ID, { kind: 'narrative_text' })]);
    expect(out.declined).toEqual([]);
    expect(out.resolutions[0].value).toBe('No acute findings.');
  });
});

describe('⚠️ THE OFFER AND THE WRITE ASK THE SAME QUESTION', () => {
  it('scaffoldDefaultOfferable refuses every case the overlay declines', () => {
    // ⚠️ ONE PREDICATE, THREE CALLERS. The pass found the panel, the door and
    // the overlay asking three different questions — so the surface offered
    // acts the writer refused and the fill declined forever.
    // ⚠️ BUILT FROM THE HELPERS, NOT BY HAND. These two used to be three- and
    // one-key literals; the predicate reads six field properties and eight
    // mapping properties, so a hand-written stub cannot exercise it.
    const ok = field('F1', { kind: 'narrative_text', scaffoldText: 'x' }) as unknown as
      OmitFieldView & { scaffolded: boolean; scaffoldText: string };
    const concept = mapping('F1', {
      clinicalConcept: 'exam.impression',
    }) as unknown as OmitMappingView & { unmentionedPolicy: string | null };
    expect(scaffoldDefaultOfferable({ field: ok, mapping: concept, current: null })).toBe(true);
    // each refusal, one at a time
    expect(scaffoldDefaultOfferable({ field: { ...ok, scaffolded: false }, mapping: concept, current: null })).toBe(false);
    expect(scaffoldDefaultOfferable({ field: { ...ok, scaffoldText: '  ' }, mapping: concept, current: null })).toBe(false);
    expect(scaffoldDefaultOfferable({ field: { ...ok, kind: 'single_select' }, mapping: concept, current: null })).toBe(false);
    expect(scaffoldDefaultOfferable({ field: ok, mapping: { ...concept, clinicalConcept: null }, current: null })).toBe(false);
    expect(scaffoldDefaultOfferable({ field: ok, mapping: null, current: null })).toBe(false);
    expect(scaffoldDefaultOfferable({ field: ok, mapping: concept, current: { status: 'denial_withheld', value: null } })).toBe(false);
    expect(scaffoldDefaultOfferable({ field: ok, mapping: concept, current: { status: 'supported', value: 'dictated' } })).toBe(false);
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

  it('⚠️ and a legacy option row hashes BYTE-IDENTICALLY to the pre-diff formula', () => {
    // ⚠️ THIS ARM WAS VACUOUS AND AN ADVERSARIAL PASS SAID SO. It used to
    // compare `overridesIdentity` against ITSELF with the two spellings of an
    // option row — which proves the defaulting works and says NOTHING about
    // whether the hash still matches what is already stored in the database.
    // Reverting the implementation to the old 2-tuple left it green.
    //
    // The real control recomputes the PRE-DIFF formula here, independently, and
    // demands equality. If the canonical tuple ever changes shape for an
    // `option` row again, every stored overridesSha256 goes stale on deploy and
    // this arm is what says so.
    const legacy = createHash('sha256')
      .update(JSON.stringify([[FIELD_ID, 3]]), 'utf8')
      .digest('hex');

    expect(overridesIdentity([{ fieldId: FIELD_ID, selectedOptionOrdinal: 3 }])).toBe(legacy);
    expect(
      overridesIdentity([
        {
          fieldId: FIELD_ID,
          selectedOptionOrdinal: 3,
          overrideKind: 'option',
          insertedText: null,
        },
      ]),
    ).toBe(legacy);
  });
});
