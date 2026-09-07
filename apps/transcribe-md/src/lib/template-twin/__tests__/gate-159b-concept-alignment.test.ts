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
import { proposeSemanticMappings } from '../semantic-mapping';
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
  // #246 family 1 — the census asserts the fixture reaches EVERY emission
  // site, so a new site without a fixture row is an unwatched emitter.
  past_surgical_history: [
    { procedure: 'Appendicectomy', evidence_quote: 'Appendicectomy in childhood.' },
  ],
  // #246 family 4 — value is the de-unit'd string, number rides beside it.
  total_time_minutes: { minutes: 45, evidence_quote: 'Total time forty five minutes.' },
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
    marital_status: { status: 'Married', evidence_quote: 'Never smoker. Occasional alcohol. No recreational drugs. Works as an accountant. Married.' },
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
// ⚠️ THE `ros` EXEMPTION IS GONE, AND ITS RETIREMENT CONDITION IS WHY.
// It read "emitted and unregistered by decision" — true only while the concept
// was the system-level `ros.<system>`, which the registry refused. Ruling #179
// made the concept `ros.<system>.<symptom>` and REGISTERED it, so the condition
// that justified the exemption no longer holds and the exemption is deleted
// rather than widened. ros is now in scope and must pass like everything else.
const FILED_NOT_BUILT: readonly string[] = [];

