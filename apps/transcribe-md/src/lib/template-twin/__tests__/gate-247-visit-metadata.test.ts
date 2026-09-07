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
  withVisitMetadataFacts,
  RECORD_DERIVED_CONCEPTS,
} from '../visit-metadata';
import {
  EncounterFactSchema,
  SemanticMappingSchema,
  TemplateFieldSchema,
  templateTwinCounts,
  type EncounterFact,
  type SemanticMapping,
  type TemplateField,
} from '../ir';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { decideAutoConfirm } from '../auto-certify-eligibility';
import { projectEncounterFacts } from '../encounter-facts';
import { assertNoRecordDerivedFacts } from '../synthetic-test';

// ---------------------------------------------------------------------------
// FIXTURES — a two-control header, exactly the shape the owner's letter has.
// ---------------------------------------------------------------------------
const NAME_ID = `ttf_${'a'.repeat(24)}`;
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
    expect(classifyFieldSource('Patient')).toBe('visit_metadata');
    expect(classifyFieldSource('Age')).toBe('visit_metadata');
    expect(visitMetadataConceptFor('Patient')).toBe(RECORD_DERIVED_CONCEPTS.name);
    expect(visitMetadataConceptFor('Age')).toBe(RECORD_DERIVED_CONCEPTS.age);
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
  it('counts whole years, and the birthday is the boundary', () => {
    expect(ageAtDate('1958-06-14', '2026-06-13T23:00:00Z')).toBe(67);
    expect(ageAtDate('1958-06-14', '2026-06-14T00:00:00Z')).toBe(68);
    expect(ageAtDate('1958-06-14', '2026-06-15T00:00:00Z')).toBe(68);
  });

  it('⚠️ THE DAY BEFORE A BIRTHDAY IS NOT A ROUNDING ERROR — division by 365.25 gets this wrong', () => {
    // 24 years and 364 days is 24, and any average-year scheme says 24.997 and
    // then rounds. The patient is 24 until the day they are 25.
    expect(ageAtDate('2001-03-02', '2026-03-01')).toBe(24);
    expect(ageAtDate('2001-03-02', '2026-03-02')).toBe(25);
  });

  it('handles a leap-day birth without inventing a birthday', () => {
    expect(ageAtDate('2000-02-29', '2026-02-28')).toBe(25);
    expect(ageAtDate('2000-02-29', '2026-03-01')).toBe(26);
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
    expect(ageAtDate(new Date('1958-06-14T00:00:00Z'), new Date(VISIT))).toBe(68);
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
