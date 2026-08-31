import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  canonicalConcept,
  isRegisteredConcept,
  REGISTRY_SUBCONCEPTS,
  synonymsFor,
} from '../concept-registry';
import { projectEncounterFacts } from '../encounter-facts';
import { isListValuedNarrative } from '../field-value-derivation';
import { resolveTemplateFields } from '../resolver';
import { MIN_CERTIFIED_FILLED_FIELDS } from '../certification-thresholds';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

// ═══════════════════════════════════════════════════════════════════════════
// RULING #159(b) — CONCEPT ALIGNMENT.
//
// The registry's own header says its list was "built from a real extraction
// run, not from imagination". It was — from the VENOUS run — and it never
// learned the SOAP/consult vocabulary. This gate makes the intersection between
// WHAT THE EMITTER PRODUCES and WHAT THE REGISTRY ADMITS a CI property, which
// is what that header claims it already is.
//
// ⚠️ THE TWO CENSUS ARMS ANSWER DIFFERENT QUESTIONS AND NEITHER IS SUFFICIENT.
// (1a) drives the REAL projection and pins the PROPERTY — it survives renames
// and cannot be satisfied by a spelling. (2a) reads the SOURCE and exists only
// to prove (1a)'s fixture reached every emission site; without it, (1a) passes
// by never exercising a branch. Together they reconcile: sites == covered.
// ═══════════════════════════════════════════════════════════════════════════

/** A payload that reaches EVERY branch of `projectEncounterFacts`. */
const CONTEXT_TEXT = [
  'Patient reports left knee pain beginning three days ago.',
  'History of hypertension.',
  'Taking syntheticmed 10 mg by mouth daily.',
  'Allergic to syntheticpen, causes rash.',
  'Mother had diabetes.',
  'Never smoker. Occasional alcohol. No recreational drugs. Works as an accountant.',
  'Denies fever.',
  'Vascular examination unremarkable.',
  'Venous duplex performed, result normal.',
  'Impression: syntheticcondition.',
  'Plan: follow up in two weeks.',
  'Great saphenous vein diameter 5.2 mm on the right.',
].join('\n');

const FULL_ENTITIES = {
  chief_complaint: {
    statement: 'Left knee pain',
    evidence_quote: 'Patient reports left knee pain beginning three days ago.',
  },
  hpi: {
    onset: 'three days ago',
    duration: 'three days',
    location: 'left knee',
    evidence_quote: 'Patient reports left knee pain beginning three days ago.',
  },
  past_medical_history: [
    { condition: 'Hypertension', evidence_quote: 'History of hypertension.' },
  ],
  medications: [
    {
      name: 'syntheticmed',
      dose: '10 mg',
      route: 'by mouth',
      frequency: 'daily',
      evidence_quote: 'Taking syntheticmed 10 mg by mouth daily.',
    },
  ],
  allergies: [
    {
      substance: 'syntheticpen',
      reaction: 'rash',
      evidence_quote: 'Allergic to syntheticpen, causes rash.',
    },
  ],
  family_history: [
    {
      relation: 'Mother',
      condition: 'Diabetes',
      evidence_quote: 'Mother had diabetes.',
    },
  ],
  social_history: {
    smoking: { status: 'Never smoker', evidence_quote: 'Never smoker. Occasional alcohol. No recreational drugs. Works as an accountant.' },
    alcohol: { status: 'Occasional', evidence_quote: 'Never smoker. Occasional alcohol. No recreational drugs. Works as an accountant.' },
    drugs: { status: 'None', evidence_quote: 'Never smoker. Occasional alcohol. No recreational drugs. Works as an accountant.' },
    occupation: { value: 'Accountant', evidence_quote: 'Never smoker. Occasional alcohol. No recreational drugs. Works as an accountant.' },
  },
  ros: [
    { system: 'constitutional', finding: 'Fever', polarity: 'denied' as const, evidence_quote: 'Denies fever.' },
  ],
  exam_findings: [
    { system: 'vascular', finding: 'Unremarkable', evidence_quote: 'Vascular examination unremarkable.' },
  ],
  tests_mentioned: [
    { test: 'venous duplex', result_if_given: 'normal', evidence_quote: 'Venous duplex performed, result normal.' },
  ],
  assessment_discussed: [
    { finding: 'Syntheticcondition', evidence_quote: 'Impression: syntheticcondition.' },
  ],
  plan_discussed: [
    { item: 'Follow up in two weeks', evidence_quote: 'Plan: follow up in two weeks.' },
  ],
  measurements: [
    {
      segment: 'great saphenous vein',
      laterality: 'right' as const,
      metric: 'diameter' as const,
      value: 5.2,
      unit: 'mm',
      sourceSpan: 'Great saphenous vein diameter 5.2 mm on the right.',
    },
  ],
};

