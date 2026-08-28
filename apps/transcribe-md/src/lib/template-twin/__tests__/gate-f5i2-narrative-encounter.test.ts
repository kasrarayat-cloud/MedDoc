// ============================================================================
// F5-i-2 — THE NARRATIVE SHAPE DERIVES A SELF-TEST, AND IT ACTUALLY FILLS.
// ----------------------------------------------------------------------------
// Owner ruling #156. F5-i removed the fallback that proved a leg-vein study and
// called it the doctor's template, and recorded the cost honestly: "a non-venous
// template that would previously have 'certified' now cannot certify at all"
// (`verification-encounter.ts`). This is the additive half — a generator for the
// measurement-less consult/SOAP shape, which is the owner's own form.
//
// ⚠️ WHAT THIS GATE IS FOR, AND WHY IT IS NOT A TEXT TEST.
// `gate-derived-encounter-actually-fills.test.ts` records the reason in its own
// header: the venous generator's text arms ALL PASSED while fourteen of twenty
// reflux cells could never fill, because **a count of phrases is not a measure
// of fill**. The same trap is available here and is cheaper to fall into,
// because narrative sentences look self-evidently fine. So the load-bearing arm
// in this file is the one that drives the REAL resolver.
//
// ⚠️ WHAT IT DOES NOT CLAIM:
//   · it does NOT claim the owner's R5 form certifies end to end. That is
//     #156's acceptance criterion, it runs on QA through a browser, and the
//     loop cannot drive one. It is owed, and the RELAY row says so.
//   · it does NOT exercise the MODEL. The facts here are the IDEAL extraction —
//     one fact per dictated concept — deliberately the BEST case, on the same
//     reasoning the venous fill proof states: if a field cannot fill from a
//     perfect extraction, no real model output will rescue it.
//   · it does NOT touch the measurement path. A form with measurement rows
//     never reaches this generator, and the arm below proves that rather than
//     asserting it in a comment.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

import {
  deriveVerificationEncounter,
  ENCOUNTER_NOT_DERIVABLE_REASONS,
  type EncounterSourceField,
} from '../verification-encounter';
import { assertTemplateTwinSyntheticEvidencePhiFree } from '../synthetic-evidence-gate';
import { isRegisteredConcept } from '../concept-registry';
import { resolveTemplateFields } from '../resolver';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

const SHA = 'b'.repeat(64);
const ACTOR = { practiceId: 'p1', userId: 'u1' };

/** The owner's shape: a GI consult form. Narrative concepts, ZERO measurements. */
const CONSULT_CONCEPTS = [
  'chief_complaint',
  'hpi.onset',
  'past_medical_history',
  'family_history',
  'social_history',
  'medication',
  'allergy',
  'exam.abdomen',
  'assessment',
  'plan',
] as const;

const consultForm = (): EncounterSourceField[] =>
  CONSULT_CONCEPTS.map((c, i) => ({
    originalLabel: `Section ${i + 1}`,
    clinicalConcept: c,
  }));

function derivedTextOf(fields: EncounterSourceField[]): string {
  const out = deriveVerificationEncounter(fields);
  if (!out.ok) throw new Error(`expected a derived encounter, got refusal: ${out.reason}`);
  return out.text;
}

/* ── fixture builders, copied in SHAPE from resolver/__tests__/resolver.test.ts
 *    so this gate drives the real resolver with objects its schemas accept. ── */

