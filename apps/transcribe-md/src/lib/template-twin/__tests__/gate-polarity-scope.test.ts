// ============================================================================
// GATE — A DENIAL MUST *GOVERN* THE FACT, NOT MERELY SHARE A SENTENCE WITH IT
// ----------------------------------------------------------------------------
// `inferPolarity` used to test the denial vocabulary against the FLAT
// concatenation `${value} ${quote}`. `no\s+(?:known|current|evidence\s+of)?`
// carries an OPTIONAL qualifier, so it collapses to a bare `no\s+`, and ANY
// mid-sentence " no " flipped the WHOLE fact to 'denied'.
//
// Measured on compiled version `070090d3-95f6-4c69-b658-6a29b5cc273d`:
//
//   assessment  finding "Stable chronic conditions with no acute change"
//               quote   "Assessment: stable chronic conditions with no acute
//                        change in this synthetic example"
//   -> polarity 'denied' -> resolution status 'explicitly_denied' with
//      value: null on a NARRATIVE field -> assertResolutionStatus
//      (note-template-docx/renderer.ts:283-310) refuses that pair ->
//      FIELD_RESOLUTION_INVALID -> the doctor loses the WHOLE DOCUMENT.
//   `validateTemplateTwin` raises NO blocking issue on the way there.
//
// ⚠️ EVERY ROW HERE DRIVES THE REAL `projectEncounterFacts`, THROUGH
// `exam_findings` — a path that does NOT carry a stated polarity, so the
// inference is what answers. The pre-existing narrative gate was blind to all
// of this precisely because it hand-built facts with `polarity` PRE-SET, which
// tests the resolver and never the thing that decides.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  EXPLICIT_DENIAL,
  DENIAL_VOCABULARY,
  projectEncounterFacts,
  type EncounterEntitySnapshot,
} from '../encounter-facts';
import { resolveTemplateFields } from '../resolver';
import type { EncounterFact, SemanticMapping, TemplateField } from '../ir';

// ── 0 · BYTE-IDENTITY OF THE VOCABULARY ─────────────────────────────────────
// The literal exactly as it stood at da7456bd (HEAD of this branch's fork
// point). This entry changes the SCOPE a denial reaches, never the tokens.
const HEAD_EXPLICIT_DENIAL_SOURCE = String.raw`(?:^|[\s,;:])(?:den(?:y|ies|ied)|without|negative\s+for|no\s+(?:known|current|evidence\s+of)?|not\s+taking|never)(?:\b|$)`;
const HEAD_EXPLICIT_DENIAL_FLAGS = 'i';

// ── 1 · THE DRIVER ──────────────────────────────────────────────────────────
type Polarity = EncounterFact['polarity'];

interface Row {
  id: string;
  value: string;
  quote: string;
  /** The polarity a clinician would give this fact. Written down BEFORE the
   *  gate was ever run. */
  expect: Polarity;
  why: string;
  /** The value's casing differs from the quote's, so a case-SENSITIVE locate
   *  returns -1 and the positional arms cannot fire. Asserted, not assumed. */
  caseDivergent?: true;
}

/**
 * Projects one or more exam findings that share a quote and returns the real
 * facts. `exam_findings` is deliberate: `projectEncounterFacts` passes NO
 * `polarity` on that path, so `inferPolarity` is what answers.
 */
function projectFindings(
  quote: string,
  findings: ReadonlyArray<string>,
): EncounterFact[] {
  const facts = projectEncounterFacts({
    mode: 'text',
    contextText: quote,
    entities: {
      exam_findings: findings.map((finding) => ({
        system: 'gastrointestinal',
        finding,
        evidence_quote: quote,
      })),
    },
  });
  // CONTROL: the projection must have produced exactly the facts asked for,
  // carrying the exact strings supplied. A driver that silently drops a fact
  // would let every expectation below pass against nothing.
  expect(facts).toHaveLength(findings.length);
  expect(facts.map((fact) => fact.value)).toEqual([...findings]);
  expect(facts.every((fact) => fact.evidenceQuote === quote)).toBe(true);
  return facts;
}

function polarityOf(row: Row): Polarity {
  return projectFindings(row.quote, [row.value])[0].polarity;
}

/** What the SHIPPED code answered: the unscoped test, on the flat
 *  concatenation. Uses the real exported regex, not a replica. */
function headPolarity(row: Row): Polarity {
  return EXPLICIT_DENIAL.test(`${row.value} ${row.quote}`) ? 'denied' : 'affirmed';
}