const emittedFacts = (): EncounterFact[] =>
  projectEncounterFacts({
    mode: 'conversation',
    contextText: CONTEXT_TEXT,
    asrQuality: 'high',
    entities: FULL_ENTITIES as never,
  });

/** The four families #159(b) adds, and the shape it deliberately does NOT. */
const ADDED_FAMILIES = ['allergy', 'medication', 'family_history', 'social_history'] as const;
const FILED_NOT_BUILT = ['ros'] as const;

describe('#159(b) — concept alignment: the emitter and the registry agree', () => {
  it('(1a) DRIVEN — every concept the REAL projection emits is registered', () => {
    const facts = emittedFacts();
    const concepts = [...new Set(facts.map((f) => f.concept))].sort();

    // ⚠️ FILED, NOT BUILT — named here so the omission is a recorded choice.
    // `ros.<system>` is emitted and unregistered, and it is NOT #159(b)'s shape:
    // there is no bare `ros` to fold to. Removing this filter must RED this arm.
    const filed = concepts.filter((c) => FILED_NOT_BUILT.some((f) => c.startsWith(`${f}.`)));
    const inScope = concepts.filter((c) => !filed.includes(c));

    const unregistered = inScope.filter((c) => !isRegisteredConcept(c));
    expect({ unregistered, ofTotal: inScope.length }).toEqual({
      unregistered: [],
      ofTotal: inScope.length,
    });

    // ARITHMETIC THAT MUST RECONCILE — a partition with no unnamed bucket.
    expect(inScope.length + filed.length).toBe(concepts.length);
    expect(filed).toEqual(['ros.constitutional']);
  });

  it('(1b) NON-VACUITY — the census is non-empty and reaches all four added families', () => {
    const concepts = new Set(emittedFacts().map((f) => f.concept));
    expect(concepts.size).toBeGreaterThan(15);

    // Each added family must actually appear, or (1a) passes without ever
    // exercising the entries this ruling adds.
    for (const family of ADDED_FAMILIES) {
      const hit = [...concepts].filter((c) => c.startsWith(`${family}.`));
      expect([family, hit.length > 0]).toEqual([family, true]);
    }
    // And the PRE-EXISTING families too, so the arm is not only about the change.
    for (const c of ['chief_complaint', 'past_medical_history', 'assessment', 'plan', 'test.name']) {
      expect([c, concepts.has(c)]).toEqual([c, true]);
    }
  });

  it('(2a) COMPLETENESS — the fixture reached EVERY emission site in the source', () => {
    const src = readFileSync(
      path.join(__dirname, '..', 'encounter-facts', 'index.ts'),
      'utf8',
    );
    // Emission sites: `concept: 'literal'` and `concept: `composed.${...}``.
    const literals = [...src.matchAll(/concept: '([^']+)'/g)].map((m) => m[1]!);
    const composed = [...src.matchAll(/concept: `([a-z_]+)\./g)].map((m) => m[1]!);
    const sites = [...new Set([...literals, ...composed.map((p) => `${p}.*`)])].sort();

    // POSITIVE CONTROL for the scan — if the regexes stop matching, this reds
    // rather than reporting a vacuous zero.
    expect(sites.length).toBeGreaterThan(12);

    const emitted = [...new Set(emittedFacts().map((f) => f.concept))];
    const covered = (site: string) =>
      site.endsWith('.*')
        ? emitted.some((c) => c.startsWith(site.slice(0, -1)))
        : emitted.includes(site);

    const missed = sites.filter((s) => !covered(s));
    expect({ missed, sites: sites.length }).toEqual({ missed: [], sites: sites.length });
  });

  it('(3a) ⚠️ A BARE FAMILY MUST NOT STAND IN FOR ITS MEMBERS — the destruction guard', () => {
    // ⚠️ THIS ARM EXISTS BECAUSE THE SECOND VERSION OF #159(b) DID THE OPPOSITE
    // AND THE MANDATORY PASS MEASURED THE HARM. Seeding sub-concepts into a
    // bare-family mapping's `approvedSynonyms` made every case below go from an
    // honest BLANK to `supported` with ZERO BLOCKING — i.e. onto a signed page:
    //
    //   `medication`     -> "Lisinopril; 10 mg; by mouth; daily; Amlodipine"
    //   `allergy`        -> "Penicillin; anaphylaxis; Cephalexin"
    //   `social_history` -> "Occasional; Accountant"   (on a TOBACCO field)
    //
    // So the property is asserted directly: no family offers its members.
    for (const family of Object.keys(REGISTRY_SUBCONCEPTS)) {
      const offered = synonymsFor(family);
      const members = REGISTRY_SUBCONCEPTS[family]!;
      const leaked = members.filter((m) => offered.includes(m));
      expect([family, leaked]).toEqual([family, []]);
    }

    // NON-VACUITY — `synonymsFor` must still work, or the rows above pass because
    // it returns nothing for everything.
    expect(synonymsFor('assessment')).toContain('impression');
    expect(synonymsFor('measurement.diameter')).toContain('exam.vascular.diameter');
  });

  it('(3b) SUB-CONCEPTS ARE REGISTERED, AND ONLY THE ENTITY-NAMING ONES ACCUMULATE', () => {
    const narrative = {
      fieldId: `ttf_${'a'.repeat(24)}`,
      kind: 'narrative_text',
      rowPrototype: false,
    } as unknown as TemplateField;
    const map = (c: string) =>
      ({ clinicalConcept: c, polarityBehavior: 'explicit_denial_allowed' }) as unknown as SemanticMapping;

    // An ENTITY-NAMING member is a LIST — a doctor's allergy section holds
    // several allergens — so it must accumulate.
    const ACCUMULATES = ['allergy.substance', 'medication.name', 'family_history.condition'];
    // An ATTRIBUTE member is single-valued. `medication.dose` is the one four
    // refutation lenses caught printing "10 mg; 20 mg" onto a form.
    const SINGLE = [
      'allergy.reaction',
      'medication.dose',
      'medication.route',
      'medication.frequency',
      'family_history.relation',
      'social_history.smoking',
      'social_history.alcohol',
      'social_history.drugs',
      'social_history.occupation',
    ];

    // The partition must cover every member exactly once — no unnamed bucket.
    const all = Object.values(REGISTRY_SUBCONCEPTS).flat().sort();
    expect([...ACCUMULATES, ...SINGLE].sort()).toEqual(all);
    expect(all.length).toBe(12);

    for (const c of ACCUMULATES) {
      expect([c, isRegisteredConcept(c)]).toEqual([c, true]);
      expect([c, isListValuedNarrative(narrative, map(c))]).toEqual([c, true]);
    }
    for (const c of SINGLE) {
      expect([c, isRegisteredConcept(c)]).toEqual([c, true]);
      expect([c, isListValuedNarrative(narrative, map(c))]).toEqual([c, false]);
    }

    // Sub-concepts still do NOT fold — canonicalisation is untouched by this
    // ruling, so nothing inherits a family's behaviour by accident.
    for (const c of all) expect([c, canonicalConcept(c)]).toEqual([c, c]);
    // ISOLATING CONTROL — a real SPELLING synonym still folds and accumulates.
    expect(canonicalConcept('impression')).toBe('assessment');
    expect(isListValuedNarrative(narrative, map('impression'))).toBe(true);
  });

  it('(4a) ⚠️ THE (a)-DEPENDENCY, PROVED END TO END — a matched denial BLANKS, it does not kill', () => {
    // #159 says "(b) MUST NEVER LAND BEFORE (a)", because the moment the concept
    // matches, a genuine denial reaches an `explicit_denial_allowed` narrative.
    // Before #157(d) that refused the WHOLE DOCUMENT. This arm makes the
    // ordering constraint a TEST rather than a sentence in a ruling.
    const facts = projectEncounterFacts({
      mode: 'conversation',
      contextText: 'No known drug allergies.',
      asrQuality: 'high',
      entities: {
        allergies: [
          { substance: 'No known drug allergies', evidence_quote: 'No known drug allergies.' },
        ],
      } as never,
    });
    const allergyFact = facts.find((f) => f.concept === 'allergy.substance');
    expect(allergyFact).toBeDefined();
    expect(allergyFact!.polarity).toBe('denied');

    // Fixtures built to the SCHEMAS (the resolver parses, so a cast will not do).
    const SHA64 = 'b'.repeat(64);
    const field = {
      fieldId: `ttf_${'b'.repeat(24)}`,
      kind: 'narrative_text',
      originalLabel: 'Allergies',
      labelSource: 'left_cell',
      displayOrder: 0,
      detectionStatus: 'certified',
      allowedOptions: [],
      rendererBinding: {
        partName: 'word/document.xml',
        bindingType: 'content_control',
        path: '/synthetic/allergies',
        ordinal: 0,
        sdtId: '900',
        tag: null,
        alias: null,
        legacyName: null,
        rowLaterality: 'unknown',
        tableIndex: null,
        rowIndex: null,
        cellIndex: null,
        repeatAncestorPath: null,
        sourceControlSha256: SHA64,
        originalContentSha256: SHA64,
      },
      required: false,
      unknownPolicy: 'blank',
      clinicallyMaterial: true,
      criticality: 'allergy',
      tableId: null,
      rowPrototype: false,
    } as TemplateField;

    const mapping = {
      fieldId: field.fieldId,
      sourceType: 'extraction',
      clinicalConcept: 'allergy.substance',
      // ⚠️ THE SYNONYMS ARE THE POINT. This is what a compile produces AFTER
      // this ruling: `semantic-mapping/index.ts` seeds `approvedSynonyms` from
      // `synonymsFor(concept)`. Before it, this array was empty and no allergy
      // fact could ever match.
      approvedSynonyms: [],
      expectedDataType: 'text',
      polarityBehavior: 'explicit_denial_allowed',
      temporality: null,
      laterality: 'optional',
      unitPolicy: 'not_applicable',
      required: false,
      blankPolicy: 'blank',
      unknownPolicy: 'blank',
      practiceDefault: null,
      status: 'certified',
    } as SemanticMapping;

    const [resolution] = resolveTemplateFields({
      fields: [field],
      mappings: [mapping],
      facts: [allergyFact!],
    });

    // (b) WORKED — the fact was MATCHED. Before this ruling the resolver
    // answered `missing`/`not_mentioned` because no concept could ever match.
    expect(resolution!.reasonCode).not.toBe('clinical_concept_unmapped');
    expect(resolution!.sourceFactIds).toContain(allergyFact!.factId);

    // (a) GOVERNED — blank with the narrative-always-blank token, value null.
    expect(resolution!.status).toBe('denial_withheld');
    expect(resolution!.value).toBeNull();
    expect(resolution!.reasonCode).toBe('denial_withheld_narrative_always_blank');
  });

  it('(5a) THE FILL FLOOR IS NOT THE ADJUSTABLE PART — ruling #159', () => {
    // #159: "The floor never lowers without its own ruling." This ruling is
    // about CONCEPTS, not about the threshold.
    expect(MIN_CERTIFIED_FILLED_FIELDS).toBe(10);
  });
});
