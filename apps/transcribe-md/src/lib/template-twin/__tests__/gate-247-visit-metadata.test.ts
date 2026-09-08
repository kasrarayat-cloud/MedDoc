// ============================================================================
// #247 STAGE B — THE THREE `visit_metadata.*` CONCEPTS, AND THEIR THREE
// DIFFERENT PROVENANCES.
// ----------------------------------------------------------------------------
// They share a prefix and they do not share a source, which is the whole reason
// this file is long:
//
//   visit_metadata.patient_name        read off the record  -> `visit_record`
//   visit_metadata.patient_age         computed from the record's DOB
//   visit_metadata.referring_physician DICTATED             -> `encounter_evidence`
//
// A change that treated them as one family would either mark a spoken name as
// record-derived, or mark a patient's name as dictated. Both are the same
// defect pointed in opposite directions, and both are invisible on the rendered
// page — the document is identical and only the manifest is wrong.
// ============================================================================
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it, vi } from 'vitest';

vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import {
  classifyFieldSource,
  compilerDecidableConcepts,
  conceptOverrideFor,
  isRegisteredConcept,
  visitMetadataConceptFor,
} from '../concept-registry';
import {
  ageAtDate,
  ageAtDateResolved,
  rawYearsOnUtcDate,
  withVisitMetadataFacts,
  RECORD_DERIVED_CONCEPTS,
} from '../visit-metadata';
import {
  RECORD_DERIVED_REFUSAL_REASONS,
  isRecordDerivedRefusal,
  EncounterFactSchema,
  SemanticMappingSchema,
  TemplateFieldSchema,
  templateTwinCounts,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from '../ir';
import { compileTemplateDocx } from '@/lib/note-template-docx';
import { prepareTemplateTwinFill } from '../fill-engine';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { decideAutoConfirm } from '../auto-certify-eligibility';
import { refuseRecordDerivedOnNonMetadata } from '../semantic-mapping';
import { projectEncounterFacts } from '../encounter-facts';
import { assertNoRecordDerivedFacts } from '../synthetic-test';

// ---------------------------------------------------------------------------
// FIXTURES — a two-control header, exactly the shape the owner's letter has.
// ---------------------------------------------------------------------------
const NAME_ID = `ttf_${'a'.repeat(24)}`;
/** #264 — a SECOND age control, the module's own documented two-control shape. */
const AGE2_ID = `ttf_${'c'.repeat(24)}`;
const AGE_ID = `ttf_${'b'.repeat(24)}`;
const REFERRER_ID = `ttf_${'d'.repeat(24)}`;

const SHA = 'a'.repeat(64);
type Mapping = SemanticMapping;

// ⚠️ PARSED THROUGH THE SHIPPED SCHEMAS, NOT HAND-SHAPED. The resolver parses
// its inputs, so a cast-shaped fixture proves the injector and then dies one
// function later — which is exactly what the first draft of this file did.
function field(fieldId: string, originalLabel: string): TemplateField {
  return TemplateFieldSchema.parse({
    fieldId,
    kind: 'narrative_text',
    originalLabel,
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: `/synthetic/${fieldId}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: false,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
  });
}

function mapping(fieldId: string, concept: string | null, over: Record<string, unknown> = {}): Mapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: concept,
    sourceType: 'visit_metadata',
    expectedDataType: 'text',
    polarityBehavior: 'value_only',
    temporality: null,
    laterality: 'not_applicable',
    unitPolicy: 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
    ...over,
  });
}

const PATIENT = { name: 'Jane Alvarez', dateOfBirth: '1958-06-14' };
const VISIT = '2026-09-07T14:00:00.000Z';

function fact(over: Record<string, unknown> = {}): EncounterFact {
  return EncounterFactSchema.parse({
    factId: `ttfact_${'c'.repeat(24)}`,
    concept: 'chief_complaint',
    value: 'chest pain',
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Clinician',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['a1'],
    evidenceQuote: 'the doctor said so',
    quality: { asr: 'unknown', evidence: 'direct' },
    ...over,
  });
}

// ---------------------------------------------------------------------------
// 1 · THE LABELS — measured against the owner's own form.
// ---------------------------------------------------------------------------
describe('#247 Stage B — the label decides, and the labels are HIS', () => {
  it('⚠️ the owner’s actual labels are `Patient` and `Age`, one word each', () => {
    // Recorded in three independent places in this repository: the measured
    // header keys in `gate-r2-r3-template-fidelity.test.ts`, the `/^patient$/i`
    // and `/^age$/i` rules in `confirm-live-template-mappings.ts`, and canon 71's
    // transcript of the 35 labels. A pattern written from the phrase "Patient
    // Name" would have matched none of them, which is how the old
    // `/referring\s+physician/i` rule missed "Referring MD".
    expect(classifyFieldSource('Patient', field(NAME_ID, 'Patient'))).toBe('visit_metadata');
    expect(classifyFieldSource('Age', field(AGE_ID, 'Age'))).toBe('visit_metadata');
    expect(visitMetadataConceptFor('Patient')).toBe(RECORD_DERIVED_CONCEPTS.name);
    expect(visitMetadataConceptFor('Age')).toBe(RECORD_DERIVED_CONCEPTS.age);
  });

  it('⚠️ AND WORD\'S PLACEHOLDER IS PART OF THE LABEL — an end anchor cannot see past it', () => {
    // The compiled label is `REFERRING PHYSICIAN: Choose an item.`, not
    // `REFERRING PHYSICIAN`. The first end-anchored draft of these patterns
    // silently refused the real controls on the owner's own form, and the F24
    // census moved by one the moment it landed.
    expect(conceptOverrideFor('REFERRING PHYSICIAN: Choose an item.')).toBe(
      'visit_metadata.referring_physician',
    );
    expect(visitMetadataConceptFor('Patient: Choose an item.')).toBe(RECORD_DERIVED_CONCEPTS.name);
    expect(visitMetadataConceptFor('Age Choose an item')).toBe(RECORD_DERIVED_CONCEPTS.age);
  });

  it('⚠️ A CONTROL THAT CANNOT CARRY A NAME IS NOT RECORD-DERIVED — the checkbox tick', () => {
    // A refutation lens drove this through the shipped chain: a CHECKBOX
    // labelled `Patient` ("History provided by: ☐ Patient ☐ Family") classified
    // `visit_metadata`, the injector minted an `affirmed` fact, and the
    // resolver's checkbox arm — which reads polarity and DISCARDS the value —
    // resolved `record_derived / value: true`, valid, zero issues. The box is
    // ticked because the chart has a name in it.
    for (const kind of ['checkbox', 'date', 'measurement']) {
      expect([kind, classifyFieldSource('Patient', { kind, allowedOptions: [] })])
        .toEqual([kind, 'extraction']);
    }
    // An enumerated pick stays the physician's to answer, as it was before.
    for (const kind of ['single_select', 'multi_select']) {
      expect([kind, classifyFieldSource('Patient', { kind, allowedOptions: [{ ordinal: 1 }] })])
        .toEqual([kind, 'verified_note_selection']);
    }
    // ⚠️ NON-VACUITY: the two kinds that CAN carry it still do.
    for (const kind of ['narrative_text', 'number']) {
      expect([kind, classifyFieldSource('Age', { kind, allowedOptions: [] })])
        .toEqual([kind, 'visit_metadata']);
    }
    // ⚠️ AND A LABEL WITH NO FIELD AT ALL IS NOT RECORD-DERIVED EITHER.
    expect(classifyFieldSource('Patient')).toBe('extraction');
  });

  it('⚠️ THE REFERRING PATTERN IS ANCHORED AT BOTH ENDS — a qualifier makes it a different field', () => {
    // The first draft was a prefix match, and two lenses independently measured
    // the referrer's NAME rendering into the fax box: `supported`,
    // "Dr. Alan Whitfield", valid, auto-confirmed. A REGRESSION — those labels
    // matched the old unanchored manual pattern and rendered an honest blank.
    for (const label of [
      'Referring Physician Fax',
      'Referring MD NPI',
      'Referring Physician Address',
      'Referring MD Phone',
      'Referring MD signature',
      'Referring provider NPI number',
      "Referring Physician's Office",
    ]) {
      expect([label, conceptOverrideFor(label)]).toEqual([label, null]);
    }
    // ⚠️ NON-VACUITY: the name-shaped spellings still resolve.
    for (const label of ['Referring MD', 'Name of Referring Physician', 'Referring Physician Name']) {
      expect([label, conceptOverrideFor(label)]).toEqual([
        label,
        'visit_metadata.referring_physician',
      ]);
    }
  });

  it('and the spellings a different form would use', () => {
    for (const label of ['Patient Name', "Patient's Name", 'Patient:', 'Patient Full Name']) {
      expect([label, visitMetadataConceptFor(label)]).toEqual([label, RECORD_DERIVED_CONCEPTS.name]);
    }
    for (const label of ['Age:', 'Patient Age', "Patient's age"]) {
      expect([label, visitMetadataConceptFor(label)]).toEqual([label, RECORD_DERIVED_CONCEPTS.age]);
    }
  });

  it('⚠️ NON-VACUITY, AND THIS IS THE ARM THAT MATTERS — neither pattern reaches into PROSE', () => {
    // A prefix match on either would put a patient's name or age into a
    // narrative control. `Age of onset` is an ordinary HPI label and
    // `Patient reports ...` is an ordinary scaffolded sentence; both are
    // one loosened anchor away from being claimed by this family.
    for (const label of [
      'Age of onset',
      'Patient reports intermittent heartburn',
      'Patient education discussed',
      'Ages of affected relatives',
      'Impatient',
    ]) {
      expect([label, visitMetadataConceptFor(label)]).toEqual([label, null]);
      expect([label, classifyFieldSource(label)]).toEqual([label, 'extraction']);
    }
  });

  it('⚠️ THE REFERRER IS UN-PINNED FROM `manual`, in the owner’s spelling and the generic one', () => {
    // Before #247 this was `manual` — an honest blank a human retypes every
    // visit. It is DICTATED, so it is an ordinary extraction with a concept.
    for (const label of ['Referring MD', 'Referring Physician', 'REFERRING PHYSICIAN:', 'Referring Provider']) {
      expect([label, classifyFieldSource(label)]).toEqual([label, 'extraction']);
      expect([label, conceptOverrideFor(label)]).toEqual([
        label,
        'visit_metadata.referring_physician',
      ]);
    }
  });

  it('⚠️ and it is NOT record-derived — the separation inside one family', () => {
    // The single most confusable line in this change: three concepts, one
    // prefix, and the third one must never be injected from the record.
    expect(classifyFieldSource('Referring MD')).not.toBe('visit_metadata');
    expect(visitMetadataConceptFor('Referring MD')).toBeNull();
  });

  it('the four that nobody says aloud are STILL manual', () => {
    // The un-pinning was one pattern, not a policy change about the class.
    for (const label of ['ULTRASOUND TECHNOLOGIST: Choose an item.', 'MACHINE: X', 'Location', 'Address']) {
      expect([label, classifyFieldSource(label)]).toEqual([label, 'manual']);
    }
  });

  it('every compiler-decidable concept is registry-legal', () => {
    // The author-time invariant `compilerDecidableConcepts` exists for: an
    // override naming a concept the extractor never emits makes its field
    // permanently unfillable in production.
    for (const c of compilerDecidableConcepts()) {
      expect([c, isRegisteredConcept(c)]).toEqual([c, true]);
    }
    expect(compilerDecidableConcepts()).toContain('visit_metadata.patient_name');
    expect(compilerDecidableConcepts()).toContain('visit_metadata.patient_age');
    expect(compilerDecidableConcepts()).toContain('visit_metadata.referring_physician');
  });
});

// ---------------------------------------------------------------------------
// 2 · THE AGE — calendar arithmetic, and its refusals.
// ---------------------------------------------------------------------------
describe('#247 Stage B — age at the VISIT date, in whole years', () => {
  // ⚠️ THESE THREE ARMS WERE REWRITTEN BY #264 — AND THE REWRITE SILENTLY REMOVED
  // THE TEETH OF ONE OF THEM. A refutation pass measured it: with the assertions
  // moved CLEAR of the ±26h window, all of them PASS against an
  // `(at - dob) / 365.25` implementation — including the middle arm, whose own
  // title says it exists to catch exactly that scheme.
  //
  // ⚠️ SCOPE CORRECTED, BECAUSE THE FIRST WRITE-UP OVERSTATED IT. "origin/main's
  // originals red on that mutation" is FALSE for two of the three. Measured
  // against a floor-based 365.25 scheme:
  //
  //     arm 1 (counts whole years)          main: does NOT catch it
  //     arm 2 (names the 365.25 scheme)     main: CATCHES it  (25 -> 24)
  //     arm 3 (leap-day)                    main: does NOT catch it
  //
  // So ONE arm lost real protection, not three — and a finding that is REAL can
  // still carry a wrong scope, which is what a reader acts on.
  //
  //     MOVING AN ASSERTION AWAY FROM THE AMBIGUITY MOVED IT AWAY FROM THE
  //     DISCRIMINATION. 365.25-division only diverges AT the birthday boundary,
  //     and the boundary is precisely what the window now refuses.
  //
  // So the boundary arithmetic is pinned on the exported, UNCLAMPED
  // `rawYearsOnUtcDate`, where no timezone question arises — see the block after
  // these three. Two concerns, two arms; neither borrows the other's coverage.
  // What remains here is the ordinary-date behaviour, which is worth an arm and
  // is not the arm that was lost.
  it('counts whole years — asserted clear of the ambiguous window', () => {
    expect(ageAtDate('1958-06-14', '2026-06-11T12:00:00Z')).toBe(67);
    expect(ageAtDate('1958-06-14', '2026-06-16T12:00:00Z')).toBe(68);
    expect(ageAtDate('1958-06-14', '2027-01-01T00:00:00Z')).toBe(68);
  });

  it('⚠️ THE DAY BEFORE A BIRTHDAY IS NOT A ROUNDING ERROR — division by 365.25 gets this wrong', () => {
    // 24 years and 364 days is 24, and any average-year scheme says 24.997 and
    // then rounds. The patient is 24 until the day they are 25. Asserted two
    // days either side, so the claim is about the ARITHMETIC and not about
    // which timezone the reader is in.
    expect(ageAtDate('2001-03-02', '2026-02-27T12:00:00Z')).toBe(24);
    expect(ageAtDate('2001-03-02', '2026-03-04T12:00:00Z')).toBe(25);
  });

  it('handles a leap-day birth without inventing a birthday', () => {
    // 2026 is not a leap year: the patient turns 26 on 1 March, not 28 February.
    expect(ageAtDate('2000-02-29', '2026-02-26T12:00:00Z')).toBe(25);
    expect(ageAtDate('2000-02-29', '2026-03-03T12:00:00Z')).toBe(26);
  });

  it('⚠️ #264 — REFUSES on the boundary, in BOTH directions, and names the reason', () => {
    // The instants the three arms above used to assert a number on. Each is
    // within ±26h of the birthday boundary, so a doctor west of UTC and a doctor
    // east of UTC would read different ages off the SAME visit.
    for (const at of [
      '2026-06-13T23:00:00Z', // was asserted 67 — but 68 for a doctor east of UTC
      '2026-06-14T00:00:00Z', // was asserted 68 — but 67 for a doctor west of UTC
    ]) {
      const r = ageAtDateResolved('1958-06-14', at);
      expect(r.ok, `${at} must refuse`).toBe(false);
      if (!r.ok) expect(r.reason).toBe('age_timezone_ambiguous');
      expect(ageAtDate('1958-06-14', at)).toBeNull();
    }
    expect(ageAtDateResolved('2001-03-02', '2026-03-02').ok).toBe(false);
    expect(ageAtDateResolved('2000-02-29', '2026-03-01').ok).toBe(false);
  });

  it('⚠️ the REAL-WORLD case, both directions, computed rather than asserted', () => {
    // DOB 1958-06-14.
    //   2026-06-13 19:00 America/Los_Angeles = 2026-06-14T02:00Z
    //     UTC says the birthday passed -> 68. Locally it is the 13th -> 67.
    //   2026-06-14 09:00 Pacific/Auckland   = 2026-06-13T21:00Z
    //     UTC says it has not -> 67. Locally it is the 14th -> 68.
    // ⚠️ THE OLD COMMENT IN visit-metadata.ts NAMED ONLY THE FIRST. The error
    // runs both ways, and a fix aimed at one direction would have shipped.
    expect(ageAtDate('1958-06-14', '2026-06-14T02:00:00Z')).toBeNull();
    expect(ageAtDate('1958-06-14', '2026-06-13T21:00:00Z')).toBeNull();
  });

  it('⚠️ THE BOUNDARY ARITHMETIC, PINNED WHERE THE WINDOW CANNOT HIDE IT', () => {
    // ⚠️ THIS ARM IS THE ONE THE REWRITE LOST, RESTORED ON THE UNCLAMPED
    // FUNCTION. It drives `rawYearsOnUtcDate` directly, so the ±26h refusal is
    // out of the way and the day-boundary is testable again.
    const on = (iso: string) => new Date(iso);
    const dob = (iso: string) => new Date(`${iso}T00:00:00Z`);

    // the birthday IS the boundary — 364 days is not a year
    expect(rawYearsOnUtcDate(dob('2001-03-02'), on('2026-03-01T00:00:00Z'))).toBe(24);
    expect(rawYearsOnUtcDate(dob('2001-03-02'), on('2026-03-02T00:00:00Z'))).toBe(25);
    // a leap-day birth invents no birthday: 2026 is not a leap year, so 1 March
    expect(rawYearsOnUtcDate(dob('2000-02-29'), on('2026-02-28T00:00:00Z'))).toBe(25);
    expect(rawYearsOnUtcDate(dob('2000-02-29'), on('2026-03-01T00:00:00Z'))).toBe(26);
    // the day before a birthday
    expect(rawYearsOnUtcDate(dob('1958-06-14'), on('2026-06-13T23:00:00Z'))).toBe(67);
    expect(rawYearsOnUtcDate(dob('1958-06-14'), on('2026-06-14T00:00:00Z'))).toBe(68);
  });

  it('⚠️ AND IT REDS ON THE 365.25 SCHEME — the mutation the rewrite stopped catching', () => {
    // ⚠️ THE ARM ABOVE IS ONLY WORTH HAVING IF IT DISCRIMINATES. Rather than
    // assert that in prose, run the wrong implementation and show the exact
    // inputs where it diverges. If this ever stops finding a divergence, the arm
    // above has gone blind again and this one says so.
    const div36525 = (dobS: string, atS: string) =>
      Math.floor(
        (new Date(atS).getTime() - new Date(`${dobS}T00:00:00Z`).getTime()) / (365.25 * 86_400_000),
      );
    const cases: Array<[string, string, number]> = [
      ['2001-03-02', '2026-03-02T00:00:00Z', 25],
      ['2000-02-29', '2026-03-01T00:00:00Z', 26],
      ['1958-06-14', '2026-06-14T00:00:00Z', 68],
    ];
    const diverged = cases.filter(([d, a, want]) => {
      expect(rawYearsOnUtcDate(new Date(`${d}T00:00:00Z`), new Date(a))).toBe(want);
      return div36525(d, a) !== want;
    });
    expect(diverged.length, 'no input discriminates — the arm above is blind').toBeGreaterThan(0);
  });

  it('⚠️ NON-VACUITY — the refusal is NARROW, not a blanket', () => {
    // A guard that refused everything would pass every arm above and destroy the
    // feature. Measured over a full year of visit instants against one DOB:
    // only the days adjacent to the birthday refuse.
    let refused = 0;
    let answered = 0;
    for (let d = 0; d < 365; d += 1) {
      const at = new Date(Date.UTC(2026, 0, 1, 12) + d * 86_400_000);
      if (ageAtDateResolved('1958-06-14', at).ok) answered += 1;
      else refused += 1;
    }
    expect(answered).toBeGreaterThan(360);
    expect(refused).toBeGreaterThan(0);
    expect(refused).toBeLessThanOrEqual(2);
  });

  it('an infant is 0, and 0 is an ANSWER rather than the failure value', () => {
    expect(ageAtDate('2026-08-01', '2026-09-07')).toBe(0);
  });

  it('REFUSES rather than guesses', () => {
    expect(ageAtDate(null, VISIT)).toBeNull();
    expect(ageAtDate('1958-06-14', null)).toBeNull();
    expect(ageAtDate('not a date', VISIT)).toBeNull();
    // A birth date after the visit means the record and the visit disagree
    // about time. Clamping to 0 would print a newborn.
    expect(ageAtDate('2030-01-01', VISIT)).toBeNull();
    // Past the verified human maximum the column holds something that is not a
    // birth date.
    expect(ageAtDate('1820-01-01', VISIT)).toBeNull();
  });

  it('accepts a Date as readily as a string, since the column is a Date', () => {
    expect(ageAtDate(new Date('1958-06-14T00:00:00Z'), new Date(VISIT))).toBe(
      ageAtDate('1958-06-14', VISIT),
    );
    expect(ageAtDate(new Date('1958-06-14T00:00:00Z'), new Date(VISIT))).not.toBeNull();
  });

  it('the named reasons are distinct — a refusal says WHICH refusal', () => {
    expect(ageAtDateResolved(null, VISIT)).toEqual({ ok: false, reason: 'age_input_absent' });
    expect(ageAtDateResolved('not a date', VISIT)).toEqual({
      ok: false,
      reason: 'age_unparseable',
    });
    expect(ageAtDateResolved('2030-01-01', VISIT)).toEqual({
      ok: false,
      reason: 'age_implausible',
    });
    expect(ageAtDateResolved('1820-01-01', VISIT)).toEqual({
      ok: false,
      reason: 'age_implausible',
    });
  });
});

// ---------------------------------------------------------------------------
// 3 · THE INJECTOR.
// ---------------------------------------------------------------------------
describe('#247 Stage B — `withVisitMetadataFacts`', () => {
  const fields = [field(NAME_ID, 'Patient'), field(AGE_ID, 'Age')];
  const mappings = [
    mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
    mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age),
  ];

  it('injects both, and BOTH wear `visit_record`', () => {
    const out = withVisitMetadataFacts({ fields, mappings, facts: [], patient: PATIENT, visitDate: VISIT });
    expect(out).toHaveLength(2);
    expect(out.every((f) => f.sourceType === 'visit_record')).toBe(true);
    expect(out.map((f) => [f.concept, f.value])).toEqual([
      [RECORD_DERIVED_CONCEPTS.name, 'Jane Alvarez'],
      [RECORD_DERIVED_CONCEPTS.age, '68'],
    ]);
    // ⚠️ THE ARM THAT MATTERS. `encounter_evidence` is the schema DEFAULT, so
    // a future edit that drops the explicit `sourceType` produces facts that
    // parse, resolve, render and lie.
    expect(out.some((f) => f.sourceType === 'encounter_evidence')).toBe(false);
  });

  it('⚠️ the evidence quote carries NO identifier of its own', () => {
    // The value is the name; the quote says where the value came from. Both go
    // into the manifest, and only one of them has to.
    const out = withVisitMetadataFacts({ fields, mappings, facts: [], patient: PATIENT, visitDate: VISIT });
    for (const f of out) {
      expect(f.evidenceQuote).not.toContain('Jane');
      expect(f.evidenceQuote).not.toContain('Alvarez');
      expect(f.evidenceQuote).toMatch(/patient record/i);
    }
  });

  it('⚠️ polarity is STATED, not inferred — canon 135', () => {
    // There is no such thing as a denied patient name, and the inference reads
    // the whole quote when the value is not locatable in it.
    const out = withVisitMetadataFacts({ fields, mappings, facts: [], patient: PATIENT, visitDate: VISIT });
    expect(out.every((f) => f.polarity === 'affirmed')).toBe(true);
  });

  it('NO-OPS with no patient record, and that is the certification path', () => {
    expect(withVisitMetadataFacts({ fields, mappings, facts: [], patient: null, visitDate: VISIT })).toHaveLength(0);
    expect(withVisitMetadataFacts({ fields, mappings, facts: [], patient: undefined, visitDate: VISIT })).toHaveLength(0);
  });

  it('injects the NAME but not the age when the record has no date of birth', () => {
    const out = withVisitMetadataFacts({
      fields, mappings, facts: [],
      patient: { name: 'Jane Alvarez', dateOfBirth: null }, visitDate: VISIT,
    });
    expect(out.map((f) => f.concept)).toEqual([RECORD_DERIVED_CONCEPTS.name]);
  });

  it('injects nothing for a blank name, rather than an empty string', () => {
    const out = withVisitMetadataFacts({
      fields, mappings, facts: [], patient: { name: '   ', dateOfBirth: '1958-06-14' }, visitDate: VISIT,
    });
    expect(out.map((f) => f.concept)).toEqual([RECORD_DERIVED_CONCEPTS.age]);
  });

  it('⚠️ ONLY what the CERTIFIED mapping asked for — an uncertified mapping fills nothing', () => {
    const draft = mappings.map((m) => ({ ...m, status: 'needs_confirmation' }) as Mapping);
    expect(withVisitMetadataFacts({ fields, mappings: draft, facts: [], patient: PATIENT, visitDate: VISIT })).toHaveLength(0);
  });

  it('⚠️ and only for the `visit_metadata` SOURCE — a same-concept `extraction` mapping fills nothing', () => {
    // The one route by which a record value could reach a control the label
    // rule never claimed. Gated on the mapping, never on the label — the label
    // was read once already, by `classifyFieldSource`.
    const extraction = mappings.map((m) => ({ ...m, sourceType: 'extraction' }) as Mapping);
    expect(withVisitMetadataFacts({ fields, mappings: extraction, facts: [], patient: PATIENT, visitDate: VISIT })).toHaveLength(0);
  });

  it('⚠️ a `visit_metadata` mapping citing SOMETHING ELSE is not this module’s business', () => {
    const off = [mapping(NAME_ID, 'visit_metadata.mrn')];
    expect(withVisitMetadataFacts({ fields, mappings: off, facts: [], patient: PATIENT, visitDate: VISIT })).toHaveLength(0);
    // And the registry closed the family at three, so it could not have been
    // certified in the first place.
    expect(isRegisteredConcept('visit_metadata.mrn')).toBe(false);
    expect(isRegisteredConcept('visit_metadata.ssn')).toBe(false);
    expect(isRegisteredConcept('visit_metadata.address')).toBe(false);
  });

  it('REAL EVIDENCE WINS — a dictated fact on the concept stops the injection', () => {
    const spoken = fact({ concept: RECORD_DERIVED_CONCEPTS.name, value: 'someone the doctor named' });
    const out = withVisitMetadataFacts({ fields, mappings, facts: [spoken], patient: PATIENT, visitDate: VISIT });
    expect(out.filter((f) => f.sourceType === 'visit_record').map((f) => f.concept)).toEqual([
      RECORD_DERIVED_CONCEPTS.age,
    ]);
  });

  it('⚠️ ONE FACT PER CONCEPT, not one per field — two name controls share one fact', () => {
    const twoNames = [field(NAME_ID, 'Patient'), field(REFERRER_ID, 'Patient Name')];
    const twoMappings = [
      mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
      mapping(REFERRER_ID, RECORD_DERIVED_CONCEPTS.name),
    ];
    const out = withVisitMetadataFacts({
      fields: twoNames, mappings: twoMappings, facts: [], patient: PATIENT, visitDate: VISIT,
    });
    expect(out).toHaveLength(1);
  });

  it('is PURE — the input array is not mutated', () => {
    const input: EncounterFact[] = [];
    withVisitMetadataFacts({ fields, mappings, facts: input, patient: PATIENT, visitDate: VISIT });
    expect(input).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 4 · RESOLVE -> VALIDATE, end to end, and the fail-closed direction.
// ---------------------------------------------------------------------------
describe('#247 Stage B — the injected facts survive the INDEPENDENT validator', () => {
  const fields = [field(NAME_ID, 'Patient'), field(AGE_ID, 'Age')];
  const mappings = [
    mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
    mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age),
  ];
  const certifiedFieldIds = [NAME_ID, AGE_ID];

  function run() {
    const facts = withVisitMetadataFacts({ fields, mappings, facts: [], patient: PATIENT, visitDate: VISIT });
    const resolutions = resolveTemplateFields({ fields, mappings, facts, certifiedFieldIds });
    const validation = validateTemplateTwin({
      fields, mappings, facts, resolutions,
      tables: [], unsupported: [], certifiedFieldIds,
      allowUncertifiedForSyntheticTest: false, now: VISIT,
    });
    return { facts, resolutions, validation };
  }

  it('both controls fill, and both are `record_derived` rather than `supported`', () => {
    const { resolutions, validation } = run();
    expect(resolutions.map((r) => [r.status, r.value])).toEqual([
      ['record_derived', 'Jane Alvarez'],
      ['record_derived', '68'],
    ]);
    expect(validation.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
    expect(validation.valid).toBe(true);
  });

  it('⚠️ THE MANIFEST COUNTS THEM, AND SAYS WHICH — `filled` alone cannot', () => {
    const { resolutions } = run();
    const counts = templateTwinCounts(resolutions, fields);
    expect(counts.filled).toBe(2);
    expect(counts.recordDerived).toBe(2);
  });

  it('⚠️ AND THE KEY IS ABSENT WHEN THE COUNT IS ZERO — every stored manifest must still re-verify', () => {
    // The sign gate recomputes these counts over a STORED manifest and compares
    // canonical shas. An unconditional new key changes the recomputed sha of
    // every manifest already on disk and fails a document nobody touched.
    const dictated = templateTwinCounts(
      resolveTemplateFields({
        fields: [field(REFERRER_ID, 'Referring MD')],
        mappings: [mapping(REFERRER_ID, 'visit_metadata.referring_physician', { sourceType: 'extraction' })],
        facts: [fact({ concept: 'visit_metadata.referring_physician', value: 'Dr. Alan Whitfield', experiencer: 'other' })],
        certifiedFieldIds: [REFERRER_ID],
      }),
      [field(REFERRER_ID, 'Referring MD')],
    );
    expect(dictated.recordDerived).toBeUndefined();
    expect(Object.keys(dictated)).not.toContain('recordDerived');
  });

  it('⚠️ FAIL-CLOSED: a `supported` resolution citing the RECORD is BLOCKING', () => {
    // The mutation is the defect this whole family exists to prevent, and it is
    // the one that renders a perfect document: the value is right, the page is
    // right, and the manifest says the clinician said it.
    const { facts, resolutions } = run();
    const mutated = resolutions.map((r) => ({ ...r, status: 'supported' as const }));
    const validation = validateTemplateTwin({
      fields, mappings, facts, resolutions: mutated,
      tables: [], unsupported: [], certifiedFieldIds,
      allowUncertifiedForSyntheticTest: false, now: VISIT,
    });
    expect(validation.valid).toBe(false);
    expect(validation.issues.filter((i) => i.code === 'SUPPORTED_STATUS_CITES_RECORD_EVIDENCE')).toHaveLength(2);
  });

  it('⚠️ FAIL-CLOSED, the other way: `record_derived` citing DICTATION is BLOCKING', () => {
    const spoken = fact({ concept: RECORD_DERIVED_CONCEPTS.name, value: 'Jane Alvarez' });
    const resolutions = resolveTemplateFields({
      fields: [fields[0]!], mappings: [mappings[0]!], facts: [spoken], certifiedFieldIds: [NAME_ID],
    });
    // The resolver correctly calls this `supported` — it IS dictated.
    expect(resolutions[0]!.status).toBe('supported');
    const mutated = resolutions.map((r) => ({ ...r, status: 'record_derived' as const }));
    const validation = validateTemplateTwin({
      fields: [fields[0]!], mappings: [mappings[0]!], facts: [spoken], resolutions: mutated,
      tables: [], unsupported: [], certifiedFieldIds: [NAME_ID],
      allowUncertifiedForSyntheticTest: false, now: VISIT,
    });
    expect(validation.issues.filter((i) => i.code === 'RECORD_DERIVED_WITHOUT_RECORD_EVIDENCE')).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// 5 · THE DICTATED MEMBER — L3 -> projector -> resolver.
// ---------------------------------------------------------------------------
describe('#247 Stage B — the referring physician is DICTATED, all the way through', () => {
  const CONTEXT = 'She was referred by Dr. Alan Whitfield for further evaluation.';
  const project = () =>
    projectEncounterFacts({
      mode: 'dictation',
      contextText: CONTEXT,
      asrQuality: 'high',
      entities: {
        referring_physician: { name: 'Dr. Alan Whitfield', evidence_quote: CONTEXT },
      } as never,
    });

  it('the projector emits it as ORDINARY evidence, never as a record value', () => {
    const facts = project().filter((f) => f.concept === 'visit_metadata.referring_physician');
    expect(facts).toHaveLength(1);
    expect(facts[0]!.sourceType).toBe('encounter_evidence');
    expect(facts[0]!.value).toBe('Dr. Alan Whitfield');
    // ⚠️ AND THE SUBJECT IS NOT THE PATIENT. Stamping `patient` here would have
    // made the resolver's experiencer gate pass with no other change — and
    // written into the manifest that a named outside physician is the patient.
    expect(facts[0]!.experiencer).toBe('other');
  });

  it('⚠️ AND IT RESOLVES — the experiencer gate admits exactly this concept', () => {
    // Without the `permitsOtherClinician` arm in the resolver, an
    // `experiencer: 'other'` fact is refused `experiencer_not_approved` and the
    // field comes back ambiguous on every visit that dictated a referrer.
    const f = field(REFERRER_ID, 'Referring MD');
    const m = mapping(REFERRER_ID, 'visit_metadata.referring_physician', { sourceType: 'extraction' });
    const resolutions = resolveTemplateFields({
      fields: [f], mappings: [m], facts: project(), certifiedFieldIds: [REFERRER_ID],
    });
    expect([resolutions[0]!.status, resolutions[0]!.value]).toEqual(['supported', 'Dr. Alan Whitfield']);
  });

  it('⚠️ NON-VACUITY: the gate still REFUSES an `other` experiencer on any other concept', () => {
    // Widening the gate by concept rather than by value is the whole point; an
    // unconditional relaxation would let a fact about the patient's brother fill
    // a field about the patient.
    const f = field(NAME_ID, 'Chief complaint');
    const m = mapping(NAME_ID, 'chief_complaint', { sourceType: 'extraction' });
    const other = fact({ concept: 'chief_complaint', value: 'chest pain', experiencer: 'other' });
    const resolutions = resolveTemplateFields({
      fields: [f], mappings: [m], facts: [other], certifiedFieldIds: [NAME_ID],
    });
    expect(resolutions[0]!.reasonCode).toBe('experiencer_not_approved');
  });

  it('an unstated referrer yields NOTHING — no computed value, no practice carry-over', () => {
    const facts = projectEncounterFacts({
      mode: 'dictation', contextText: 'Ordinary visit.', asrQuality: 'high',
      entities: { referring_physician: null } as never,
    });
    expect(facts.filter((f) => f.concept === 'visit_metadata.referring_physician')).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// 6 · THE TWO CONSERVATIVE CALLS THE OWNER RULED.
// ---------------------------------------------------------------------------
describe('#247 Stage B — a `visit_metadata` mapping NEVER auto-confirms', () => {
  const candidate = {
    originalLabel: 'Patient',
    criticality: null,
    sourceType: 'visit_metadata',
    hasClinicalConcept: true,
  };

  it('the engine refuses, and says why in words a doctor can read', () => {
    const d = decideAutoConfirm(candidate);
    expect(d.confirm).toBe(false);
    expect(d.provenance).toBeNull();
    expect(d.reason).toMatch(/patient record/i);
  });

  it('⚠️ REFUSED FIRST — no later arm can confirm it by satisfying something else', () => {
    // Every other confirming arm is reachable with this candidate's shape: it
    // has a concept, it has no bad scope, and adding `criticality: 'laterality'`
    // hits an arm that returns `confirm: true` unconditionally. Ordering is the
    // only thing that makes those unreachable.
    expect(decideAutoConfirm({ ...candidate, criticality: 'laterality' }).confirm).toBe(false);
    expect(decideAutoConfirm({ ...candidate, conceptScope: ['chief_complaint'] }).confirm).toBe(false);
    expect(decideAutoConfirm({ ...candidate, hasClinicalConcept: false }).confirm).toBe(false);
  });

  it('⚠️ NON-VACUITY: the ordinary classes still auto-confirm', () => {
    // Without this the arm above is satisfied by a function that refuses
    // everything, which would stop the owner certifying at all.
    expect(decideAutoConfirm({ ...candidate, sourceType: 'extraction' }).confirm).toBe(true);
    expect(decideAutoConfirm({ ...candidate, sourceType: 'manual' })).toMatchObject({
      confirm: true, provenance: 'blank_by_design',
    });
  });

  it('⚠️ AND THE DICTATED REFERRER IS NOT CAUGHT BY IT', () => {
    // It is `extraction`, so the human-confirm requirement lands on the two
    // controls that print an identity and on nothing else.
    expect(decideAutoConfirm({
      ...candidate, originalLabel: 'Referring MD', sourceType: 'extraction',
    }).confirm).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 6b · WHAT THE ADVERSARIAL PASS FOUND, EACH WITH ITS OWN ARM.
// ---------------------------------------------------------------------------
describe('#247 Stage B — a record-derived fact matches by EXACT concept only', () => {
  const f = field(NAME_ID, 'Patient');

  it('⚠️ a SYNONYM cannot carry it — the route that withheld a whole document', () => {
    // Measured by a lens: mapping `visit_metadata.patient_name` with
    // `approvedSynonyms: ['chief_complaint']` plus a dictated chief-complaint
    // fact of the same value resolved `supported` over BOTH facts, which the
    // validator's own arm then refuses as BLOCKING -> `render: null` -> the
    // doctor loses the entire native document.
    const m = mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name, {
      approvedSynonyms: ['chief_complaint'],
    });
    // ⚠️ THE PROJECTED FACTS GO IN, exactly as `prepareTemplateTwinFill` feeds
    // them — the injector's "real evidence wins" test cannot see a fact handed
    // to it after the fact, and neither can the shipped pipeline.
    const spoken = fact({ concept: 'chief_complaint', value: 'Jane Alvarez' });
    const facts = withVisitMetadataFacts({
      fields: [f], mappings: [m], facts: [spoken], patient: PATIENT, visitDate: VISIT,
    });
    // Nothing was injected: the dictated fact already satisfies this mapping,
    // which is the question the RESOLVER asks and which this guard now asks too.
    expect(facts).toHaveLength(1);
    const res = resolveTemplateFields({
      fields: [f], mappings: [m], facts, certifiedFieldIds: [NAME_ID],
    });
    expect(res[0]!.sourceFactIds).toHaveLength(1);
    expect(res[0]!.status).toBe('supported');
    const v = validateTemplateTwin({
      fields: [f], mappings: [m], facts, resolutions: res,
      tables: [], unsupported: [], certifiedFieldIds: [NAME_ID],
      allowUncertifiedForSyntheticTest: false, now: VISIT,
    });
    expect(v.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
  });

  it('⚠️ a DECLARED SCOPE cannot carry it either', () => {
    const m = mapping(NAME_ID, 'chief_complaint', {
      conceptScope: [RECORD_DERIVED_CONCEPTS.name],
    });
    const record = fact({
      concept: RECORD_DERIVED_CONCEPTS.name, value: 'Jane Alvarez', sourceType: 'visit_record',
    });
    const res = resolveTemplateFields({
      fields: [f], mappings: [m], facts: [record], certifiedFieldIds: [NAME_ID],
    });
    expect(res[0]!.value).toBeNull();
  });

  it('⚠️ NON-VACUITY: a DICTATED fact still reaches a mapping through its synonym', () => {
    // Without this, the arms above are satisfied by a matcher that stopped
    // honouring `approvedSynonyms` at all — which would blank a great many
    // legitimately-mapped controls.
    const m = mapping(NAME_ID, 'assessment', { approvedSynonyms: ['impression'], sourceType: 'extraction' });
    const spoken = fact({ concept: 'impression', value: 'reflux' });
    const res = resolveTemplateFields({
      fields: [f], mappings: [m], facts: [spoken], certifiedFieldIds: [NAME_ID],
    });
    expect([res[0]!.status, res[0]!.value]).toEqual(['supported', 'reflux']);
  });
});

describe('#247 Stage B — a record concept on a non-metadata mapping is REFUSED at proposal', () => {
  it('nulls it, so nothing can auto-confirm a control that would print a name', () => {
    expect(refuseRecordDerivedOnNonMetadata(RECORD_DERIVED_CONCEPTS.name, 'extraction')).toBeNull();
    expect(refuseRecordDerivedOnNonMetadata(RECORD_DERIVED_CONCEPTS.age, 'verified_note_selection')).toBeNull();
    expect(refuseRecordDerivedOnNonMetadata(RECORD_DERIVED_CONCEPTS.name, 'manual')).toBeNull();
  });

  it('⚠️ NON-VACUITY: it passes everything else through untouched', () => {
    expect(refuseRecordDerivedOnNonMetadata(RECORD_DERIVED_CONCEPTS.name, 'visit_metadata'))
      .toBe(RECORD_DERIVED_CONCEPTS.name);
    expect(refuseRecordDerivedOnNonMetadata('chief_complaint', 'extraction')).toBe('chief_complaint');
    // The DICTATED member is not record-derived and must not be caught.
    expect(refuseRecordDerivedOnNonMetadata('visit_metadata.referring_physician', 'extraction'))
      .toBe('visit_metadata.referring_physician');
    expect(refuseRecordDerivedOnNonMetadata(null, 'extraction')).toBeNull();
  });
});

describe('#247 Stage B — the referrer states its polarity and its tense', () => {
  const project = (text: string) =>
    projectEncounterFacts({
      mode: 'dictation', contextText: text, asrQuality: 'high',
      entities: { referring_physician: { name: 'Dr. Lee', evidence_quote: text } } as never,
    }).filter((f) => f.concept === 'visit_metadata.referring_physician')[0]!;

  it('⚠️ A HEDGED DIAGNOSIS DOES NOT MAKE THE REFERRAL UNCERTAIN', () => {
    // Every one of these came back `uncertain` -> `ambiguous` -> FIELD_AMBIGUOUS
    // -> blocking -> `render: null`, because `clinicallyMaterial: true` is
    // hard-coded at all twelve compiler emission sites. The hedge is about the
    // DIAGNOSIS; the referral is not in doubt.
    for (const text of [
      'Referred by Dr. Lee for possible inflammatory bowel disease.',
      'Dr. Osei referred her for suspected celiac disease.',
      'She was referred by Dr. Lee in May for evaluation.',
      'Dr. Lee referred her; she may need an upper endoscopy.',
    ]) {
      expect([text, project(text).polarity]).toEqual([text, 'affirmed']);
    }
  });

  it('⚠️ AND THE WORD "REFERRED" DOES NOT MAKE THE REFERRAL A PLAN', () => {
    // `PLANNED` is /plan|will|schedule|refer(red|ral)?|start|follow-up/, so the
    // very word that identifies a referral sentence stamped every one of these
    // `planned`. Against a mapping declaring `current` that is
    // `temporality_not_approved`: a permanently blank control, validation green.
    for (const text of [
      'She was referred by Dr. Ramirez for further evaluation.',
      'The patient was referred by Dr. Alan Whitfield for further evaluation.',
      'Referral from Dr. Lee for evaluation of dysphagia.',
    ]) {
      expect([text, project(text).temporality]).toEqual([text, 'current']);
    }
  });

  it('⚠️ NON-VACUITY: inference still governs a concept that did NOT state them', () => {
    // Without this the arms above are satisfied by hard-wiring every fact to
    // affirmed/current, which would destroy ROS polarity.
    const denied = projectEncounterFacts({
      mode: 'dictation', contextText: 'No fever.', asrQuality: 'high',
      entities: { ros: [{ system: 'constitutional', finding: 'fever', polarity: 'denied', evidence_quote: 'No fever.' }] } as never,
    });
    expect(denied.some((f) => f.polarity === 'denied')).toBe(true);
  });
});

describe('#247 Stage B — one fact per concept AND per approved tense', () => {
  it('⚠️ two controls demanding different tenses BOTH fill', () => {
    // The first draft kept the first mapping per concept: control 2 came back
    // `not_mentioned / temporality_not_approved` — silently blank — and with
    // `required: true` it was `needs_clinician_input`, blocking, whole document
    // withheld. The outcome depended on the order of the mappings array.
    const fields = [field(NAME_ID, 'Patient'), field(REFERRER_ID, 'Patient Name')];
    const mappings = [
      mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name, { temporality: 'current' }),
      mapping(REFERRER_ID, RECORD_DERIVED_CONCEPTS.name, { temporality: 'historical' }),
    ];
    const facts = withVisitMetadataFacts({ fields, mappings, facts: [], patient: PATIENT, visitDate: VISIT });
    expect(facts).toHaveLength(2);
    expect(facts.map((f) => f.temporality).sort()).toEqual(['current', 'historical']);
    const res = resolveTemplateFields({ fields, mappings, facts, certifiedFieldIds: [NAME_ID, REFERRER_ID] });
    expect(res.map((r) => r.value)).toEqual(['Jane Alvarez', 'Jane Alvarez']);
  });

  it('⚠️ NON-VACUITY: agreeing mappings still mint exactly ONE fact', () => {
    const fields = [field(NAME_ID, 'Patient'), field(REFERRER_ID, 'Patient Name')];
    const mappings = [
      mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
      mapping(REFERRER_ID, RECORD_DERIVED_CONCEPTS.name),
    ];
    expect(withVisitMetadataFacts({ fields, mappings, facts: [], patient: PATIENT, visitDate: VISIT }))
      .toHaveLength(1);
  });
});

describe('#247 Stage B — the injector will not fill a shape that cannot carry the value', () => {
  it('⚠️ a BOOLEAN mapping gets nothing, however it came to exist', () => {
    // The classifier now refuses to call a checkbox `visit_metadata` — but a
    // certified mapping is DATA, restored and hand-editable, and the classifier
    // does not run again at fill time. This is the second wall.
    const f = field(NAME_ID, 'Patient');
    const m = mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name, { expectedDataType: 'boolean' });
    expect(withVisitMetadataFacts({ fields: [f], mappings: [m], facts: [], patient: PATIENT, visitDate: VISIT }))
      .toHaveLength(0);
    for (const t of ['date', 'single_select', 'multi_select', 'measurement']) {
      const bad = mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name, { expectedDataType: t });
      expect([t, withVisitMetadataFacts({ fields: [f], mappings: [bad], facts: [], patient: PATIENT, visitDate: VISIT }).length])
        .toEqual([t, 0]);
    }
  });

  it('⚠️ NON-VACUITY: text and number still fill', () => {
    const f = field(NAME_ID, 'Patient');
    for (const t of ['text', 'number']) {
      const m = mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name, { expectedDataType: t });
      expect([t, withVisitMetadataFacts({ fields: [f], mappings: [m], facts: [], patient: PATIENT, visitDate: VISIT }).length])
        .toEqual([t, 1]);
    }
  });
});

// ---------------------------------------------------------------------------
// 7 · THE CERTIFICATION ARTIFACT.
// ---------------------------------------------------------------------------
describe('#247 Stage B — the certification artifact still never holds a record value', () => {
  it('the shipped predicate refuses one, whichever side of the fill it arrives on', () => {
    // Stage A guarded this function's INPUT. Stage B made injection possible
    // one layer BELOW that check, so the predicate is now also driven over the
    // produced manifest's own fact list — the artifact the ruling names.
    const injected = withVisitMetadataFacts({
      fields: [field(NAME_ID, 'Patient')],
      mappings: [mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name)],
      facts: [], patient: PATIENT, visitDate: VISIT,
    });
    expect(injected).toHaveLength(1);
    expect(() => assertNoRecordDerivedFacts(injected)).toThrow(/certification/i);
  });

  it('⚠️ NON-VACUITY: an ordinary dictated fact set passes', () => {
    expect(() => assertNoRecordDerivedFacts([fact()])).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// 6 · RULING #264 — THE BLANK IS NAMED, ALL THE WAY TO THE MANIFEST.
// ---------------------------------------------------------------------------
describe('#264 — a refused age reaches the resolver as a NAMED reason', () => {
  const fields = [field(NAME_ID, 'Patient'), field(AGE_ID, 'Age')];
  const mappings = [
    mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
    mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age),
  ];
  /** DOB 1958-06-14 against an instant inside the ±26h birthday window. */
  const AMBIGUOUS_VISIT = '2026-06-14T02:00:00Z';

  it('the injector NAMES the refusal instead of skipping silently', () => {
    const refusals: Array<{ fieldId: string; unfilled: string; required: string }> = [];
    const out = withVisitMetadataFacts({
      fields,
      mappings,
      facts: [],
      patient: PATIENT,
      visitDate: AMBIGUOUS_VISIT,
      refusals,
    });

    // the NAME still fills — the refusal is narrow, not a blanket
    expect(out.map((f) => f.concept)).toEqual([RECORD_DERIVED_CONCEPTS.name]);
    expect(refusals).toEqual([
      {
        fieldId: AGE_ID,
        unfilled: 'age_timezone_ambiguous',
        required: 'required_age_timezone_ambiguous',
      },
    ]);
  });

  it('names NOTHING when the age is unambiguous — the collector is not noise', () => {
    const refusals: Array<{ fieldId: string; unfilled: string; required: string }> = [];
    const out = withVisitMetadataFacts({
      fields,
      mappings,
      facts: [],
      patient: PATIENT,
      visitDate: VISIT,
      refusals,
    });
    expect(out).toHaveLength(2);
    expect(refusals).toEqual([]);
  });

  it('⚠️ THE WHOLE POINT — the manifest says WHY, not "nobody said it"', () => {
    const refusals: Array<{ fieldId: string; unfilled: string; required: string }> = [];
    const facts = withVisitMetadataFacts({
      fields,
      mappings,
      facts: [],
      patient: PATIENT,
      visitDate: AMBIGUOUS_VISIT,
      refusals,
    });

    const withReason = resolveTemplateFields({ fields, mappings, facts, refusals });
    const age = withReason.find((f) => f.fieldId === AGE_ID)!;

    // BLANK — unchanged, and that half was already true
    expect(age.value).toBeNull();
    // and NAMED — this is what #264 adds
    expect(age.reasonCode).toBe('age_timezone_ambiguous');

    // ⚠️ THE CONTROL THAT MAKES THE ARM MEAN SOMETHING: the SAME facts without
    // the refusals threaded through report `fact_not_mentioned` — "nobody said
    // it" — which is the misleading label this ruling exists to remove. If the
    // plumbing were inert, both branches would read the same and the arm above
    // would pass for the wrong reason.
    const withoutReason = resolveTemplateFields({ fields, mappings, facts });
    const ageBefore = withoutReason.find((f) => f.fieldId === AGE_ID)!;
    expect(ageBefore.value).toBeNull();
    expect(ageBefore.reasonCode).toBe('fact_not_mentioned');
    expect(ageBefore.reasonCode).not.toBe(age.reasonCode);
  });

  it('⚠️ THE COUNTS *DO* MOVE FOR AN `omit`-POLICY CONTROL — and the movement is correct', () => {
    // ⚠️ THIS ARM ASSERTED THE OPPOSITE AND PASSED VACUOUSLY. The claim was
    // "the counts do not move, because `templateTwinCounts` keys on STATUS".
    // A refutation pass measured it and the claim is FALSE:
    //
    //     notMentioned: status === 'not_mentioned' && reasonCode !== 'omitted_unsupported_default'
    //     omitted:      reasonCode === 'omitted_unsupported_default'
    //                                                            (ir.ts:813-821)
    //
    // Both bucket on **reasonCode**. The original arm passed only because its
    // fixture carried no `unmentionedPolicy: 'omit'`, so neither run could reach
    // the `omitted` bucket and two identical count objects proved nothing.
    //
    // THE MOVEMENT IS THE RIGHT ONE, which is why this arm now pins it rather
    // than preventing it: a refused age is not "the scaffold was deliberately
    // cleared" (#191's `omitted_unsupported_default`), it is "we declined to
    // compute it". `notMentioned` is the truthful bucket, and a doctor reading
    // the omitted count should not be told a refusal was a deliberate clearing.
    const omitMappings = [
      mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
      { ...mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age), unmentionedPolicy: 'omit' },
    ] as typeof mappings;

    const refusals: Array<{ fieldId: string; unfilled: string; required: string }> = [];
    const facts = withVisitMetadataFacts({
      fields,
      mappings: omitMappings,
      facts: [],
      patient: PATIENT,
      visitDate: AMBIGUOUS_VISIT,
      refusals,
    });
    const withRef = resolveTemplateFields({ fields, mappings: omitMappings, facts, refusals });
    const without = resolveTemplateFields({ fields, mappings: omitMappings, facts });

    const cWith = templateTwinCounts(withRef, fields);
    const cWithout = templateTwinCounts(without, fields);

    // the control: without the refusal the field lands in `omitted`
    expect(cWithout.omitted).toBe(1);
    expect(cWithout.notMentioned).toBe(0);
    // and with it, in `notMentioned` — named, not silently cleared
    expect(cWith.omitted).toBe(0);
    expect(cWith.notMentioned).toBe(1);
    // the TOTAL unresolved is unchanged; only which bucket it sits in moves
    expect((cWith.omitted ?? 0) + cWith.notMentioned).toBe(
      (cWithout.omitted ?? 0) + cWithout.notMentioned,
    );
  });

  it('a refusal for a field nobody asked about is inert', () => {
    // Fail-safe: a stale or wrong fieldId in the collector must not blank a
    // field that resolved perfectly well from real evidence.
    const facts = withVisitMetadataFacts({
      fields,
      mappings,
      facts: [],
      patient: PATIENT,
      visitDate: VISIT,
    });
    const out = resolveTemplateFields({
      fields,
      mappings,
      facts,
      refusals: [{ fieldId: `ttf_${'f'.repeat(24)}`, unfilled: 'x', required: 'y' }],
    });
    expect(out.find((f) => f.fieldId === AGE_ID)!.value).toBe('68');
  });
});

describe('#264 — TWO age controls, and the capability change stated at its true size', () => {
  const twoFields = [field(NAME_ID, 'Patient'), field(AGE_ID, 'Age'), field(AGE2_ID, 'Age (header)')];
  const twoMappings = [
    mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
    mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age),
    mapping(AGE2_ID, RECORD_DERIVED_CONCEPTS.age),
  ];

  it('⚠️ EVERY age control gets the named reason — not just the first', () => {
    // ⚠️ THE FIRST VERSION NAMED ONLY ONE. `wanted` is keyed by
    // concept|temporality because ONE fact serves every control that wants it,
    // which is right for fact-minting and wrong for refusals: a refusal is
    // per-FIELD. A document with two Age controls got `age_timezone_ambiguous`
    // on one and `fact_not_mentioned` — "nobody said it" — on the other.
    //
    //   ONE MANIFEST CONTRADICTING ITSELF ABOUT THE SAME VALUE IS WORSE THAN
    //   EITHER LABEL ALONE.
    //
    // Found by a refutation pass, on the module's own documented two-control
    // shape — the header control and the letter's opening line.
    const refusals: Array<{ fieldId: string; unfilled: string; required: string }> = [];
    const facts = withVisitMetadataFacts({
      fields: twoFields,
      mappings: twoMappings,
      facts: [],
      patient: PATIENT,
      visitDate: '2026-06-14T02:00:00Z',
      refusals,
    });
    expect(refusals.map((r) => r.fieldId).sort()).toEqual([AGE_ID, AGE2_ID].sort());

    const out = resolveTemplateFields({
      fields: twoFields,
      mappings: twoMappings,
      facts,
      refusals,
    });
    const codes = out
      .filter((f) => f.fieldId === AGE_ID || f.fieldId === AGE2_ID)
      .map((f) => f.reasonCode);
    expect(codes).toEqual(['age_timezone_ambiguous', 'age_timezone_ambiguous']);
    // and neither is the misleading label
    expect(codes).not.toContain('fact_not_mentioned');
  });

  it('⚠️ ONE fact still serves both when the age IS computable — no regression', () => {
    // The control for the arm above: collecting every field for refusals must
    // not make the injector mint a fact per field.
    const facts = withVisitMetadataFacts({
      fields: twoFields,
      mappings: twoMappings,
      facts: [],
      patient: PATIENT,
      visitDate: VISIT,
    });
    expect(facts.filter((f) => f.concept === RECORD_DERIVED_CONCEPTS.age)).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// 7 · #264 THROUGH THE PRODUCTION ENTRY POINT — the wire, not its two ends.
// ---------------------------------------------------------------------------
describe('#264 — the refusal survives `prepareTemplateTwinFill`, which is the only path production has', () => {
  // ⚠️ THIS BLOCK EXISTS BECAUSE THE REFUTATION PASS PROVED THE OTHER ARMS
  // CANNOT SEE THE WIRE. Every arm in section 6 hand-constructs the `refusals`
  // array and hands it to `withVisitMetadataFacts` and `resolveTemplateFields`
  // directly — so they prove the INJECTOR and the RESOLVER in isolation and
  // never the thing between them. Measured on this branch: deleting BOTH
  // `refusals: injectorRefusals` lines from `fill-engine.ts` left **850 of 850
  // green**.
  //
  //     TWO ENDS PROVEN AND THE WIRE UNPROVEN IS A GREEN THAT MEANS NOTHING,
  //     BECAUSE THE WIRE IS THE ONLY PART PRODUCTION RUNS.
  //
  // ⚠️ AND THE NON-VACUITY CONTROL EARNED ITS KEEP IMMEDIATELY. The first draft
  // bound the age onto a control and the AMBIGUOUS arm passed while the control
  // FAILED — the field was blank on the unambiguous visit too, for an unrelated
  // reason. Without the control this block would have shipped green and proved
  // nothing.
  const WM_IOV = path.resolve(process.cwd(), '../../WM IOV Template.docx');
  const bytes = new Uint8Array(readFileSync(WM_IOV));
  const ir = compileTemplateDocx(bytes);
  const AGE_FIELD = ir.fields.find((f) => f.kind === 'narrative_text')!;

  /** Bind ONE narrative control to the age concept; every other field is inert. */
  const irMappings = ir.fields.map((f) =>
    f.fieldId === AGE_FIELD.fieldId
      ? mapping(f.fieldId, RECORD_DERIVED_CONCEPTS.age)
      : mapping(f.fieldId, null, {
          sourceType: 'manual',
          expectedDataType: f.kind === 'single_select' ? 'single_select' : 'text',
        }),
  );

  async function ageFieldFor(visitDate: string) {
    const prepared = await prepareTemplateTwinFill({
      compiledVersionId: 'cv-264',
      noteTemplateId: 'tpl-264',
      noteTemplateVersion: 1,
      ir,
      mappings: irMappings,
      facts: [],
      certifiedFieldIds: ir.fields.map((f) => f.fieldId),
      source: bytes,
      resolverModelVersion: null,
      validationNow: new Date(visitDate),
      visitDate: new Date(visitDate),
      patient: PATIENT,
      clinicianOverrides: [],
    } as never);
    const m = (prepared as { manifest: { fields: Array<{ fieldId: string; value: string | null; reasonCode: string }> } })
      .manifest;
    return m.fields.find((f) => f.fieldId === AGE_FIELD.fieldId)!;
  }

  // ⚠️ AN HONEST LIMIT, NAMED RATHER THAN GLOSSED. This harness does NOT achieve
  // a FILL: on the unambiguous visit the injector mints the age fact (proved
  // separately in section 3) and the resolver still declines it, for a binding
  // reason particular to this synthetic mapping set and NOT to the product. So
  // these arms prove the WIRE — that a refusal named by the injector survives
  // `prepareTemplateTwinFill` into the manifest — and they do not prove the fill.
  // Saying which half is proved is the whole discipline; an unverified step named
  // honestly is worth more than a green tick.
  //
  // The DIFFERENTIAL is what makes that sufficient. Cut the wire and BOTH visits
  // read `fact_not_mentioned`; with it live they differ, and only one input can
  // produce the named token.
  it('⚠️ NON-VACUITY CONTROL FIRST — the token is NOT what this path says about every visit', async () => {
    const age = await ageFieldFor(VISIT);
    expect(
      age.reasonCode,
      'an unambiguous visit must NOT carry the ambiguity token — else the arm below is vacuous',
    ).not.toBe('age_timezone_ambiguous');
    expect(age.reasonCode).toBe('fact_not_mentioned');
  });

  it('an AMBIGUOUS visit arrives in the manifest NAMED, not as "nobody said it"', async () => {
    const age = await ageFieldFor('2026-06-14T02:00:00.000Z');
    expect(age.value).toBeNull();
    // ⚠️ THE ASSERTION THAT DIES IF THE WIRE IS CUT. With the fill-engine
    // threading removed this reads `fact_not_mentioned`, and before this block
    // existed no arm in the file noticed.
    expect(age.reasonCode).toBe('age_timezone_ambiguous');
  });
});

// ---------------------------------------------------------------------------
// 8 · RULING #272 — A RECORD-DERIVED REFUSAL NEVER WITHHOLDS A DOCUMENT.
// ---------------------------------------------------------------------------
describe('#272 — a REQUIRED control with an ambiguous age still RENDERS', () => {
  // ⚠️ THIS IS THE OWNER-CLASS (b) QUESTION #1057 SURFACED, NOW DECIDED.
  // `requiresInput` turns a blank into `needs_clinician_input`;
  // `validation/index.ts:583-586` makes that BLOCKING on
  // `critical || field.required || mapping.required`; `fill-engine.ts:198` turns
  // a blocking issue into `render: null`. So on a required control the refusal
  // did not blank a field — it withheld the whole document.
  //
  //   A WITHHELD CONSULT OVER ONE AMBIGUOUS AGE IS THE WRONG TRADE.
  //   A DOCTOR TYPING "61" IS THE RIGHT ONE.
  //
  // ⚠️ AND THE TARGET BEHAVIOUR IS NOT INVENTED HERE — IT IS THE MANUAL FIELD'S,
  // which the ruling names: `manual_source_not_filled` returns `not_mentioned`,
  // renders blank, and goes to the doctor. Its own comment records the cost of
  // the alternative: "four such fields refused the native document on every
  // visit, forever … the only effect was that the doctor never got their own
  // form back."
  const REQUIRED_AGE = { ...mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age), required: true } as ReturnType<typeof mapping>;
  const fields = [field(NAME_ID, 'Patient'), field(AGE_ID, 'Age')];
  const mappings = [mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name), REQUIRED_AGE];
  const AMBIGUOUS = '2026-06-14T02:00:00.000Z';

  function resolve(visitDate: string) {
    const refusals: Array<{ fieldId: string; unfilled: string; required: string }> = [];
    const facts = withVisitMetadataFacts({
      fields,
      mappings,
      facts: [],
      patient: PATIENT,
      visitDate,
      refusals,
    });
    // ⚠️ THE SAME FACTS GO TO BOTH. The first draft passed `facts: []` to the
    // validator while the resolutions cited facts the injector had minted, and
    // the validator correctly reported SOURCE_FACT_MISSING /
    // EVIDENCE_ANCHOR_UNTRACEABLE / ASSERTION_NOT_SUPPORTED on the NAME field.
    // Those were my fixture, not the product — and they would have masked the
    // one blocking issue this block is actually about.
    return { resolutions: resolveTemplateFields({ fields, mappings, facts, refusals }), facts };
  }

  it('⚠️ THE ARM THE RULING NAMES — blank, NAMED, and NOT needs_clinician_input', () => {
    const age = resolve(AMBIGUOUS).resolutions.find((f) => f.fieldId === AGE_ID)!;
    expect(age.value).toBeNull();
    expect(age.reasonCode).toBe('age_timezone_ambiguous');
    // the whole point: NOT the status that blocks
    expect(age.status).toBe('not_mentioned');
    expect(age.status).not.toBe('needs_clinician_input');
  });

  it('and validation does NOT block — so the document is not withheld', () => {
    const { resolutions, facts } = resolve(AMBIGUOUS);
    const v = validateTemplateTwin({
      fields,
      mappings,
      resolutions,
      facts,
    } as never) as { valid: boolean; issues: Array<{ code: string; severity: string }> };
    expect(v.valid, JSON.stringify(v.issues)).toBe(true);
    expect(v.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
  });

  it('⚠️ NON-VACUITY — the SAME required control DOES block for an unrelated reason', () => {
    // Without this the arms above could pass because validation blocks nothing
    // for this fixture at all, and the ruling would be "proved" by a fixture
    // that cannot block. `clinical_concept_unmapped` is a different route into
    // `needs_clinician_input` — one #272 deliberately does NOT touch.
    const unmapped = [
      mapping(NAME_ID, RECORD_DERIVED_CONCEPTS.name),
      { ...mapping(AGE_ID, null), required: true },
    ] as typeof mappings;
    const resolutions = resolveTemplateFields({ fields, mappings: unmapped, facts: [] });
    const age = resolutions.find((f) => f.fieldId === AGE_ID)!;
    expect(age.status).toBe('needs_clinician_input');
    const v = validateTemplateTwin({
      fields,
      mappings: unmapped,
      resolutions,
      facts: [],
    } as never) as { valid: boolean };
    expect(v.valid, 'the escalation must still work for every OTHER route').toBe(false);
  });

  it('the unambiguous visit is unaffected — it still FILLS', () => {
    const age = resolve(VISIT).resolutions.find((f) => f.fieldId === AGE_ID)!;
    expect(age.value).toBe(String(ageAtDate(PATIENT.dateOfBirth, VISIT)));
  });
});

describe('#272 — the three readers of the refusal vocabulary cannot drift', () => {
  // ⚠️ THIS IS THE ARM THE COMMENTS PROMISE, AND WITHOUT IT THEY ARE A WISH.
  // The vocabulary has THREE readers: the injector mints the tokens, the
  // resolver routes them by CHANNEL, and `validation/index.ts` must reach the
  // same verdict from a reasonCode ALONE. A fifth reason added to the injector
  // and not to `ir.ts`'s list would compile, resolve, and then BLOCK the
  // document — the exact regression #272 ends, through the one door nobody
  // watches.

  it('every reason the injector can EMIT is a member of the shared list', () => {
    // Drive the real function across inputs chosen to reach each arm, and
    // collect what it actually returns rather than restating the list.
    const probes: Array<[string | null, string | null]> = [
      [null, VISIT], // age_input_absent
      ['not a date', VISIT], // age_unparseable
      ['1820-01-01', VISIT], // age_implausible
      ['1958-06-14', '2026-06-14T02:00:00.000Z'], // age_timezone_ambiguous
    ];
    const emitted = new Set<string>();
    for (const [dob, at] of probes) {
      const r = ageAtDateResolved(dob, at);
      if (!r.ok) emitted.add(r.reason);
    }

    // ⚠️ NON-VACUITY: the probe set must reach EVERY reason, or a subset would
    // satisfy the membership test while a missing token went unchecked.
    expect(
      [...emitted].sort(),
      'the probes no longer reach every refusal arm — widen them, do not weaken this',
    ).toEqual([...RECORD_DERIVED_REFUSAL_REASONS].sort());

    for (const reason of emitted) {
      expect(isRecordDerivedRefusal(reason), `${reason} is not in the shared list`).toBe(true);
    }
  });

  it('the predicate REFUSES a non-member — it is not just "any truthy string"', () => {
    for (const other of [
      'fact_not_mentioned',
      'manual_source_not_filled',
      'temporality_not_approved',
      'omitted_unsupported_default',
      '',
      null,
      undefined,
    ]) {
      expect(isRecordDerivedRefusal(other), `${other} must NOT be a record-derived refusal`).toBe(
        false,
      );
    }
  });

  it('⚠️ and the list is what VALIDATION reads — not a copy of it', () => {
    // The membership test above proves the injector agrees with the list. This
    // proves the list is load-bearing at the validator: a reason IN the list
    // produces a warning, one OUTSIDE it produces the blocking arm.
    const fields = [field(AGE_ID, 'Age')];
    const mappings = [{ ...mapping(AGE_ID, RECORD_DERIVED_CONCEPTS.age), required: true }] as ReturnType<typeof mapping>[];
    const judge = (reasonCode: string) => {
      const resolutions = resolveTemplateFields({
        fields,
        mappings,
        facts: [],
        refusals: [{ fieldId: AGE_ID, unfilled: reasonCode, required: `required_${reasonCode}` }],
      });
      const v = validateTemplateTwin({ fields, mappings, resolutions, facts: [] } as never) as {
        valid: boolean;
        issues: Array<{ code: string; severity: string }>;
      };
      return v;
    };

    const member = judge('age_timezone_ambiguous');
    expect(member.valid, JSON.stringify(member.issues)).toBe(true);
    expect(member.issues.some((i) => i.code === 'RECORD_DERIVED_REFUSAL')).toBe(true);

    const stranger = judge('some_reason_nobody_registered');
    expect(stranger.valid, 'an UNREGISTERED reason must still block — fail-closed').toBe(false);
    expect(stranger.issues.some((i) => i.code === 'REQUIRED_FIELD_NOT_MENTIONED')).toBe(true);
  });
});