function check(rows: ReadonlyArray<Row>): void {
  const wrong = rows
    .map((row) => ({ row, measured: polarityOf(row) }))
    .filter(({ row, measured }) => measured !== row.expect)
    .map(({ row, measured }) => `${row.id}: expected ${row.expect}, measured ${measured} — ${row.why}`);
  expect(wrong).toEqual([]);
}

// ── 2 · THE CORPUS ──────────────────────────────────────────────────────────

/** (a) A DETERMINER HEADS THE VALUE. These must stay denied forever. */
const SHORT_FORM_DENIALS: Row[] = [
  { id: 'a1', value: 'no chest pain', quote: 'Cardiovascular: no chest pain, no palpitations.', expect: 'denied', why: 'bare determiner heads the value' },
  { id: 'a2', value: 'no fever', quote: 'Constitutional: no fever, no chills.', expect: 'denied', why: 'bare determiner heads the value' },
  { id: 'a3', value: 'no shortness of breath', quote: 'Respiratory: no shortness of breath on exertion.', expect: 'denied', why: 'bare determiner heads the value' },
  { id: 'a4', value: 'No cough', quote: 'Respiratory: no cough and no sputum.', expect: 'denied', why: 'capitalised determiner heads the value', caseDivergent: true },
  { id: 'a5', value: 'No known allergies', quote: 'No known allergies.', expect: 'denied', why: 'qualified determiner heads the value' },
  { id: 'a6', value: 'never smoker', quote: 'Social history: never smoker, never drinker.', expect: 'denied', why: '"never" heads the value' },
  { id: 'a7', value: 'no guarding', quote: 'Abdomen: soft, non-tender, no guarding, no rebound.', expect: 'denied', why: 'determiner heads the value; "non-tender" is not a cue' },
  { id: 'a8', value: 'Allergies: no known drug allergies', quote: 'Allergies: no known drug allergies', expect: 'denied', why: 'determiner behind a "Label:" prefix ON THE VALUE' },
];

/** (b) A CUE IN THE QUOTE, BEFORE THE VALUE, IN THE SAME CLAUSE. These are the
 *  shapes that feed a CHECKBOX: the entity is affirmative, the quote negates
 *  it, and only position can tell. */
const NEGATED_BY_QUOTE: Row[] = [
  { id: 'b1', value: 'chest pain', quote: 'The patient denies chest pain.', expect: 'denied', why: 'predicate cue immediately governs the value' },
  { id: 'b2', value: 'melena', quote: 'Negative for melena.', expect: 'denied', why: 'cue at the head of the clause governs the value' },
  { id: 'b3', value: 'dysphagia', quote: 'Patient denies dysphagia.', expect: 'denied', why: 'predicate cue governs the value' },
  { id: 'b4', value: 'guarding', quote: 'Abdomen soft, no guarding.', expect: 'denied', why: 'determiner cue abuts the value' },
  { id: 'b5', value: 'Rebound tenderness', quote: 'Abdomen: soft, without rebound tenderness.', expect: 'denied', why: 'cue immediately precedes the value; the comma sits BEFORE the cue, so this row does NOT pin comma-spanning — g3 does', caseDivergent: true },
  { id: 'b6', value: 'warfarin', quote: 'The patient is not taking warfarin.', expect: 'denied', why: 'multi-word predicate cue governs the value' },
];

/** (c) THE VALUE IS NOT LOCATABLE IN ITS OWN QUOTE — keep the shipped answer. */
const NOT_LOCATABLE: Row[] = [
  { id: 'c1', value: 'Denies tobacco use', quote: 'He says he has never smoked.', expect: 'denied', why: 'paraphrased value; nothing positional can be said, so keep the unscoped answer' },
  { id: 'c2', value: 'Follow-up in three months', quote: 'Plan: continue current medications and review again in three months', expect: 'affirmed', why: 'REAL pinned twin row: paraphrased value, unscoped answer is affirmed' },
];

/** (d) THE VALUE IS THE WHOLE STATEMENT, so (b) has nothing to scan. */
const WHOLE_STATEMENT_DENIALS: Row[] = [
  { id: 'd1', value: 'Patient denies dysphagia.', quote: 'Patient denies dysphagia.', expect: 'denied', why: 'predicate in the statement’s first clause' },
  { id: 'd2', value: 'Denies chest pain.', quote: 'Denies chest pain.', expect: 'denied', why: 'predicate at the head of the statement' },
  { id: 'd3', value: 'Negative for melena.', quote: 'Negative for melena.', expect: 'denied', why: 'predicate at the head of the statement' },
  { id: 'd4', value: 'Not taking warfarin.', quote: 'Not taking warfarin.', expect: 'denied', why: 'multi-word predicate at the head of the statement' },
  { id: 'd5', value: 'Without rebound tenderness.', quote: 'Without rebound tenderness.', expect: 'denied', why: 'predicate at the head of the statement' },
];