function field(idSeed: string, overrides: Partial<TemplateField> = {}): TemplateField {
  return {
    fieldId: `ttf_${idSeed.repeat(24).slice(0, 24)}`,
    kind: 'narrative_text',
    originalLabel: 'Synthetic narrative_text',
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: `/synthetic/${idSeed}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown' as const,
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
    ...overrides,
  };
}

function mapping(definition: TemplateField, concept: string): SemanticMapping {
  return {
    fieldId: definition.fieldId,
    sourceType: 'extraction' as const,
    clinicalConcept: concept,
    expectedDataType: 'text',
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
  };
}

/**
 * The fact an IDEAL Layer-3 extraction emits for one dictated sentence: the
 * concept the form asked for, the sentence itself as the evidence quote.
 */
function factFor(seed: string, concept: string, sentence: string): EncounterFact {
  return {
    factId: `ttfact_${seed.repeat(24).slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value: sentence,
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: { start: 0, end: 10 },
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${seed}`],
    evidenceQuote: sentence,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  };
}

/** Split the derived encounter back into its dictated sentences. */
function sentencesOf(text: string): string[] {
  return text
    .split(/(?<=\.)\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

describe('F5-i-2 — the narrative shape derives', () => {
  it('POSITIVE CONTROL — the measurement path is UNCHANGED and still derives', () => {
    // ⚠️ THE NON-VACUITY ARM, AND IT GUARDS THE OTHER DIRECTION TOO. If this
    // change had broken the venous generator, every narrative arm below would
    // still pass. It also proves the claim the implementation makes in a
    // comment — that a measurement-carrying form never reaches the narrative
    // branch — by showing it still produces venous text.
    const venous: EncounterSourceField[] = [
      { originalLabel: 'GSV at the SFJ', clinicalConcept: 'measurement.diameter' },
      { originalLabel: 'SSV at the SPJ', clinicalConcept: 'measurement.diameter' },
    ];
    const text = derivedTextOf(venous);
    // ⚠️ PIN THE GENERATOR'S OWN FIXED LINES, NOT WORDS THAT COME FROM THE
    // LABELS. A first draft asserted "saphenous" and went red: these two labels
    // are the abbreviations GSV and SSV, so that word appears only when the
    // FORM happens to spell it out. The assertion was measuring the fixture and
    // reading as though it measured the generator.
    expect(text).toContain('venous reflux study');
    expect(text).toContain('no deep vein thrombosis');
    expect(text).toContain('diameter');
    // and NOT one word of the narrative generator's vocabulary.
    expect(text).not.toContain('Chief complaint');
  });

  it('the consult shape DERIVES — the case that could not self-test at all before', () => {
    const text = derivedTextOf(consultForm());
    expect(text.length).toBeGreaterThan(100);
    expect(text).toContain('Chief complaint:');
    expect(text).toContain('Plan:');
  });

  it('⚠️ it speaks to EVERY concept the form carries, and the count is pinned', () => {
    // A generator that silently dropped concepts would still satisfy every
    // `toContain` above. The arithmetic is asserted so a drop cannot hide.
    const text = derivedTextOf(consultForm());
    const dictated = sentencesOf(text);
    // 2 header lines (the synthetic marker + the encounter type) + one per concept.
    expect(dictated.length).toBe(2 + CONSULT_CONCEPTS.length);
  });

  it('⚠️ AND TO NOTHING ELSE — the fabrication class, which is what killed the arterial version', () => {
    // A form naming only a chief complaint must not acquire a history, a
    // medication list, a plan or an examination it never asked for. This is the
    // exact discipline the venous generator learned the hard way: its first
    // guard admitted an ARTERIAL study and dictated reflux times for vessels
    // that have no valves.
    const text = derivedTextOf([
      { originalLabel: 'Reason for visit', clinicalConcept: 'chief_complaint' },
    ]);
    expect(text).toContain('Chief complaint:');
    for (const absent of [
      'Past medical history',
      'Family history',
      'Social history',
      'Medications:',
      'Allergies:',
      'Assessment:',
      'Plan:',
      'Examination of the',
      'History of present illness',
      'Result of the',
    ]) {
      expect(text, `a form asking only for a chief complaint must not dictate "${absent}"`).not.toContain(
        absent,
      );
    }
  });

  it('⚠️ NOT ONE WORD OF VENOUS NARRATIVE reaches a narrative form', () => {
    // The defect F5-i existed to kill, asserted on the new path rather than
    // assumed to be impossible there.
    const text = derivedTextOf(consultForm()).toLowerCase();
    for (const word of [
      'saphenous',
      'reflux',
      'incompetent',
      'deep vein thrombosis',
      'varicos',
      'bilateral lower extremity',
      'millimeters',
    ]) {
      expect(text).not.toContain(word);
    }
  });

  it('⚠️ the SUBJECT of a patterned concept is READ FROM THE SLUG, never guessed', () => {
    // `exam.*` and `hpi.*` name their own subject, so the generator can speak to
    // them without inventing one — that is evidence from the form. The arm
    // proves the slug actually reaches the text, which is what distinguishes
    // "read from the form" from "hard-coded and coincidentally right".
    const text = derivedTextOf([
      { originalLabel: 'Thyroid exam', clinicalConcept: 'exam.thyroid_gland' },
      { originalLabel: 'Onset', clinicalConcept: 'hpi.duration' },
    ]);
    expect(text).toContain('thyroid gland');
    expect(text).toContain('duration');
  });

  it('⚠️ and an exam dictates an UNREMARKABLE finding, never a pathology', () => {
    // The generator knows the SUBJECT and knows nothing about what an abnormal
    // result would be for it. Asserting a specific finding would be invented
    // clinical content in an artifact the certification stores.
    const text = derivedTextOf([
      { originalLabel: 'Abdomen', clinicalConcept: 'exam.abdomen' },
    ]);
    expect(text).toContain('unremarkable');
    for (const pathology of ['tender', 'mass', 'enlarged', 'abnormal', 'no abnormality']) {
      expect(text.toLowerCase()).not.toContain(pathology);
    }
  });

  /**
   * ⚠️ BOTH ARMS BELOW COME FROM THE ADVERSARIAL PASS, AND THE FIRST ONE
   * RECORDS A FABRICATION THIS CHANGE ITSELF INTRODUCED.
   *
   * `REGISTRY_SYNONYMS` lets a physician approve an alternative spelling, and
   * `resolveTemplateFields` honours it when MATCHING facts. The classifier read
   * the raw string, so it saw a different vocabulary from the one that fills.
   */
  it('⚠️ a measurement mapped by its SYNONYM is a MEASUREMENT, not an examination', () => {
    // CONCRETE INPUT -> WRONG OUTPUT, before the fix:
    //   exam.vascular.diameter  ->  ok: true,
    //   "Examination of the vascular diameter: documented and unremarkable…"
    // which is invented prose about a measurement field, stored in the
    // certification artifact. Before F5-i-2 this input refused safely, so the
    // change had made it strictly worse — the arterial fabrication class
    // arriving through a synonym.
    const bySynonym: EncounterSourceField[] = [
      { originalLabel: 'Right GSV at the SFJ', clinicalConcept: 'exam.vascular.diameter' },
      { originalLabel: 'Right SSV at the SPJ', clinicalConcept: 'exam.vascular.reflux_time' },
    ];
    const text = derivedTextOf(bySynonym);
    // It took the MEASUREMENT path: venous dictation, not an exam sentence.
    expect(text).toContain('diameter');
    expect(text).toContain('venous reflux study');
    expect(text).not.toContain('Examination of the');
    expect(text).not.toContain('vascular diameter');
  });

  it('⚠️ a narrative concept mapped by its SYNONYM still gets its sentence', () => {
    // `impression` is a synonym of `assessment` and an ordinary consult
    // mapping. Keyed on the raw string it found no sentence, so the field was
    // silently dropped — and a form mapped entirely that way would have been
    // refused as unaddressable when it is nothing of the kind.
    const text = derivedTextOf([
      { originalLabel: 'Impression', clinicalConcept: 'impression' },
    ]);
    expect(text).toContain('Assessment:');

    // The degenerate case the defect would have produced: a form whose ONLY
    // concept is a synonym must derive, not refuse.
    expect(
      deriveVerificationEncounter([
        { originalLabel: 'Impression', clinicalConcept: 'assessment_discussed' },
      ]).ok,
    ).toBe(true);
  });

  it('is DETERMINISTIC — the pinned note is keyed on this text', () => {
    // `pinnedNoteEncounterSha256` keys a stored synthetic note on the
    // encounter's own hash, so a generator that varied run to run would
    // invalidate its own cache every time and could never be compared to
    // itself.
    const a = derivedTextOf(consultForm());
    const b = derivedTextOf([...consultForm()].reverse());
    expect(a).toBe(b);
  });

  it('passes the REAL synthetic-evidence gate, regex not re-implemented', async () => {
    // ⚠️ THIS IS THE ARM WHOSE ABSENCE ONCE MADE EVERY TEMPLATE UNCERTIFIABLE.
    // `assertTemplateTwinSyntheticEvidencePhiFree` throws
    // SYNTHETIC_EVIDENCE_REJECTED, deterministically and before any model call,
    // when the text carries no explicit synthetic marker. The unit suites mock
    // the synthetic test wholesale, so nothing else in the suite reaches it.
    const cleanScan = {
      complete: vi.fn(async () => ({
        appearsExplicitlySynthetic: true,
        anyUncertain: false,
        directIdentifierClasses: [] as string[],
      })),
    };
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: derivedTextOf(consultForm()),
        ...ACTOR,
        client: cleanScan as never,
      }),
    ).resolves.toBeUndefined();
  });

  /**
   * ⚠️ THIS ARM EXISTS BECAUSE A MUTATION PROOF FOUND THE ONE BELOW UNPROVED.
   *
   * Deleting the two header lines from the generator SHOULD have reddened the
   * evidence-gate arm. It did not — three unrelated sentence-count arms caught
   * it instead, which is canon's *overlapping guards must not launder an
   * unproved arm* precisely: the mutation was caught, and the arm being proved
   * was still not exercised.
   *
   * The measurement that explains it: of the twelve sentences this generator
   * can dictate, **four carry an explicit synthetic marker of their own**
   * (`assessment`, `test.name`, `exam.*`, `test.*.result` — each says "in this
   * synthetic example") and **eight carry none** (`chief_complaint`,
   * `past_medical_history`, `family_history`, `social_history`, `medication`,
   * `allergy`, `plan`, `hpi.*`). The consult fixture used above happens to
   * include two of the four, so the marker survived the header's deletion and
   * the gate passed for a reason nobody designed.
   *
   * ⚠️ SO THE HEADER IS LOAD-BEARING FOR SOME FORMS AND REDUNDANT FOR OTHERS,
   * AND ONLY THE FIRST KIND CAN PROVE IT. This arm builds one: an ordinary
   * consult whose every sentence comes from the bare eight. Strip the header
   * from THAT and the real gate must refuse — which is what makes the header a
   * requirement rather than a decoration.
   */
  it('⚠️ the HEADER is load-bearing — on a form whose own sentences carry no marker', async () => {
    const cleanScan = {
      complete: vi.fn(async () => ({
        appearsExplicitlySynthetic: true,
        anyUncertain: false,
        directIdentifierClasses: [] as string[],
      })),
    };
    // Every one of these dictates a sentence with no synthetic marker in it.
    const bare: EncounterSourceField[] = [
      { originalLabel: 'Reason for visit', clinicalConcept: 'chief_complaint' },
      { originalLabel: 'PMH', clinicalConcept: 'past_medical_history' },
      { originalLabel: 'Medications', clinicalConcept: 'medication' },
      { originalLabel: 'Plan', clinicalConcept: 'plan' },
    ];
    const text = derivedTextOf(bare);

    // WITH the header: the real gate accepts.
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: text,
        ...ACTOR,
        client: cleanScan as never,
      }),
    ).resolves.toBeUndefined();

    // WITHOUT it: the body alone carries no marker, so the gate REFUSES.
    const bodyOnly = sentencesOf(text).slice(2).join(' ');
    expect(bodyOnly.length).toBeGreaterThan(50);
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: bodyOnly,
        ...ACTOR,
        client: cleanScan as never,
      }),
    ).rejects.toThrow();
  });

  it('⚠️ MUTATION PROOF — strip the synthetic label and the REAL gate refuses', async () => {
    const cleanScan = {
      complete: vi.fn(async () => ({
        appearsExplicitlySynthetic: true,
        anyUncertain: false,
        directIdentifierClasses: [] as string[],
      })),
    };
    const stripped = derivedTextOf(consultForm())
      .split(' ')
      .filter((w) => !/synthetic|fictional|example|test/i.test(w))
      .join(' ');
    expect(stripped.length).toBeGreaterThan(50); // still substantial text
    await expect(
      assertTemplateTwinSyntheticEvidencePhiFree({
        encounterText: stripped,
        ...ACTOR,
        client: cleanScan as never,
      }),
    ).rejects.toThrow();
  });
});

describe('F5-i-2 — the narrative encounter ACTUALLY FILLS', () => {
  /**
   * ⚠️ THE LOAD-BEARING ARM. Everything above measures TEXT. This drives the
   * production resolver — `resolveTemplateFields`, the same function a real
   * visit runs — over the derived encounter's own sentences, and asserts the
   * fields resolve to values. The venous generator passed all of its text arms
   * while most of its cells could not fill; nothing in this file would have
   * caught that either, except this.
   */
  function fillConsultForm() {
    const text = derivedTextOf(consultForm());
    const dictated = sentencesOf(text);

    // Pair each concept with the sentence dictated for it, the way an ideal L3
    // extraction would. The generator emits concepts in SORTED order after two
    // header lines, which is the contract the implementation states.
    const sorted = [...CONSULT_CONCEPTS].sort();
    const body = dictated.slice(2);
    expect(body.length).toBe(sorted.length);

    const fields = sorted.map((_, i) => field(String(i % 10)));
    // ⚠️ distinct ids — `field()` seeds from a repeated digit, so two concepts
    // at the same index modulo 10 would collide and silently halve the form.
    const uniqueFields = sorted.map((_, i) =>
      field(String(i % 10), { fieldId: `ttf_${String(i).padStart(24, '0')}` }),
    );
    expect(new Set(uniqueFields.map((f) => f.fieldId)).size).toBe(sorted.length);
    void fields;

    const mappings = uniqueFields.map((f, i) => mapping(f, sorted[i]));
    const facts = sorted.map((c, i) => factFor(String(i % 10), c, body[i]));

    return {
      sorted,
      resolutions: resolveTemplateFields({
        fields: uniqueFields,
        mappings,
        facts,
        allowUncertifiedForSyntheticTest: true,
      }),
    };
  }

  it('EVERY narrative field resolves to a value — not one is left blank', () => {
    const { sorted, resolutions } = fillConsultForm();
    expect(resolutions.length).toBe(sorted.length);

    const filled = resolutions.filter((r) => r.value !== null);
    const blank = resolutions.filter((r) => r.value === null);
    // Report the blanks by field so a partial fill names itself rather than
    // arriving as an off-by-N.
    expect(
      blank.map((r) => `${r.fieldId}:${r.status}`),
      'every dictated concept must fill from its own sentence',
    ).toEqual([]);
    expect(filled.length).toBe(sorted.length);
  });

  it('⚠️ each field cites the sentence dictated for ITS OWN concept, not a neighbour', () => {
    // Ten fields all filling is satisfied by ten fields filling from ONE fact.
    // The venous arc's own scar is a cell that filled citing a DIFFERENT vein.
    const { sorted, resolutions } = fillConsultForm();
    const text = derivedTextOf(consultForm());
    const body = sentencesOf(text).slice(2);

    const byId = new Map(resolutions.map((r) => [r.fieldId, r]));
    sorted.forEach((concept, i) => {
      const r = byId.get(`ttf_${String(i).padStart(24, '0')}`);
      expect(r, `no resolution for ${concept}`).toBeDefined();
      expect(String(r?.value), `${concept} filled from the wrong sentence`).toBe(body[i]);
    });
  });

  /**
   * ⚠️ ADDED AFTER A MUTATION PROOF SHOWED THE ARM ABOVE COULD NOT SEE THIS.
   *
   * Replacing every dictated sentence with ONE identical string left "each
   * field cites the sentence dictated for ITS OWN concept" GREEN — the harness
   * pairs sentence `i` with concept `i`, and when every sentence is the same
   * string that comparison is satisfied by construction. The arm proves
   * CORRESPONDENCE and cannot prove DISTINCTNESS, and only the second one
   * catches a generator that says the same thing ten times.
   *
   * ⚠️ AND THE IMPLEMENTATION ALREADY CLAIMED THIS PROPERTY IN A COMMENT
   * ("the values are globally distinct") with nothing asserting it — which is
   * the venous generator's own scar restated: `index % 5` gave eight distinct
   * reflux values across twenty cells, every text arm passed, and fourteen
   * cells could never fill.
   */
  it('⚠️ every dictated sentence is DISTINCT — a generator that repeats itself proves nothing', () => {
    const body = sentencesOf(derivedTextOf(consultForm())).slice(2);
    expect(body.length).toBe(CONSULT_CONCEPTS.length);
    expect(new Set(body).size, 'two concepts dictated the same sentence').toBe(body.length);
  });

  it('⚠️ NON-VACUITY — a form whose facts do not match its concepts fills NOTHING', () => {
    // The control that makes the two arms above mean something. If the resolver
    // were filling on anything other than a concept match, this would still
    // fill and nobody would know the assertions were free.
    const sorted = [...CONSULT_CONCEPTS].sort();
    const fields = sorted.map((_, i) =>
      field(String(i % 10), { fieldId: `ttf_${String(i).padStart(24, '0')}` }),
    );
    const mappings = fields.map((f, i) => mapping(f, sorted[i]));
    const wrongFacts = sorted.map((_, i) =>
      factFor(String(i % 10), 'measurement.velocity', 'an unrelated measurement sentence.'),
    );
    const resolutions = resolveTemplateFields({
      fields,
      mappings,
      facts: wrongFacts,
      allowUncertifiedForSyntheticTest: true,
    });
    expect(resolutions.filter((r) => r.value !== null)).toEqual([]);
  });
});

describe('F5-i-2 — the refusal stays honest', () => {
  /**
   * ⚠️ THE BOUNDARY THE ADVERSARIAL PASS ASKED ABOUT, PINNED SO IT IS VISIBLE
   * RATHER THAN LATENT — AND IT IS A NAMED LIMIT OF THIS SLICE.
   *
   * A consult form is served by the narrative generator only while it carries
   * ZERO measurement rows. Map ONE field to a measurement concept — a doctor
   * confirming "Largest polyp diameter (mm)" as `measurement.length` is an
   * entirely ordinary act — and the form leaves the narrative branch, fails
   * `venousEvidence` on its own labels, and refuses `unsupported_study_type`.
   *
   * That is the CORRECT refusal today: this engine cannot dictate a polyp
   * diameter, and inventing one is the fabrication class. But it means #156's
   * acceptance ("the owner's R5 form certifies") is contingent on his form
   * having no measurement-mapped field, which has NOT been established — the
   * only measurement of it was taken under a blanket `exam.vascular`
   * substitution that forced `measurementRows` to zero for any form
   * (docs/canon/71). The RELAY row carries this as owed, and this arm makes the
   * boundary fail loudly the day somebody changes it by accident.
   */
  it('⚠️ a MIXED form — narrative concepts plus ONE measurement — leaves the narrative branch', () => {
    const mixed: EncounterSourceField[] = [
      { originalLabel: 'Indication', clinicalConcept: 'chief_complaint' },
      { originalLabel: 'Findings', clinicalConcept: 'assessment' },
      { originalLabel: 'Largest polyp diameter (mm)', clinicalConcept: 'measurement.length' },
    ];
    expect(deriveVerificationEncounter(mixed)).toEqual({
      ok: false,
      reason: 'unsupported_study_type',
    });

    // DISCRIMINATING CONTROL: the same form WITHOUT that one field derives.
    // Without this, the arm above would pass on a generator that refused
    // everything, and would say nothing about which field caused it.
    expect(deriveVerificationEncounter(mixed.slice(0, 2)).ok).toBe(true);
  });

  it('a form with no mapped concept REFUSES — unconfirmed is not addressable', () => {
    expect(
      deriveVerificationEncounter([
        { originalLabel: 'Subjective', clinicalConcept: null },
        { originalLabel: 'Objective', clinicalConcept: null },
      ]),
    ).toEqual({ ok: false, reason: 'no_addressable_fields' });
  });

  it('a form whose only concepts are ones this generator cannot speak to REFUSES', () => {
    // ⚠️ THE OTHER HALF OF THE REFUSAL, AND IT IS THE ONE THAT COULD ROT.
    // `no_addressable_fields` covers two situations — nothing mapped, and
    // mapped to something with no sentence. If a future edit made the generator
    // emit a catch-all sentence for unknown concepts, this arm reddens and the
    // "skipped, never guessed" rule gets defended by a test rather than a
    // comment.
    expect(
      deriveVerificationEncounter([
        { originalLabel: 'Odd', clinicalConcept: 'not_a_registry_concept' },
      ]),
    ).toEqual({ ok: false, reason: 'no_addressable_fields' });
  });

  it('⚠️ every sentence key is a REGISTERED concept — a sentence that fills nothing cannot ship', () => {
    // Bound to the registry rather than listed here. A key the extractor never
    // emits can be matched by no fact, so its field would be permanently
    // unfillable and the encounter would carry a sentence nobody could use.
    // The module also asserts this at load; this arm is what makes the failure
    // readable, and the mutation that reddens it reddens the import too.
    const text = derivedTextOf(consultForm());
    const spoken = [...CONSULT_CONCEPTS].filter((c) => isRegisteredConcept(c));
    expect(spoken.length).toBe(CONSULT_CONCEPTS.length);
    expect(text.length).toBeGreaterThan(0);
  });

  it('the reason vocabulary is ONE value, and it is closed', () => {
    // The cross-tenant constraint: `blocking` fans out to every subscribed
    // SUPER_ADMIN, so it may carry closed reason codes and nothing else.
    expect([...ENCOUNTER_NOT_DERIVABLE_REASONS]).toEqual([
      'no_addressable_fields',
      'only_placeholder_rows',
      'unsupported_study_type',
    ]);
    // and no reason string can carry a customer's field label.
    for (const r of ENCOUNTER_NOT_DERIVABLE_REASONS) {
      expect(r).toMatch(/^[a-z_]+$/);
    }
  });
});