describe('#159(b) — concept alignment: the emitter and the registry agree', () => {
  it('(1a) DRIVEN — every concept the REAL projection emits is registered', () => {
    const facts = emittedFacts();
    const concepts = [...new Set(facts.map((f) => f.concept))].sort();

    // ⚠️ THE FILTER IS KEPT THOUGH THE LIST IS EMPTY, DELIBERATELY. It is the
    // mechanism a future filed-not-built concept would use, and an empty list
    // makes the arithmetic below assert that NOTHING is currently exempt —
    // which is a stronger statement than deleting the partition outright.
    const filed = concepts.filter((c) => FILED_NOT_BUILT.some((f) => c.startsWith(`${f}.`)));
    const inScope = concepts.filter((c) => !filed.includes(c));

    const unregistered = inScope.filter((c) => !isRegisteredConcept(c));
    expect({ unregistered, ofTotal: inScope.length }).toEqual({
      unregistered: [],
      ofTotal: inScope.length,
    });

    // ARITHMETIC THAT MUST RECONCILE — a partition with no unnamed bucket.
    expect(inScope.length + filed.length).toBe(concepts.length);
    expect(filed).toEqual([]);
    // ⚠️ AND ros IS NOW POSITIVELY IN SCOPE, not merely un-exempted. Without
    // this the arm would pass just as happily if the projector stopped emitting
    // ROS altogether — an empty `filed` and an absent concept look identical.
    expect(
      inScope.some((c) => c.startsWith('ros.')),
      'no ros.* concept was emitted at all — the arm is vacuous, not passing',
    ).toBe(true);
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
    // Literal sites: `concept: 'past_medical_history'`.
    const literals = [...src.matchAll(/concept: '([^']+)'/g)].map((m) => m[1]!);
    // COMPOSED SITES ARE KEYED ON THE WHOLE TEMPLATE, NOT ITS PREFIX, AND THE
    // ADVERSARIAL PASS IS WHY. Keying on the prefix collapsed every `test.*`
    // site onto one bucket, and that bucket was discharged by the LITERAL
    // `test.name` emitted somewhere else entirely — so a brand-new unregistered
    // site left this arm GREEN while being wholly unexercised. An arm that
    // reports "covered" for a site the fixture never reached is the exact
    // defect this arm exists to prevent, one level up.
    const composed = [...src.matchAll(/concept: `([^`]+)`/g)].map((m) => m[1]!);
    // ⚠️ FUNCTION-CALL SITES, AND THIS SCAN WAS BLIND TO THEM UNTIL #179.
    // `concept: rosConcept(a, b)` is neither a literal nor a template literal,
    // so BOTH scans above miss it entirely and the ROS emission site simply
    // vanished from this census — the arm stayed green while no longer watching
    // the thing it was built to watch. A composed identifier has no literal in
    // source; the site must be reconstructed from the helper's own shape.
    const calls = [...src.matchAll(/concept: rosConcept\(/g)].map(
      () => 'ros.${system}.${symptom}',
    );
    const sites = [...new Set([...literals, ...composed, ...calls])].sort();

    // POSITIVE CONTROL for the scan — a regex that stopped matching would make
    // this arm vacuous rather than red.
    expect(sites.length).toBeGreaterThan(12);
    expect(composed.length).toBeGreaterThan(3);
    // the call-site scan needs its own control, or its silence reads as absence
    expect(calls.length, 'the rosConcept emission site was not found').toBeGreaterThan(0);

    // ⚠️ ARITHMETIC THAT MUST RECONCILE — AND IT CLOSES THE CLASS THE THREE
    // SCANS ABOVE ONLY CLOSED ONE INSTANCE OF AT A TIME.
    //
    // Each scan above learned about ONE emission form after that form had
    // already gone unwatched: composed sites after a prefix collapse, function
    // calls after `rosConcept` vanished from the census entirely. Every one of
    // those was found by an adversarial pass rather than by this arm, because
    // an unreadable form contributes NOTHING and silence reads as absence.
    //
    // So instead of adding a fourth scan the next time, every `concept:` in the
    // file is CLAIMED by exactly one reader, and anything unclaimed is a
    // finding that names its own line. A new helper — `concept: examConcept(a)`
    // — or a ternary, or a bare identifier, reds here on the day it lands.
    //
    // MEASURED when this was written: 22 occurrences = 13 literal + 5 composed
    // + 1 call + 3 declared non-sites, and the three non-sites are the
    // `concept: string;` type field and the `add()` helper's two
    // `concept: options.concept` pass-throughs — plumbing that RECEIVES a
    // concept from the real sites rather than naming one.
    const NON_SITE_FORMS = [
      /concept: string;/g,           // the snapshot type's own field
      /concept: options\.concept,/g,  // `add()` forwarding a caller's concept
    ];
    const claimed = new Set<number>();
    for (const pattern of [
      /concept: '[^']+'/g,
      /concept: `[^`]+`/g,
      /concept: [a-zA-Z_]+\(/g,
      ...NON_SITE_FORMS,
    ]) {
      for (const m of src.matchAll(pattern)) claimed.add(m.index!);
    }
    const unreadable = [...src.matchAll(/\bconcept:/g)]
      .filter((m) => !claimed.has(m.index!))
      .map((m) => {
        const line = src.slice(0, m.index!).split('\n').length;
        return `${line}: ${src.split('\n')[line - 1]!.trim().slice(0, 90)}`;
      });
    expect(
      unreadable,
      'a `concept:` form this census cannot read — it would be silently ' +
        `unwatched:\n  ${unreadable.join('\n  ')}`,
    ).toEqual([]);
    // NON-VACUITY for the arithmetic itself: if the total scan ever stopped
    // matching, `unreadable` would be empty for the wrong reason.
    expect([...src.matchAll(/\bconcept:/g)].length).toBeGreaterThan(sites.length);

    const emitted = [...new Set(emittedFacts().map((f) => f.concept))];
    const covered = (site: string): boolean => {
      if (!site.includes('${')) return emitted.includes(site);
      const parts: string[] = site.split(/\$\{[^}]*\}/);
      const rx = new RegExp(
        '^' + parts.map((lit: string) => lit.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('[a-z0-9_]+') + '$',
      );
      return emitted.some((c) => rx.test(c));
    };

    // ⚠️ NOTHING IS FILED ANY MORE — #179 registered ros, so the ROS site is
    // held to the same completeness bar as every other emission site and must
    // be REACHED by the fixture rather than excused from it.
    const FILED_SITES: string[] = [];
    const inScope = sites.filter((s) => !FILED_SITES.includes(s));

    const missed = inScope.filter((s) => !covered(s));
    expect({ missed, sites: inScope.length }).toEqual({ missed: [], sites: inScope.length });
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

  it('(3c) ⚠️ THE **MODEL** CANNOT SEED SUB-CONCEPTS EITHER — the production carrier', async () => {
    // ⚠️ (3a) WATCHES `synonymsFor`. THE PRODUCTION CARRIER IS `approvedSynonyms`,
    // AND IT HAS A SECOND AUTHOR. The proposer unions the MODEL's own array in,
    // so "no bare family offers its members" was true of the registry module and
    // FALSE of the system: a model answering `medication` +
    // ['medication.name','medication.dose', …] re-creates the destruction —
    // "Lisinopril; 10 mg; by mouth; daily; Amlodipine", supported, zero
    // blocking, a drug printed with NO DOSE.
    //
    // This arm drives the REAL proposer with a stubbed client, which is the only
    // way to watch the seam where the model's array actually enters.
    const field = {
      fieldId: `ttf_${'c'.repeat(24)}`,
      kind: 'narrative_text',
      originalLabel: 'Current Medications',
      labelSource: 'alias',
      displayOrder: 0,
      detectionStatus: 'recognized',
      allowedOptions: [],
      rendererBinding: {
        partName: 'word/document.xml', bindingType: 'content_control',
        path: '/x/meds', ordinal: 0, sdtId: '1', tag: null, alias: null,
        legacyName: null, rowLaterality: 'unknown', tableIndex: null,
        rowIndex: null, cellIndex: null, repeatAncestorPath: null,
        sourceControlSha256: 'b'.repeat(64), originalContentSha256: 'b'.repeat(64),
      },
      required: false, unknownPolicy: 'blank', clinicallyMaterial: true,
      criticality: 'medication', tableId: null, rowPrototype: false,
    } as unknown as TemplateField;

    const POISON = ['medication.name', 'medication.dose', 'medication.route', 'medication.frequency'];
    const client = {
      complete: async () => ({
        mappings: [{
          fieldId: field.fieldId,
          clinicalConcept: 'medication',
          approvedSynonyms: [...POISON, 'Current Medications'],
          expectedDataType: 'text',
          polarityBehavior: 'value_only',
          temporality: null, laterality: null, unitPolicy: null,
          required: false, blankPolicy: 'blank', unknownPolicy: 'blank',
          practiceDefault: null, status: 'needs_confirmation',
        }],
      }),
    };

    const [mapping] = await proposeSemanticMappings(
      { fields: [field] },
      { practiceId: 'p', userId: null, client: client as never },
    );

    // The concept the model chose SURVIVES — this arm is about synonyms only.
    expect(mapping!.clinicalConcept).toBe('medication');
    // NON-VACUITY — the stub really did offer them, or the row below is empty
    // of meaning.
    expect(POISON.every((p) => isRegisteredConcept(p))).toBe(true);
    // ⚠️ AND NOT ONE REACHES THE MAPPING.
    const leaked = mapping!.approvedSynonyms.filter((sy) => POISON.includes(sy));
    expect(leaked).toEqual([]);
    // ISOLATING CONTROL — a NON-sub-concept synonym the model proposed is KEPT,
    // so the row above measures the filter and not a blanket wipe.
    expect(mapping!.approvedSynonyms).toContain('Current Medications');
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
    const ACCUMULATES = ['allergy.substance', 'medication.name'];
    // An ATTRIBUTE member is single-valued. `medication.dose` is the one four
    // refutation lenses caught printing "10 mg; 20 mg" onto a form.
    const SINGLE = [
      // ⚠️ `family_history.condition` IS HERE, NOT IN ACCUMULATES, AND THE
      // ADVERSARIAL PASS IS WHY. Joining conditions destroys the RELATION —
      // "Diabetes; Hypertension" with no indication of whose — and the relation
      // rides a separate fact that nothing can bind back. Same shape this
      // file's header bans `exam.*` for. Moving it back into ACCUMULATES reds
      // this arm.
      'family_history.condition',
      'allergy.reaction',
      'medication.dose',
      'medication.route',
      'medication.frequency',
      'family_history.relation',
      'social_history.smoking',
      'social_history.alcohol',
      'social_history.drugs',
      'social_history.occupation',
      // #246 family 2 — an ATTRIBUTE, not a list. A person has ONE marital
      // status, so joining several would be as wrong as "10 mg; 20 mg" on a
      // dose. It sits beside occupation for the same reason.
      'social_history.marital_status',
    ];

    // The partition must cover every member exactly once — no unnamed bucket.
    const all = Object.values(REGISTRY_SUBCONCEPTS).flat().sort();
    expect([...ACCUMULATES, ...SINGLE].sort()).toEqual(all);
    // #246 family 2 — 12 -> 13. This count is deliberately hardcoded so that
    // adding a sub-concept forces a reader to decide whether it ACCUMULATES or
    // is SINGLE, which is the whole point of the partition above.
    expect(all.length).toBe(13);

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