/** REAL GI CONSULT PROSE THAT MUST BE AFFIRMED. Every one of these is denied
 *  by the shipped code, and every one costs the whole document. */
const GI_PROSE_AFFIRMED: Row[] = [
  { id: 'e1', value: 'Reflux disease, well controlled', quote: 'Impression: reflux disease, well controlled, patient denies dysphagia.', expect: 'affirmed', why: 'the cue is AFTER the value and does not reach back', caseDivergent: true },
  { id: 'e2', value: 'Colitis without alarm features', quote: 'Impression: chronic colitis without alarm features.', expect: 'affirmed', why: 'the cue is inside the value, qualifying it, not governing it', caseDivergent: true },
  { id: 'e3', value: 'Mild gastritis', quote: 'Impression: mild gastritis, no red flag features.', expect: 'affirmed', why: '"no red flag features" follows the value and does not reach back', caseDivergent: true },
  { id: 'e4', value: 'Reflux disease well controlled', quote: 'Never had a prior endoscopy. Impression: reflux disease well controlled.', expect: 'affirmed', why: 'a denial does not reach across a full stop', caseDivergent: true },
  // ⚠️ ARM (d) MUST *NOT* FIRE HERE. The value sits at offset 0 but covers
  // only part of the clause, so it is a head-anchored FRAGMENT, not the whole
  // statement — and a cue after a fragment does not reach back. Without this
  // row, widening (d) to any start===0 reds nothing.
  { id: 'e5', value: 'Colitis', quote: 'Colitis without alarm features.', expect: 'affirmed', why: 'head-anchored FRAGMENT: (d) must not fire, and the cue follows the value' },
];

/** NON-VACUITY CONTROLS. Without these the gate could be stamping everything
 *  affirmed and still look green. */
const CONTROLS: Row[] = [
  // Substring traps — the vocabulary must not match inside a word.
  { id: 'f1', value: 'Nodule in the left lobe', quote: 'Thyroid: nodule in the left lobe.', expect: 'affirmed', why: '"nodule" must not match "no"', caseDivergent: true },
  { id: 'f2', value: 'None appreciated', quote: 'Murmur: none appreciated.', expect: 'affirmed', why: '"none" is outside the vocabulary — unchanged from HEAD, deliberately', caseDivergent: true },
  { id: 'f3', value: 'Nonspecific abdominal pain', quote: 'Assessment: nonspecific abdominal pain.', expect: 'affirmed', why: '"nonspecific" must not match "no"', caseDivergent: true },
  { id: 'f4', value: 'Neversink syndrome', quote: 'Assessment: neversink syndrome.', expect: 'affirmed', why: '"neversink" must not match "never"', caseDivergent: true },
  // Plainly affirmed rows — if the gate is stamping DENIED, these red.
  { id: 'f5', value: 'Systolic murmur at the apex', quote: 'Cardiovascular: systolic murmur at the apex.', expect: 'affirmed', why: 'no denial anywhere', caseDivergent: true },
  { id: 'f6', value: 'Hepatomegaly', quote: 'Abdomen: hepatomegaly, four centimetres below the costal margin.', expect: 'affirmed', why: 'no denial anywhere', caseDivergent: true },
  { id: 'f7', value: 'Continue current medications', quote: 'Plan: continue current medications and review again in three months', expect: 'affirmed', why: 'REAL pinned twin row, plainly affirmed', caseDivergent: true },
];


/** (g) HOLES THE ADVERSARIAL PASS FOUND, EACH PINNED. Every row below was
 *  GREEN in the gate while a realistic clinical input got the wrong answer —
 *  which is why they exist. Rows g1-g5 are the D1 family: a cue that STARTS
 *  before the value but ENDS inside it used to abort the scan and read the
 *  fact AFFIRMED. On a checkbox that TICKS THE BOX for a finding the record
 *  explicitly denies — the silent direction. */
