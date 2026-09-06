import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { projectEncounterFacts } from '../encounter-facts';
import { isRegisteredConcept } from '../concept-registry';

/**
 * ⚠️ THE PRODUCER AND THE VALIDATOR HAD DIFFERENT VOCABULARIES, AND NOTHING SAID SO.
 *
 * `encounter-facts` emitted `ros.<system>`; `isRegisteredConcept` had patterns
 * for `test.*`, `exam.*` and `hpi.*` and none for `ros.*`. The mapping proposer
 * offers the model `'ros.<system>'` one line above `'exam.<system>'`, then nulls
 * whatever the registry refuses — so every ROS proposal was discarded silently,
 * for every doctor, and the six ROS controls on a per-clause form could never
 * certify (`fieldsReady` demands a concept on any non-`manual` field).
 *
 * A census of either file alone reads fine. The defect lives only in the
 * RELATION between them.
 *
 * ⚠️ AND THE FIRST VERSION OF THIS GATE REPORTED THREE FALSE FINDINGS, WHICH IS
 * WHY IT DRIVES THE REAL FUNCTION NOW. It parsed the emitter's template
 * literals and substituted a slug into each — but `medication.${field}` and
 * `measurement.${m.metric}` substitute ENUM MEMBERS, not slugs, and
 * `test.${…}.result` carries a SUFFIX the prefix-extraction dropped. So it
 * accused `medication.upper_gi`, `measurement.upper_gi` and `test.upper_gi` —
 * three strings the emitter can never produce. A predicate that merely
 * RESEMBLES the shipped one is not evidence about the shipped one.
 */
const EMITTER = join(__dirname, '..', 'encounter-facts', 'index.ts');

const ev = (q: string) => ({ evidence_quote: q });

/**
 * A snapshot populating EVERY entity family, so the real projector emits every
 * concept it is capable of emitting.
 */
const MAXIMAL = {
  chief_complaint: { ...ev('here for reflux'), statement: 'reflux' },
  measurements: (['diameter', 'reflux_time', 'velocity', 'length', 'depth'] as const).map(
    (metric) => ({
      segment: 'gsv',
      laterality: 'left' as const,
      metric,
      value: 7,
      unit: 'mm',
      sourceSpan: 'seven millimetres',
    }),
  ),
  hpi: {
    ...ev('burning for three months, worse at night'),
    onset: 'three months', duration: 'three months', quality: 'burning',
    severity: 'moderate', location: 'epigastric', timing: 'nocturnal',
    context: 'after meals', modifying_factors: 'antacids help',
    associated_symptoms: 'nausea',
  },
  past_medical_history: [{ ...ev('history of hypertension'), condition: 'hypertension' }],
  medications: [{
    ...ev('lisinopril ten milligrams by mouth daily'),
    name: 'lisinopril', dose: '10 mg', route: 'by mouth', frequency: 'daily',
  }],
  allergies: [{ ...ev('penicillin causes anaphylaxis'), substance: 'penicillin', reaction: 'anaphylaxis' }],
  family_history: [{ ...ev('father had colon cancer'), relation: 'father', condition: 'colon cancer' }],
  social_history: {
    smoking: { ...ev('former smoker'), status: 'former' },
    alcohol: { ...ev('social drinker'), status: 'social' },
    drugs: { ...ev('denies recreational drugs'), status: 'none' },
    occupation: { ...ev('works as an accountant'), value: 'accountant' },
  },
  ros: [{ ...ev('reports nausea'), system: 'Upper GI', finding: 'nausea', polarity: 'affirmed' as const }],
  exam_findings: [{ ...ev('abdomen soft'), system: 'Abdomen', finding: 'soft' }],
  tests_mentioned: [{ ...ev('EGD showed mild gastritis'), test: 'EGD', result_if_given: 'mild gastritis' }],
  assessment_discussed: [{ ...ev('impression is GERD'), finding: 'GERD' }],
  plan_discussed: [{ ...ev('start omeprazole'), item: 'start omeprazole' }],
};

const facts = projectEncounterFacts({
  mode: 'text',
  contextText:
    'here for reflux. burning for three months, worse at night. history of hypertension. ' +
    'lisinopril ten milligrams by mouth daily. penicillin causes anaphylaxis. father had colon ' +
    'cancer. former smoker. social drinker. denies recreational drugs. works as an accountant. ' +
    'reports nausea. abdomen soft. EGD showed mild gastritis. impression is GERD. start ' +
    'omeprazole. seven millimetres.',
  entities: MAXIMAL,
});

const concepts = [...new Set(facts.map((f) => f.concept))].sort();
/** `ros.upper_gi` -> `ros`; `test.egd.result` -> `test`. */
const families = [...new Set(concepts.map((c) => c.split('.')[0]))].sort();

describe('every concept the real emitter produces is registered', () => {
  it.each(concepts)('%s is accepted by the registry', (concept) => {
    expect(isRegisteredConcept(concept), `emitted but unregistered: ${concept}`).toBe(true);
  });

  it('THE DRIVE IS COMPLETE — every emission site in the file is reached', () => {
    // ⚠️ Driving the real function is only as good as the INPUT. A family the
    // snapshot forgot to populate would be silently unchecked — the exact
    // failure this gate exists to catch. So the families actually produced are
    // reconciled against the families the SOURCE can emit.
    const source = readFileSync(EMITTER, 'utf8');
    // ⚠️ NOT ANCHORED TO LINE START. The first version required `^\s*concept:`
    // and so missed the four `social_history.*` emissions, which are written
    // inline inside a one-line `add({…})` — a census that silently under-counted
    // by four, which is the very shape this gate exists to catch.
    const sites = [...source.matchAll(/\bconcept: [`']([a-z0-9_]+)[.`']/g)].map((m) => m[1]);
    const declared = [...new Set(sites)].sort();
    expect(declared.length).toBeGreaterThanOrEqual(7);
    expect(families).toEqual(declared);
  });

  it('is not vacuous — the ros family and every measurement kind are present', () => {
    expect(concepts).toContain('ros.upper_gi');
    expect(concepts).toContain('measurement.reflux_time');
    expect(concepts.length).toBeGreaterThanOrEqual(18);
  });

  it('POSITIVE CONTROL — the registry check can still say no', () => {
    // Shaped exactly like the family that slipped through, and its correct
    // answer is the OPPOSITE of every assertion above.
    expect(isRegisteredConcept('ros_notafamily.upper_gi')).toBe(false);
    expect(isRegisteredConcept('cardiology.murmur')).toBe(false);
  });
});