const D1_CUE_OVERLAPS_VALUE: Row[] = [
  { id: 'g1', value: 'Denies chest pain', quote: 'ROS: denies chest pain.', expect: 'denied', why: 'cue starts at 4 and ends at 11; value starts at 5 — the cue overlaps the value and still governs it', caseDivergent: true },
  { id: 'g2', value: 'Negative for melena', quote: 'GI: negative for melena.', expect: 'denied', why: 'overlapping cue governs', caseDivergent: true },
  { id: 'g3', value: 'Not taking warfarin', quote: 'Medications: not taking warfarin.', expect: 'denied', why: 'overlapping multi-word cue governs', caseDivergent: true },
  { id: 'g4', value: 'known drug allergies', quote: 'Allergies: no known drug allergies', expect: 'denied', why: 'the determiner sits immediately before the value and governs it' },
  { id: 'g5', value: 'evidence of metastatic disease', quote: 'Imaging: no evidence of metastatic disease.', expect: 'denied', why: 'the determiner phrase overlaps the value and governs it' },
];

/** (h) KNOWN RESIDUALS, PINNED SO THEY ARE VISIBLE RATHER THAN ABSENT.
 *  ⚠️ h1-h4 ARE A DELIBERATE, MEASURED CHOICE AGAINST THE ADVERSARIAL PASS.
 *  A whole-statement denial carried by a DETERMINER reads AFFIRMED, because
 *  arm (d) consults the predicate subset. Widening it would deny these — and
 *  would also deny h5, which on a `narrative_text` field is not a blank box
 *  but `explicitly_denied` + null and a REFUSAL OF THE WHOLE DOCUMENT.
 *  Measured trade: widening closes a false affirmation on 0 existing checkbox
 *  fields and breaks 18 live narrative facts. See CLAUSE_PREDICATE's note for
 *  the retirement condition.
 *  ⚠️ EVERY ROW HERE IS ALREADY DENIED BY THE SHIPPED CODE, so none of them is
 *  a regression this entry introduces — they are improvements it declines to
 *  make, which is a different and smaller claim. */
const KNOWN_RESIDUALS: Row[] = [
  { id: 'h1', value: 'There is no evidence of deep vein thrombosis.', quote: 'There is no evidence of deep vein thrombosis.', expect: 'affirmed', why: 'RESIDUAL: determiner-carried whole-statement denial; arm (d) is predicate-only. Harmless on every field kind production has; unsafe the day a checkbox exists' },
  { id: 'h2', value: 'Patient reports no chest pain.', quote: 'Patient reports no chest pain.', expect: 'affirmed', why: 'RESIDUAL: same shape as h1' },
  { id: 'h3', value: 'Has no known drug allergies.', quote: 'Has no known drug allergies.', expect: 'affirmed', why: 'RESIDUAL: same shape as h1' },
  { id: 'h4', value: 'She has never used tobacco.', quote: 'She has never used tobacco.', expect: 'affirmed', why: 'RESIDUAL: same shape as h1, carried by "never"' },
  // ⚠️ h5 IS NOT A RESIDUAL — IT IS THE POINT. This is why arm (d) stays
  // narrow. Widen it and this statement is denied, and a normal chest exam
  // takes the whole document down with it.
  { id: 'h5', value: 'Lungs clear to auscultation, no wheezes or rales.', quote: 'Lungs clear to auscultation, no wheezes or rales.', expect: 'affirmed', why: 'DESIRED: an affirmative exam whose denial is a trailing qualifier must render, not refuse the document' },
  { id: 'h6', value: 'Impression: reflux disease, well controlled, patient denies dysphagia.', quote: 'Impression: reflux disease, well controlled, patient denies dysphagia.', expect: 'denied', why: 'RESIDUAL, and the costly direction: a whole-statement impression with a trailing PREDICATE is denied and loses the document. Note e1 — the same sentence with L3 returning a FRAGMENT — is correctly affirmed, and the owner\'s real assessment entity is a fragment' },
];

/** (i) THE REMAINING SIX ROWS THE PASS REQUIRED, one per green mutation. */
const PASS_REQUIRED_ROWS: Row[] = [
  { id: 'i1', value: 'melena', quote: 'Review of systems is negative for melena.', expect: 'denied', why: 'MID-STATEMENT `negative for` — only a head-anchored instance was pinned before' },
  { id: 'i2', value: 'rebound tenderness', quote: 'Abdomen is soft, without rebound tenderness.', expect: 'denied', why: 'MID-STATEMENT `without`' },
  { id: 'i3', value: 'Patient denies dysphagia', quote: 'Patient denies dysphagia', expect: 'denied', why: 'arm (d) with NO TERMINAL PUNCTUATION — every d-row carries a full stop, and the real pinned entities do not' },
  { id: 'i4', value: 'palpitations', quote: 'Denies chest pain, palpitations.', expect: 'denied', why: 'the cue governs ACROSS A COMMA, which is not a clause break — b5 does not pin this' },
  { id: 'i5', value: 'guarding', quote: 'No fever. Denies guarding.', expect: 'denied', why: 'NEAREST cue governs; a first-cue scan would pick "No" and be blocked by the full stop' },
  { id: 'i6', value: 'Colitis (mild', quote: 'Impression: colitis (mild, quiescent).', expect: 'affirmed', why: 'UNBALANCED METACHARACTER in the value must not throw out of the clinical path' },
];

const ALL_ROWS: Row[] = [
  ...SHORT_FORM_DENIALS,
  ...NEGATED_BY_QUOTE,
  ...NOT_LOCATABLE,
  ...WHOLE_STATEMENT_DENIALS,
  ...GI_PROSE_AFFIRMED,
  ...CONTROLS,
  ...D1_CUE_OVERLAPS_VALUE,
  ...KNOWN_RESIDUALS,
  ...PASS_REQUIRED_ROWS,
];

// ── 3 · THE REAL PINNED ENTITIES ────────────────────────────────────────────
// SYNTHETIC, no PHI. Copied verbatim from `pinnedSyntheticEntities` on compiled
// version 070090d3-95f6-4c69-b658-6a29b5cc273d.
const PINNED_CONTEXT_LINES = [
  'Chief complaint: fatigue and reduced exercise tolerance for three months',
  'Past medical history: hypertension and type 2 diabetes mellitus, both longstanding',
  'lisinopril ten milligrams daily',
  'metformin five hundred milligrams twice daily',
  'Allergies: no known drug allergies',
  'Family history: hypertension in one parent',
  'Assessment: stable chronic conditions with no acute change in this synthetic example',
  'Plan: continue current medications and review again in three months',
];

const PINNED_ENTITIES: EncounterEntitySnapshot = {
  chief_complaint: {
    statement: 'Fatigue and reduced exercise tolerance for three months',
    evidence_quote: 'Chief complaint: fatigue and reduced exercise tolerance for three months',
    speaker: 'Doctor',
  },
  hpi: {
    onset: 'three months ago',
    duration: 'three months',
    quality: 'fatigue and reduced exercise tolerance',
    evidence_quote: 'Chief complaint: fatigue and reduced exercise tolerance for three months',
    speaker: 'Doctor',
  },
  past_medical_history: [
    { condition: 'Hypertension', evidence_quote: 'Past medical history: hypertension and type 2 diabetes mellitus, both longstanding' },
    { condition: 'Type 2 diabetes mellitus', evidence_quote: 'Past medical history: hypertension and type 2 diabetes mellitus, both longstanding' },
  ],
  medications: [
    { name: 'Lisinopril', dose: '10 mg', route: null, frequency: 'daily', evidence_quote: 'lisinopril ten milligrams daily' },
    { name: 'Metformin', dose: '500 mg', route: null, frequency: 'twice daily', evidence_quote: 'metformin five hundred milligrams twice daily' },
  ],
  allergies: [
    { substance: 'No known drug allergies', reaction: null, superseded: false, evidence_quote: 'Allergies: no known drug allergies' },
  ],
  family_history: [
    { relation: 'One parent', condition: 'Hypertension', evidence_quote: 'Family history: hypertension in one parent' },
  ],
  social_history: {},
  ros: [],
  exam_findings: [],
  tests_mentioned: [],
  measurements: [],
  assessment_discussed: [
    { finding: 'Stable chronic conditions with no acute change', evidence_quote: 'Assessment: stable chronic conditions with no acute change in this synthetic example' },
  ],
  plan_discussed: [
    { item: 'Continue current medications', evidence_quote: 'Plan: continue current medications and review again in three months' },
    { item: 'Follow-up in three months', evidence_quote: 'Plan: continue current medications and review again in three months' },
  ],
};

function pinnedFacts(): EncounterFact[] {
  return projectEncounterFacts({
    mode: 'text',
    contextText: PINNED_CONTEXT_LINES.join('\n'),
    asrQuality: 'unknown',
    entities: PINNED_ENTITIES,
  });
}

// ── 4 · CHECKBOX WIRING ─────────────────────────────────────────────────────
const SHA = 'b'.repeat(64);

function syntheticField(seed: string, kind: TemplateField['kind']): TemplateField {
  return {
    fieldId: `ttf_${seed.repeat(24).slice(0, 24)}`,
    kind,
    originalLabel: `Synthetic ${kind}`,
    labelSource: 'alias',
    displayOrder: 0,
    detectionStatus: 'certified',
    allowedOptions: [],
    rendererBinding: {
      partName: 'word/document.xml',
      bindingType: 'content_control',
      path: `/synthetic/${seed}`,
      ordinal: 0,
      sdtId: '1',
      tag: null,
      alias: null,
      legacyName: null,
      rowLaterality: 'unknown',
      tableIndex: null,
      rowIndex: null,
      cellIndex: null,
      repeatAncestorPath: null,
      sourceControlSha256: SHA,
      originalContentSha256: SHA,
    },
    required: false,
    unknownPolicy: 'blank',
    clinicallyMaterial: true,
    criticality: 'routine',
    tableId: null,
    rowPrototype: false,
  };
}

function syntheticMapping(
  field: TemplateField,
  concept: string,
  expectedDataType: SemanticMapping['expectedDataType'],
  polarityBehavior: SemanticMapping['polarityBehavior'],
): SemanticMapping {
  return {
    fieldId: field.fieldId,
    sourceType: 'extraction',
    clinicalConcept: concept,
    expectedDataType,
    polarityBehavior,
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

/** Drives the REAL resolver with the REAL projected fact. */
function checkboxValue(row: Row): unknown {
  const field = syntheticField('c', 'checkbox');
  const [resolution] = resolveTemplateFields({
    fields: [field],
    mappings: [
      syntheticMapping(field, 'exam.gastrointestinal', 'boolean', 'explicit_denial_allowed'),
    ],
    facts: projectFindings(row.quote, [row.value]),
    certifiedFieldIds: [field.fieldId],
  });
  return resolution.value;
}

// ============================================================================

describe('a denial must GOVERN the fact, not merely share a sentence with it', () => {
  // ── THE VOCABULARY IS UNCHANGED ───────────────────────────────────────────
  it('rebuilds EXPLICIT_DENIAL byte-identically from the factored token list', () => {
    expect(EXPLICIT_DENIAL.source).toBe(HEAD_EXPLICIT_DENIAL_SOURCE);
    expect(EXPLICIT_DENIAL.flags).toBe(HEAD_EXPLICIT_DENIAL_FLAGS);
    // …and the rebuild really is a rebuild: the tokens, joined in order, ARE
    // the alternation inside the shipped literal. A hand-kept second copy is
    // how the two would drift.
    const joined = DENIAL_VOCABULARY.map((entry) => entry.token).join('|');
    expect(HEAD_EXPLICIT_DENIAL_SOURCE).toContain(`(?:${joined})`);
  });

  it('splits that vocabulary into two NON-EMPTY roles, each token in exactly one', () => {
    const determiners = DENIAL_VOCABULARY.filter((e) => e.role === 'determiner');
    const predicates = DENIAL_VOCABULARY.filter((e) => e.role === 'predicate');
    expect(determiners.length).toBeGreaterThan(0);
    expect(predicates.length).toBeGreaterThan(0);
    expect(determiners.length + predicates.length).toBe(DENIAL_VOCABULARY.length);
    expect(new Set(DENIAL_VOCABULARY.map((e) => e.token)).size).toBe(DENIAL_VOCABULARY.length);
  });

  // ── THE REPORTED FAILURE, ON THE REAL PINNED DATA ─────────────────────────
  it('THE REFUSAL: the pinned assessment becomes AFFIRMED, and the allergy STAYS DENIED', () => {
    const facts = pinnedFacts();
    // Arithmetic that reconciles: the pinned snapshot projects 18 facts.
    expect(facts).toHaveLength(18);

    const assessment = facts.filter((fact) => fact.concept === 'assessment');
    expect(assessment).toHaveLength(1);
    expect(assessment[0].value).toBe('Stable chronic conditions with no acute change');
    expect(assessment[0].polarity).toBe('affirmed');

    const allergy = facts.filter((fact) => fact.concept === 'allergy.substance');
    expect(allergy).toHaveLength(1);
    expect(allergy[0].value).toBe('No known drug allergies');
    expect(allergy[0].polarity).toBe('denied');
  });

  it('THE REFUSAL CLEARS: the pinned assessment resolves SUPPORTED with a value, not explicitly_denied + null', () => {
    // ord 53 on compiled version 070090d3 — `narrative_text`, concept
    // 'assessment', polarityBehavior 'affirmative_only'. It was the ENTIRE
    // measured refusal set.
    const assessment = pinnedFacts().find((fact) => fact.concept === 'assessment');
    expect(assessment).toBeDefined();
    // ⚠️ the seed must be HEX — `TemplateFieldSchema` pins /^ttf_[a-f0-9]{24}$/.
    const field = syntheticField('e', 'narrative_text');
    const [resolution] = resolveTemplateFields({
      fields: [field],
      mappings: [syntheticMapping(field, 'assessment', 'text', 'affirmative_only')],
      facts: [assessment!],
      certifiedFieldIds: [field.fieldId],
    });
    expect(resolution.status).toBe('supported');
    expect(resolution.value).toBe('Stable chronic conditions with no acute change');
    // ⚠️ THE PAIR THE RENDERER REFUSES, NAMED SO IT CANNOT COME BACK QUIETLY.
    // `assertResolutionStatus` (note-template-docx/renderer.ts:283-310) rejects
    // a NON-CHECKBOX field whose status is supported / explicitly_denied /
    // approved_practice_default while `value` is null — FIELD_RESOLUTION_INVALID,
    // and the doctor loses the WHOLE DOCUMENT rather than one field.
    // HONEST LIMIT: this row asserts the RESOLUTION, not a render. The baseline
    // phase executed the real `renderTemplateDocx` to establish that this pair
    // is what refuses; this row asserts the pair is no longer produced.
    expect(resolution.status).not.toBe('explicitly_denied');
    expect(resolution.value).not.toBeNull();
  });

  it('and the pinned snapshot yields EXACTLY ONE denial — the allergy', () => {
    const denied = pinnedFacts()
      .filter((fact) => fact.polarity === 'denied')
      .map((fact) => `${fact.concept}=${String(fact.value)}`);
    expect(denied).toEqual(['allergy.substance=No known drug allergies']);
    // NON-VACUITY: the other seventeen are affirmed, not some other polarity.
    const polarities = new Set(pinnedFacts().map((fact) => fact.polarity));
    expect([...polarities].sort()).toEqual(['affirmed', 'denied']);
  });

  it('THE CASE-INSENSITIVITY THAT MAKES IT WORK: every pinned value that IS in its quote is invisible to a case-SENSITIVE scan', () => {
    // ⚠️ L3 CAPITALISES the finding; the quote keeps the sentence's own casing.
    // A positional scan keyed on `quote.indexOf(value)` NEVER FIRES on real
    // data — every fact falls through to the unscoped fallback and nothing
    // changes. These are the measured offsets, case-insensitively.
    const expected: ReadonlyArray<[string, string, number]> = [
      ['Stable chronic conditions with no acute change', 'Assessment: stable chronic conditions with no acute change in this synthetic example', 12],
      ['No known drug allergies', 'Allergies: no known drug allergies', 11],
      ['Hypertension', 'Family history: hypertension in one parent', 16],
      ['Hypertension', 'Past medical history: hypertension and type 2 diabetes mellitus, both longstanding', 22],
      ['Continue current medications', 'Plan: continue current medications and review again in three months', 6],
    ];
    for (const [value, quote, offset] of expected) {
      expect(quote.indexOf(value)).toBe(-1);
      expect(quote.toLowerCase().indexOf(value.toLowerCase())).toBe(offset);
    }
  });

  // ── THE CORPUS ────────────────────────────────────────────────────────────
  it('(a) a DETERMINER heading the value still denies', () => check(SHORT_FORM_DENIALS));
  it('(b) a cue in the quote, before the value, in the same clause, denies', () => check(NEGATED_BY_QUOTE));
  it('(c) a value that is not locatable in its quote keeps the shipped answer', () => check(NOT_LOCATABLE));
  it('(d) a whole-statement denial is denied by its PREDICATE', () => check(WHOLE_STATEMENT_DENIALS));
  it('real GI consult prose is AFFIRMED', () => check(GI_PROSE_AFFIRMED));
  it('NON-VACUITY: substring traps and plainly affirmed prose', () => check(CONTROLS));
  // ⚠️ THESE THREE WERE ADDED TO `ALL_ROWS` AND, FOR ONE RUN, ASSERTED BY
  // NOTHING — the meta-tests saw them and no `check()` did. A list that is
  // produced and not worked from is a comment.
  it('(g) a cue OVERLAPPING the value still governs it — the D1 family', () => check(D1_CUE_OVERLAPS_VALUE));
  it('KNOWN RESIDUALS stay exactly as measured, and are visible', () => check(KNOWN_RESIDUALS));
  it('the holes the adversarial pass found are each pinned', () => check(PASS_REQUIRED_ROWS));

  it('the designated case-divergent rows really are invisible to a case-SENSITIVE locate', () => {
    const rows = ALL_ROWS.filter((row) => row.caseDivergent);
    expect(rows.length).toBeGreaterThanOrEqual(12);
    const notDivergent = rows
      .filter((row) => row.quote.indexOf(row.value) !== -1)
      .map((row) => row.id);
    expect(notDivergent).toEqual([]);
  });

  // ── TWO FACTS, ONE SENTENCE, OPPOSITE POLARITIES ──────────────────────────
  it('two findings sharing ONE quote take opposite polarities — the cue reaches forward, never back', () => {
    const [affirmed, denied] = projectFindings(
      'Abdomen is tender in the right upper quadrant, no guarding.',
      ['Tender in the right upper quadrant', 'no guarding'],
    );
    expect(affirmed.polarity).toBe('affirmed');
    expect(denied.polarity).toBe('denied');
    // …and they really do share one evidence anchor, so this is one sentence
    // and not two fixtures wearing a costume.
    expect(affirmed.evidenceQuote).toBe(denied.evidenceQuote);
  });

  it('a denial does NOT reach across a full stop', () => {
    const [denied, affirmed] = projectFindings(
      'Abdomen: no guarding. Tenderness in the right upper quadrant.',
      ['no guarding', 'Tenderness in the right upper quadrant'],
    );
    expect(denied.polarity).toBe('denied');
    expect(affirmed.polarity).toBe('affirmed');
  });

  // ── THE CHECKBOX, THROUGH THE REAL RESOLVER ───────────────────────────────
  it('a quote-negated entity UNTICKS its checkbox, and an affirmed one TICKS it', () => {
    const unticked = NEGATED_BY_QUOTE.map((row) => [row.id, checkboxValue(row)] as const);
    expect(unticked).toEqual(NEGATED_BY_QUOTE.map((row) => [row.id, false]));
    // NON-VACUITY: the checkbox leg is not simply stamping false.
    expect(
      checkboxValue({ id: 'x', value: 'Hepatomegaly', quote: 'Abdomen: hepatomegaly on palpation.', expect: 'affirmed', why: 'control' }),
    ).toBe(true);
  });

  // ── THE BLAST RADIUS, MEASURED ────────────────────────────────────────────
  it('EVERY arm NARROWS: nothing this gate carries becomes denied that the shipped code did not already deny', () => {
    const invented = ALL_ROWS.filter(
      (row) => polarityOf(row) === 'denied' && headPolarity(row) === 'affirmed',
    ).map((row) => row.id);
    expect(invented).toEqual([]);
  });

  it('and the rows it CHANGES are exactly these — the whole blast radius, written down', () => {
    const changed = ALL_ROWS.filter(
      (row) => headPolarity(row) === 'denied' && polarityOf(row) === 'affirmed',
    ).map((row) => row.id);
    expect(changed).toEqual([
      // real GI prose the shipped code denied and lost the document over
      'e1', 'e2', 'e3', 'e4', 'e5',
      // whole-statement narrative whose denial is a trailing qualifier —
      // affirmed now renders the sentence verbatim instead of refusing
      'h1', 'h2', 'h3', 'h4', 'h5',
    ]);
  });

  it('NON-VACUITY: the corpus is not one-sided', () => {
    const denied = ALL_ROWS.filter((row) => row.expect === 'denied');
    const affirmed = ALL_ROWS.filter((row) => row.expect === 'affirmed');
    expect(denied.length).toBeGreaterThanOrEqual(15);
    expect(affirmed.length).toBeGreaterThanOrEqual(10);
    expect(new Set(ALL_ROWS.map((row) => row.id)).size).toBe(ALL_ROWS.length);
    // …and the corpus is not trivially separable: at least four rows carry a
    // denial TOKEN and are still affirmed.
    const tokenBearingAffirmed = affirmed.filter((row) =>
      EXPLICIT_DENIAL.test(`${row.value} ${row.quote}`),
    );
    expect(tokenBearingAffirmed.length).toBeGreaterThanOrEqual(4);
  });
});
