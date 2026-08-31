// ============================================================================
// OWNER RULING #157(c) — THE DENIAL CONTRACT, DRIVEN END TO END.
// ----------------------------------------------------------------------------
// ⚠️ #157(c) AMENDS #157(b)'s RULE (1) AND THIS GATE CARRIES BOTH. Everything
// #157(b) proved still holds and is still asserted here; what changed is that a
// denied narrative fact no longer prints its quote merely because it is denied.
//
//   Q1  a denial prints its quote ONLY when the quote ITSELF carries a negation
//       scoping the finding. Otherwise BLANK, reason `denial_quote_not_self_negating`.
//       ⚠️ BOTH PROPERTIES ARE ASSERTED ON EVERY PRINT ROW: the rendered text is
//       a SUBSET of the doctor's quote (nothing MANUFACTURED) and it CONTAINS a
//       negation token scoping the finding (nothing DESTROYED). Arm (1h) pins
//       the exact string that satisfies the first and inverts the second, so a
//       gate carrying only property (i) is demonstrably not enough.
//   Q2  the certification blocker exempts an ENUMERATED allowlist. Arm (7a)
//       asserts SET EQUALITY against what the pipeline really emits for the
//       rule-(4)-approved behaviours, in both directions.
//   Q3  mixed polarity resolves PER FACT, in dictation order — arms (8a)-(8e).
//       `polarity_conflict` as a document-killer dies with its sibling.
//
// ⚠️ AND ARM (1f) WAS REBUILT BECAUSE IT WAS A CONTROL AIMED WHERE THE ANSWER
// WAS PREDETERMINED. Its five KEEP fixtures were all `DENIAL_VOCABULARY` tokens
// and the guard was built from that same list, so it measured its own target
// and stayed green while twelve of fourteen negating headings were stripped and
// printed their inverse. Its KEEP set is now out of vocabulary BY CONSTRUCTION
// and each row asserts that it is.
// ----------------------------------------------------------------------------
// #157(b), unchanged and still gated below:
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE REPLACES A GATE BUILT ON A FALSIFIED PREMISE, AND THE PREMISE IS
// RECORDED HERE BECAUSE THE CORRECTION IS THE POINT.
//
// The original #157 said a narrative field "prints the denial's PROSE", and its
// gate asserted exactly that. The premise was FALSE: `projectEncounterFacts`
// puts the AFFIRMED ENTITY in `fact.value` and the doctor's sentence in
// `fact.evidenceQuote`. Re-measured on this tree, through the real projection:
//
//   "The patient has no history of diabetes."  -> value "Diabetes"
//   "No evidence of pulmonary embolism."       -> value "Pulmonary embolism"
//   "Plan: no further imaging is required."    -> value "Further imaging"
//   "Allergies: no known drug allergies"       -> value "No known drug allergies"
//
// Implementing #157 would have printed **"Diabetes"** into a past-medical-history
// section for a patient said NOT to have it, and `validateTemplateTwin` would
// have returned `valid: true`.
//
// ⚠️⚠️ AND THE PREDECESSOR GATE COULD NOT HAVE SEEN IT — WHICH IS THE MOST
// IMPORTANT SENTENCE IN THIS HEADER. Every fact it used was HAND-BUILT with
//
//     evidenceQuote: `${spec.value} (synthetic dictation, gate 157)`
//
// so the value WAS a prefix of the quote. Under that fixture "prints the value"
// and "prints the quote" are indistinguishable, and the gate was structurally
// blind to the one defect that sank the ruling it was written for. So:
//
// > **EVERY RULE-(1) ROW BELOW DRIVES THE REAL `projectEncounterFacts`, AND THE
// > FIXTURE ASSERTS THE DIVERGENCE IS REAL** — `(pre-2)` fails if a value is a
// > substring of its own quote, which is the condition that made the old gate
// > vacuous.
//
// ⚠️ ZERO COMPOSITION IS ASSERTED AS A PROPERTY, NOT DESCRIBED AS AN INTENTION.
// For every rule-(1) row the text actually extracted from the rendered .docx
// must be a SUFFIX of the doctor's own `evidenceQuote`. Nothing synthesized,
// templated, prefixed or joined can satisfy that — a `"; "` join fails it, a
// `"No " + entity` composition fails it, and the one permitted heading strip
// passes it because it only removes a prefix.
//
// ⚠️ WHAT THIS GATE DRIVES, because a replica of an assertion proves nothing
// about the assertion: the REAL projection (`projectEncounterFacts`), the REAL
// compiler (`compileTemplateDocx`), the REAL resolver (`resolveTemplateFields`),
// the REAL validator (`validateTemplateTwin`) and the REAL, AWAITED
// `renderTemplateDocx`. The renderer recompiles its source and compares field
// hashes, so the IR cannot be hand-built: every field below is one the compiler
// actually emitted from a .docx.
//
// ⚠️ AN AWAITED RENDERER. `renderTemplateDocx` is ASYNC. A probe that calls it
// inside try/catch without `await` reports OK for EVERY input, including the
// ones that MUST fail. Every call below is awaited, through `await` or
// `expect(...).rejects`.
//
// ⚠️ ONE DENIAL AT A TIME FOR THE ASSERTION ARMS, ALL AT ONCE FOR RULE (3). A
// refusal kills the whole package, so a fixture that denies everything makes
// every arm red whenever any single kind regresses — the arms stop
// discriminating and a half-landed fix reads like a full revert. Each assertion
// arm therefore denies only its OWN concept; rule (3)'s matrix denies all of
// them, deliberately, because "does anything refuse?" is exactly the question
// it asks.
//
// ⚠️ WHAT THIS GATE DOES NOT CLAIM:
//   · it does not exercise the MODEL. The L3 entities are the ideal extraction.
//   · `multi_select` CANNOT be driven end to end — `compileTemplateDocx`
//     contains zero occurrences of that kind and can never emit one. Its rule-(2)
//     coverage is at the contract and renderer-predicate level, MEASURED and
//     stated in arm (2d) rather than quietly skipped.
// ============================================================================

import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  compileTemplateDocx,
  inspectDocxPackage,
  renderTemplateDocx,
} from '@/lib/note-template-docx';
import {
  buildSyntheticDocx,
  syntheticOpc,
} from '../../note-template-docx/__tests__/synthetic-docx';
import {
  EncounterFactSchema,
  FieldResolutionSchema,
  templateTwinCounts,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinValidationResult,
} from '../ir';
import { expectedDataTypeForFieldKind } from '../semantic-mapping';
import { resolveTemplateFields } from '../resolver';
import { validateTemplateTwin } from '../validation';
import { projectEncounterFacts } from '../encounter-facts';
import { bridgeTemplateFill } from '../bridge-fill';
import {
  CERTIFICATION_EXEMPT_DENIAL_REASONS,
  denialOutcome,
  denialWithheldMaterialFieldIds,
  isPrintableDenial,
  mixedPolarityNarrative,
  selfNegationCues,
  selfNegationScopingFinding,
  stripLeadingDictationHeading,
} from '../denial-contract';
import { EXPLICIT_DENIAL } from '../encounter-facts';
import { MIN_CERTIFIED_FILLED_FIELDS } from '../certification-thresholds';

// ── the source document ──────────────────────────────────────────────────────
// The shared synthetic package plus the labels this gate needs. The compiler
// infers KIND from the label, so these names are load-bearing:
//   "Allergies" / "Past medical history" / "Plan of care" / "Impression"
//        -> narrative_text  ("Allergies" also -> criticality `allergy`)
//   "Polyp count"     -> number
//   "Lesion diameter" -> measurement
//
// ⚠️ The shared package's DATA-BOUND control is dropped. It compiles
// `detectionStatus: 'unsupported'`, which the resolver answers with
// needs_clinician_input — BLOCKING for a clinically material field — and a
// blocked validation would make the renderer refuse with VALIDATION_REQUIRED
// before reaching the assertion under test. An overlapping guard must not
// launder the arm being proved.
const EXTRA_CONTROLS = `
<w:p><w:sdt><w:sdtPr><w:id w:val="301"/><w:alias w:val="Allergies"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter allergies</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="302"/><w:alias w:val="Past medical history"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter history</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="303"/><w:alias w:val="Plan of care"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter plan</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="304"/><w:alias w:val="Impression"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter impression</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="305"/><w:alias w:val="Polyp count"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter count</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="306"/><w:alias w:val="Lesion diameter"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter diameter</w:t></w:r></w:sdtContent></w:sdt></w:p>
<w:p><w:sdt><w:sdtPr><w:id w:val="307"/><w:alias w:val="Review of systems"/><w:text/></w:sdtPr><w:sdtContent><w:r><w:t>Enter ROS</w:t></w:r></w:sdtContent></w:sdt></w:p>
`;
const DATA_BOUND_CONTROL =
  '<w:p><w:sdt><w:sdtPr><w:id w:val="108"/><w:alias w:val="Data-bound synthetic value"/><w:text/><w:dataBinding w:xpath="/root/value" w:storeItemID="{00000000-0000-0000-0000-000000000000}"/></w:sdtPr><w:sdtContent><w:r><w:t>Unapproved bound value</w:t></w:r></w:sdtContent></w:sdt></w:p>';

function sourceDocumentXml(): string {
  const withoutDataBinding = syntheticOpc.documentXml.replace(
    DATA_BOUND_CONTROL,
    '',
  );
  // ASSERT THE EDIT APPLIED. A `.replace()` that matches nothing is a silent
  // no-op that returns the original string, and the unsupported control would
  // then reach the validator and refuse the render for the wrong reason.
  if (withoutDataBinding === syntheticOpc.documentXml) {
    throw new Error('synthetic package changed: data-bound control not removed');
  }
  return withoutDataBinding.replace('<w:sectPr>', `${EXTRA_CONTROLS}<w:sectPr>`);
}

// ── THE FOUR DICTATIONS, PROJECTED FOR REAL ─────────────────────────────────
// The ruling's own four sentences. `entities` is the L3 shape; the projection
// decides concept, value, polarity and evidenceQuote. Nothing here asserts what
// it will decide — arm (pre-2) measures it.

interface NarrativeCase {
  readonly label: string;
  readonly controlId: string;
  readonly concept: string;
  /** The dictation as DENIED — the polarity comes from the sentence, not from
   *  a flag this fixture sets. */
  readonly deniedText: string;
  readonly deniedEntities: unknown;
  /** The same clinical slot dictated in the POSITIVE, for the isolating
   *  control: polarity must be the ONLY difference between the two runs. */
  readonly affirmedText: string;
  readonly affirmedEntities: unknown;
  /** The AFFIRMED ENTITY the projection puts in `fact.value` — the string the
   *  falsified #157 would have printed. Asserted ABSENT from the document. */
  readonly deniedEntity: string;
  /** What rule (1) must print: the quote, minus at most a leading heading. */
  readonly printed: string;
  readonly headingStripped: boolean;
}

const NARRATIVE: readonly NarrativeCase[] = [
  {
    label: 'Allergies',
    controlId: '301',
    concept: 'allergy.substance',
    deniedText: 'Allergies: no known drug allergies',
    deniedEntities: {
      allergies: [
        {
          substance: 'No known drug allergies',
          evidence_quote: 'Allergies: no known drug allergies',
        },
      ],
    },
    affirmedText: 'Allergies: penicillin',
    affirmedEntities: {
      allergies: [{ substance: 'Penicillin', evidence_quote: 'Allergies: penicillin' }],
    },
    deniedEntity: 'No known drug allergies',
    printed: 'no known drug allergies',
    headingStripped: true,
  },
  {
    label: 'Past medical history',
    controlId: '302',
    concept: 'past_medical_history',
    deniedText: 'The patient has no history of diabetes.',
    deniedEntities: {
      past_medical_history: [
        {
          condition: 'Diabetes',
          evidence_quote: 'The patient has no history of diabetes.',
        },
      ],
    },
    affirmedText: 'The patient has a history of diabetes.',
    affirmedEntities: {
      past_medical_history: [
        { condition: 'Diabetes', evidence_quote: 'The patient has a history of diabetes.' },
      ],
    },
    deniedEntity: 'Diabetes',
    printed: 'The patient has no history of diabetes.',
    headingStripped: false,
  },
  {
    label: 'Plan of care',
    controlId: '303',
    concept: 'plan',
    deniedText: 'Plan: no further imaging is required.',
    deniedEntities: {
      plan_discussed: [
        {
          item: 'Further imaging',
          evidence_quote: 'Plan: no further imaging is required.',
        },
      ],
    },
    affirmedText: 'Plan: further imaging is required.',
    affirmedEntities: {
      plan_discussed: [
        { item: 'Further imaging', evidence_quote: 'Plan: further imaging is required.' },
      ],
    },
    deniedEntity: 'Further imaging',
    printed: 'no further imaging is required.',
    headingStripped: true,
  },
  {
    label: 'Impression',
    controlId: '304',
    concept: 'assessment',
    deniedText: 'No evidence of pulmonary embolism.',
    deniedEntities: {
      assessment_discussed: [
        {
          finding: 'Pulmonary embolism',
          evidence_quote: 'No evidence of pulmonary embolism.',
        },
      ],
    },
    affirmedText: 'Findings consistent with pulmonary embolism.',
    affirmedEntities: {
      assessment_discussed: [
        {
          finding: 'Pulmonary embolism',
          evidence_quote: 'Findings consistent with pulmonary embolism.',
        },
      ],
    },
    deniedEntity: 'Pulmonary embolism',
    printed: 'No evidence of pulmonary embolism.',
    headingStripped: false,
  },
  {
    // ⚠️ #157(c). ROS IS THE ONLY ENTITY TYPE L3 STATES A POLARITY ON
    // (encounter-facts/index.ts:705), which is what makes it the route to the
    // R1 harm. This ROW does NOT state one — it is the ordinary, self-negating
    // ROS dictation, so rule (1) still prints it and every PLAN-iterating arm
    // gets a real denial here. The arms that need the STATED-polarity shape
    // supply it themselves and `omit` this default, by name.
    label: 'Review of systems',
    controlId: '307',
    concept: 'ros.constitutional',
    deniedText: 'No fever or chills.',
    deniedEntities: {
      ros: [
        {
          system: 'constitutional',
          finding: 'Fever',
          evidence_quote: 'No fever or chills.',
        },
      ],
    },
    affirmedText: 'Reports fever and chills.',
    affirmedEntities: {
      ros: [
        {
          system: 'constitutional',
          finding: 'Fever',
          evidence_quote: 'Reports fever and chills.',
        },
      ],
    },
    deniedEntity: 'Fever',
    printed: 'No fever or chills.',
    headingStripped: false,
  },
];

function projected(text: string, entities: unknown): EncounterFact[] {
  return projectEncounterFacts({
    mode: 'dictation',
    contextText: text,
    entities: entities as never,
  });
}

// ── THE NON-NARRATIVE KINDS ─────────────────────────────────────────────────
// Hand-built, because the projection's entity shapes for a dropdown ordinal or
// a repeating row do not exist. They mirror the projection's SHAPE where it
// matters: the value is the clinical ENTITY and the quote is the doctor's
// sentence, and arm (pre-2) asserts the value is not a substring of its quote —
// so "the option was not printed" is a real assertion and not a coincidence.

interface ScalarCase {
  readonly label: string;
  readonly controlId: string;
  readonly concept: string;
  readonly value: string;
  readonly quote: string;
  readonly seed: number;
}

const SCALAR: readonly ScalarCase[] = [
  {
    label: 'Exam side',
    controlId: '100',
    concept: 'exam.side',
    value: 'R',
    quote: 'The affected side was not identified on this study.',
    seed: 1,
  },
  {
    label: 'Encounter category',
    controlId: '101',
    concept: 'encounter.category',
    value: 'initial',
    quote: 'The visit type was not documented.',
    seed: 2,
  },
  {
    label: 'Encounter date',
    controlId: '103',
    concept: 'procedure.date',
    value: '2026-02-03',
    quote: 'No procedure was performed at that visit.',
    seed: 3,
  },
  {
    label: 'Medication reviewed',
    controlId: '104',
    concept: 'medication.review',
    value: 'warfarin',
    quote: 'The patient is not taking anticoagulation.',
    seed: 4,
  },
  {
    label: 'Polyp count',
    controlId: '305',
    concept: 'finding.polyp_count',
    value: '3',
    quote: 'No polyps were identified.',
    seed: 5,
  },
  {
    label: 'Lesion diameter',
    controlId: '306',
    concept: 'measurement.lesion',
    value: '4 mm',
    quote: 'No lesion was measured.',
    seed: 6,
  },
];

/** The repeating section — two rows, one concept. */
const ROW_CONCEPT = 'exam.abdomen';
const ROW_FACTS: readonly { value: string; quote: string; seed: number }[] = [
  { value: 'Hepatomegaly', quote: 'There is no hepatomegaly.', seed: 7 },
  { value: 'Splenomegaly', quote: 'There is no splenomegaly.', seed: 8 },
];

function factId(seed: number): string {
  return `ttfact_${seed.toString(16).padStart(24, '0')}`;
}

function handBuilt(
  seed: number,
  concept: string,
  value: string,
  quote: string,
  polarity: EncounterFact['polarity'],
): EncounterFact {
  return EncounterFactSchema.parse({
    factId: factId(seed),
    sourceType: 'encounter_evidence',
    concept,
    value,
    polarity,
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`gate157b-anchor-${seed}`],
    evidenceQuote: quote,
    segment: null,
    quality: { asr: 'high', evidence: 'direct' },
  });
}

// ── the plan ────────────────────────────────────────────────────────────────

type Behavior = SemanticMapping['polarityBehavior'];

const PLAN: Record<string, { concept: string; polarityBehavior: Behavior }> = {
  Allergies: { concept: 'allergy.substance', polarityBehavior: 'explicit_denial_allowed' },
  'Past medical history': { concept: 'past_medical_history', polarityBehavior: 'explicit_denial_allowed' },
  'Plan of care': { concept: 'plan', polarityBehavior: 'explicit_denial_allowed' },
  Impression: { concept: 'assessment', polarityBehavior: 'explicit_denial_allowed' },
  'Exam side': { concept: 'exam.side', polarityBehavior: 'explicit_denial_allowed' },
  'Encounter category': { concept: 'encounter.category', polarityBehavior: 'explicit_denial_allowed' },
  'Encounter date': { concept: 'procedure.date', polarityBehavior: 'explicit_denial_allowed' },
  'Medication reviewed': { concept: 'medication.review', polarityBehavior: 'explicit_denial_allowed' },
  'Polyp count': { concept: 'finding.polyp_count', polarityBehavior: 'explicit_denial_allowed' },
  'Lesion diameter': { concept: 'measurement.lesion', polarityBehavior: 'explicit_denial_allowed' },
  'Repeat finding': { concept: ROW_CONCEPT, polarityBehavior: 'explicit_denial_allowed' },
  // ⚠️ #157(c). `ros.*` is the ONLY entity type L3 states a polarity on
  // (encounter-facts/index.ts:705), so it is the only route to a fact that is
  // `denied` on a quote carrying no negation — the R1 harm. It carries an
  // ORDINARY self-negating default (see NARRATIVE) so the PLAN-iterating arms
  // exercise it like any other narrative; the R1 arms `omit` that default and
  // supply the stated-polarity fact themselves.
  'Review of systems': { concept: 'ros.constitutional', polarityBehavior: 'explicit_denial_allowed' },
};

// ── #157(c) FIXTURES ────────────────────────────────────────────────────────

/** THE R1 HARM: polarity STATED as denied on a sentence that reads as an
 *  assertion. Driven through the real projection, not hand-built, so the
 *  bypass at `options.polarity ?? inferPolarity(...)` is the thing exercised. */
function statedPolarityRos(): EncounterFact[] {
  return projected('Fever, chills, and night sweats.', {
    ros: [
      {
        system: 'constitutional',
        finding: 'Fever',
        polarity: 'denied',
        evidence_quote: 'Fever, chills, and night sweats.',
      },
    ],
  });
}

/** The narrative field and mapping arm (8f) asks the mixed contract about
 *  directly. Everything else drives the compiled IR; this one row needs a fact
 *  QUALITY the projection will not produce for an assessment entity. */
const FIELD_STUB = {
  fieldId: `ttf_${'a'.repeat(24)}`,
  kind: 'narrative_text',
  rowPrototype: false,
} as unknown as TemplateField;
const MAPPING_STUB = {
  clinicalConcept: 'assessment',
  polarityBehavior: 'explicit_denial_allowed',
} as unknown as SemanticMapping;

/** Q3's mixed-polarity dictation: one affirmed finding, one denied, one field. */
const MIXED_TEXT =
  'Findings consistent with pneumonia. No evidence of pulmonary embolism.';
const MIXED_ENTITIES = {
  assessment_discussed: [
    { finding: 'Pneumonia', evidence_quote: 'Findings consistent with pneumonia.' },
    {
      finding: 'Pulmonary embolism',
      evidence_quote: 'No evidence of pulmonary embolism.',
    },
  ],
};

const ALL_CONCEPTS: readonly string[] = Object.values(PLAN).map((p) => p.concept);

interface DriveOptions {
  /** Concepts dictated in the NEGATIVE. Everything else is affirmed. */
  readonly denied?: readonly string[];
  /** Override every planned mapping's polarity behaviour — rule (4)/(3). */
  readonly behavior?: Behavior;
  /** Extra facts appended verbatim (the multi-fact narrative arms). */
  readonly extraFacts?: readonly EncounterFact[];
  /** Suppress the default facts for these concepts. */
  readonly omit?: readonly string[];
}

function mappingFor(field: TemplateField, behavior?: Behavior): SemanticMapping {
  const planned = PLAN[field.originalLabel];
  const expectedDataType = expectedDataTypeForFieldKind(field.kind);
  if (!expectedDataType) throw new Error(`no expectedDataType for kind ${field.kind}`);
  return {
    fieldId: field.fieldId,
    sourceType: 'extraction',
    clinicalConcept: planned?.concept ?? `gate157b.unused.${field.fieldId}`,
    expectedDataType,
    // ⚠️ `any`, DELIBERATELY. "The patient has no history of diabetes." infers
    // temporality `historical` (the projection reads "history of"), so a
    // `current` mapping would drop the fact at the temporality filter and the
    // arm would test `missingResolution` while looking like it tested a denial.
    polarityBehavior: behavior ?? planned?.polarityBehavior ?? 'value_only',
    temporality: 'any',
    laterality: 'optional',
    unitPolicy: field.kind === 'measurement' ? 'optional' : 'not_applicable',
    approvedSynonyms: [],
    required: false,
    blankPolicy: 'blank',
    unknownPolicy: 'blank',
    practiceDefault: null,
    status: 'certified',
  };
}

interface Driven {
  readonly ir: TemplateDocIR;
  readonly source: Buffer;
  readonly facts: EncounterFact[];
  readonly mappings: SemanticMapping[];
  readonly resolutions: FieldResolution[];
  readonly validation: TemplateTwinValidationResult;
  byLabel(label: string): { field: TemplateField; resolution: FieldResolution };
  factsFor(concept: string): EncounterFact[];
  render(): Promise<string>;
}

let compiled: { source: Buffer; ir: TemplateDocIR } | null = null;

async function compiledSource(): Promise<{ source: Buffer; ir: TemplateDocIR }> {
  if (!compiled) {
    const source = await buildSyntheticDocx({ documentXml: sourceDocumentXml() });
    compiled = { source, ir: compileTemplateDocx(source) };
  }
  return compiled;
}

/** REAL projection -> REAL compiler -> REAL resolver -> REAL validator. */
async function drive(options: DriveOptions = {}): Promise<Driven> {
  const denied = new Set(options.denied ?? []);
  const omit = new Set(options.omit ?? []);
  // A misspelled concept here would silently make an arm test the AFFIRMED path
  // and pass for the wrong reason. Refuse it at the fixture.
  for (const concept of [...denied, ...omit]) {
    if (!ALL_CONCEPTS.includes(concept)) {
      throw new Error(`gate 157b: ${concept} is not a fixture concept`);
    }
  }

  const facts: EncounterFact[] = [];
  for (const narrative of NARRATIVE) {
    if (omit.has(narrative.concept)) continue;
    facts.push(
      ...(denied.has(narrative.concept)
        ? projected(narrative.deniedText, narrative.deniedEntities)
        : projected(narrative.affirmedText, narrative.affirmedEntities)),
    );
  }
  for (const scalar of SCALAR) {
    if (omit.has(scalar.concept)) continue;
    facts.push(
      handBuilt(
        scalar.seed,
        scalar.concept,
        scalar.value,
        scalar.quote,
        denied.has(scalar.concept) ? 'denied' : 'affirmed',
      ),
    );
  }
  if (!omit.has(ROW_CONCEPT)) {
    for (const row of ROW_FACTS) {
      facts.push(
        handBuilt(
          row.seed,
          ROW_CONCEPT,
          row.value,
          row.quote,
          denied.has(ROW_CONCEPT) ? 'denied' : 'affirmed',
        ),
      );
    }
  }
  facts.push(...(options.extraFacts ?? []));

  const { source, ir } = await compiledSource();
  const mappings = ir.fields.map((field) => mappingFor(field, options.behavior));
  const certifiedFieldIds = ir.fields.map((field) => field.fieldId);
  const resolutions = resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    certifiedFieldIds,
  });
  const validation = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts,
    resolutions,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds,
    now: '2026-01-01T00:00:00.000Z',
  });

  return {
    ir,
    source,
    facts,
    mappings,
    resolutions,
    validation,
    byLabel(label) {
      const field = ir.fields.find((item) => item.originalLabel === label);
      if (!field) throw new Error(`no compiled field labelled ${label}`);
      const resolution = resolutions.find((item) => item.fieldId === field.fieldId);
      if (!resolution) throw new Error(`no resolution for ${label}`);
      return { field, resolution };
    },
    factsFor(concept) {
      return facts.filter((fact) => fact.concept === concept);
    },
    async render() {
      // EVERY ARM RE-ASSERTS THE VALIDATION IS CLEAN BEFORE RENDERING. Without
      // it a blocked validation refuses with VALIDATION_REQUIRED and the arm
      // reads as "the renderer rejected the denial".
      expect(validation.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
      expect(validation.valid).toBe(true);
      const rendered = await renderTemplateDocx({
        source,
        ir,
        resolutions,
        validation,
      });
      expect(rendered.verification.verified).toBe(true);
      return documentXmlOf(rendered.document);
    },
  };
}

/** A blank control's rendered text. Measured, not assumed — see (pre-4). */
const BLANK = '';

function documentXmlOf(rendered: Buffer): string {
  return inspectDocxPackage(rendered)
    .zip.entries.get('word/document.xml')!
    .bytes.toString('utf8');
}

/** The `w:sdt` element carrying this `w:id`, so a text assertion is about THAT
 *  FIELD rather than about the package. A document-wide `toContain` can be
 *  satisfied by a coincidental match in a neighbouring control. */
function controlById(xml: string, id: string): string {
  const identity = xml.indexOf(`<w:id w:val="${id}"`);
  if (identity < 0) throw new Error(`no control with w:id ${id} in the output`);
  const start = xml.lastIndexOf('<w:sdt>', identity);
  if (start < 0) throw new Error(`control ${id} is malformed`);
  // ⚠️ BALANCED, NOT FIRST-CLOSE. A repeating section CONTAINS the controls it
  // repeats, so `indexOf('</w:sdt>')` returns the INNER control's close and
  // silently truncates the slice after row one — which reads as "the second row
  // did not render".
  let depth = 0;
  let cursor = start;
  while (cursor < xml.length) {
    const open = xml.indexOf('<w:sdt>', cursor);
    const close = xml.indexOf('</w:sdt>', cursor);
    if (close < 0) break;
    if (open >= 0 && open < close) {
      depth += 1;
      cursor = open + '<w:sdt>'.length;
      continue;
    }
    depth -= 1;
    cursor = close + '</w:sdt>'.length;
    if (depth === 0) return xml.slice(start, cursor);
  }
  throw new Error(`control ${id} is unbalanced`);
}

/** The visible text of a control, concatenated across its `w:t` nodes.
 *  This — not a `toContain` — is what the zero-composition suffix assertion
 *  runs against, because `toContain` cannot detect EXTRA text around a match. */
function renderedTextOf(controlXml: string): string {
  const parts: string[] = [];
  const re = /<w:t(?:\s[^>]*)?>([\s\S]*?)<\/w:t>/g;
  let match = re.exec(controlXml);
  while (match !== null) {
    parts.push(match[1]!);
    match = re.exec(controlXml);
  }
  return parts
    .join('')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');
}

/** Swap ONE resolution and keep everything else exactly as the real pipeline
 *  produced it — including the real validation result, which stays `valid`. A
 *  refusal below therefore cannot come from VALIDATION_REQUIRED. */
function withResolution(
  driven: Driven,
  fieldId: string,
  patch: Partial<FieldResolution>,
): FieldResolution[] {
  return driven.resolutions.map((item) =>
    item.fieldId === fieldId
      ? (FieldResolutionSchema.parse({ ...item, ...patch }) as FieldResolution)
      : item,
  );
}

// ============================================================================

describe('#157(b) — the denial contract, end to end', () => {
  // ── PRE: the fixture is what it claims, and it is not blind ───────────────

  it('(pre-1) the compiled document carries every kind this gate assumes', async () => {
    const { ir } = await compiledSource();
    const kindOf = (label: string) =>
      ir.fields.find((f) => f.originalLabel === label)?.kind;
    expect(kindOf('Allergies')).toBe('narrative_text');
    expect(kindOf('Past medical history')).toBe('narrative_text');
    expect(kindOf('Plan of care')).toBe('narrative_text');
    expect(kindOf('Impression')).toBe('narrative_text');
    expect(kindOf('Exam side')).toBe('single_select');
    expect(kindOf('Encounter category')).toBe('single_select');
    expect(kindOf('Encounter date')).toBe('date');
    expect(kindOf('Medication reviewed')).toBe('checkbox');
    expect(kindOf('Polyp count')).toBe('number');
    expect(kindOf('Lesion diameter')).toBe('measurement');
    const repeat = ir.fields.find((f) => f.originalLabel === 'Repeat finding');
    expect(repeat?.rowPrototype).toBe(true);
    // The owner's ord-21 SHAPE, asserted rather than described.
    const allergies = ir.fields.find((f) => f.originalLabel === 'Allergies')!;
    expect(allergies.criticality).toBe('allergy');
    expect(allergies.clinicallyMaterial).toBe(true);
  });

  it('(pre-2) ⚠️ THE ANTI-BLINDNESS ARM — the real projection makes value ≠ quote', async () => {
    // THIS IS THE ARM THE PREDECESSOR GATE DID NOT HAVE. It built every fact
    // with `evidenceQuote = value + " (synthetic dictation)"`, so "prints the
    // value" and "prints the quote" were the same observation and the gate
    // could not see the defect that falsified #157.
    for (const narrative of NARRATIVE) {
      const facts = projected(narrative.deniedText, narrative.deniedEntities);
      expect([narrative.label, facts.length]).toEqual([narrative.label, 1]);
      const fact = facts[0]!;
      expect([narrative.label, fact.concept]).toEqual([narrative.label, narrative.concept]);
      expect([narrative.label, fact.polarity]).toEqual([narrative.label, 'denied']);
      expect([narrative.label, fact.value]).toEqual([narrative.label, narrative.deniedEntity]);
      expect([narrative.label, fact.sourceType]).toEqual([
        narrative.label,
        'encounter_evidence',
      ]);
      // The quote is the doctor's sentence, and rule (1)'s output is a SUFFIX
      // of it — the heading strip removes a prefix and nothing else.
      expect([narrative.label, fact.evidenceQuote]).toEqual([
        narrative.label,
        narrative.headingStripped ? narrative.deniedText : narrative.printed,
      ]);
      expect(stripLeadingDictationHeading(fact.evidenceQuote)).toBe(narrative.printed);
      expect(fact.evidenceQuote.endsWith(narrative.printed)).toBe(true);
      expect(narrative.headingStripped).toBe(fact.evidenceQuote !== narrative.printed);
    }

    // ⚠️ THE PROPERTY THAT MAKES THIS GATE NON-VACUOUS, STATED AS THE EXACT
    // THING THE OLD FIXTURE DESTROYED: for every row, PRINTING THE VALUE AND
    // PRINTING THE QUOTE ARE DIFFERENT OBSERVATIONS. Under the predecessor's
    // `quote = value + " (synthetic dictation)"` they were the same one.
    for (const narrative of NARRATIVE) {
      const fact = projected(narrative.deniedText, narrative.deniedEntities)[0]!;
      const value = String(fact.value);
      expect([narrative.label, value === fact.evidenceQuote]).toEqual([
        narrative.label,
        false,
      ]);
      expect([
        narrative.label,
        value === stripLeadingDictationHeading(fact.evidenceQuote),
      ]).toEqual([narrative.label, false]);
      // And the entity is not even a literal substring of the sentence, so an
      // absence assertion against it cannot be satisfied by an accident of the
      // quote. (Case matters here and that is the point: the projection
      // Title-Cases the entity — "Diabetes" — while the dictation says
      // "diabetes". The lower-cased word IS in the sentence; the VALUE is not.)
      expect([narrative.label, fact.evidenceQuote.includes(value)]).toEqual([
        narrative.label,
        false,
      ]);
    }
  });

  it('(pre-3) the hand-built scalar facts cannot make an ABSENCE assertion vacuous', () => {
    for (const scalar of SCALAR) {
      expect([scalar.label, scalar.quote.includes(scalar.value)]).toEqual([
        scalar.label,
        false,
      ]);
    }
    for (const row of ROW_FACTS) {
      expect([row.value, row.quote.includes(row.value)]).toEqual([row.value, false]);
    }
  });

  it('(pre-4) the affirmed baseline is clean and renders — nothing below fails for a fixture reason', async () => {
    const affirmed = await drive();
    expect(affirmed.validation.valid).toBe(true);
    expect(
      affirmed.validation.issues.filter((i) => i.severity === 'blocking'),
    ).toEqual([]);
    const xml = await affirmed.render();
    // NON-VACUITY: an AFFIRMED narrative prints its VALUE, not its quote. That
    // is what makes "a denial prints the quote" a statement about denials.
    const pmh = controlById(xml, '302');
    expect(pmh).toContain('<w:t>Diabetes</w:t>');
    expect(renderedTextOf(pmh)).toBe('Diabetes');

    // ⚠️ AND WHAT "BLANK" MEANS IN A RENDERED PACKAGE, ANCHORED TO ESTABLISHED
    // BEHAVIOUR RATHER THAN TO THIS GATE'S EXPECTATION. `contentControlPatches`
    // clears a null value's text container, so an honestly-unfilled field
    // renders EMPTY — the template's placeholder does not survive into a signed
    // document. `Assessment narrative` (w:id 102) carries a concept no fact
    // names, so it is `not_mentioned`, and every withheld-denial arm below
    // asserts EXACTLY this same rendering. That is what makes "a withheld
    // denial is a blank" a claim about the document rather than about a status.
    const { resolution: unmapped } = affirmed.byLabel('Assessment narrative');
    expect(unmapped.status).toBe('not_mentioned');
    expect(unmapped.value).toBeNull();
    expect(renderedTextOf(controlById(xml, '102'))).toBe(BLANK);
  });

  // ── RULE 1 — a narrative denial prints the EVIDENCE QUOTE, verbatim ───────

  for (const narrative of NARRATIVE) {
    it(`(1) ${narrative.label} — the denial prints the doctor's own sentence${narrative.headingStripped ? ', heading stripped' : ' (already bare)'}`, async () => {
      const driven = await drive({ denied: [narrative.concept] });
      const { field, resolution } = driven.byLabel(narrative.label);
      expect(field.kind).toBe('narrative_text');

      expect(resolution.status).toBe('explicitly_denied');
      expect(resolution.value).toBe(narrative.printed);
      expect(resolution.reasonCode).toBe('explicit_denial_dictated_quote');
      expect(resolution.sourceFactIds).toHaveLength(1);

      const control = controlById(await driven.render(), narrative.controlId);
      const printed = renderedTextOf(control);

      // (i) VERBATIM, in this field's own control.
      expect(printed).toBe(narrative.printed);

      // (ii) ⚠️ ZERO COMPOSITION, ASSERTED AS A PROPERTY. The rendered text is
      // CONTAINED IN — and is a SUFFIX of — the doctor's own quote. A join, a
      // template, a prefix or a synthesized "No <entity>" all fail this.
      const quote = driven.factsFor(narrative.concept)[0]!.evidenceQuote;
      expect(quote.includes(printed)).toBe(true);
      expect(quote.endsWith(printed)).toBe(true);


      // (iii) ⚠️ #157(c) Q1 — AND IT CARRIES A NEGATION SCOPING THE FINDING.
      // BOTH PROPERTIES, OR THE GUARD REPORTS GREEN ON THE INVERSION OF THE
      // THING IT GUARDS. (ii) proves nothing was MANUFACTURED; it CANNOT prove
      // nothing was DESTROYED — every one of the twelve heading-strip
      // inversions satisfies (ii) exactly, because an inverted output is still
      // a strict suffix of the doctor's own quote. A row that satisfies only
      // (ii) must RED here, and arm (1h) pins one such string.
      const fact = driven.factsFor(narrative.concept)[0]!;
      const cue = selfNegationScopingFinding(printed, fact.value);
      expect([narrative.label, cue === null]).toEqual([narrative.label, false]);
      expect([narrative.label, printed.includes(cue!.match)]).toEqual([
        narrative.label,
        true,
      ]);

      // (iv) THE FALSIFIED #157's OUTPUT IS ABSENT. This is the assertion that
      // would have caught it: the AFFIRMED ENTITY must not reach the document.
      expect(control).not.toContain(`<w:t>${narrative.deniedEntity}</w:t>`);
    });
  }

  it('(1e) the heading strip is a PREFIX removal and cannot eat a sentence', () => {
    // The one formatting allowance, and its counterexample. `encounter-facts`'s
    // VALUE_LABEL_PREFIX would turn the first line into "30 the patient denied
    // chest pain." — it allows any non-colon character in the heading.
    expect(stripLeadingDictationHeading('At 10:30 the patient denied chest pain.')).toBe(
      'At 10:30 the patient denied chest pain.',
    );
    expect(stripLeadingDictationHeading('Plan: no further imaging is required.')).toBe(
      'no further imaging is required.',
    );
    expect(stripLeadingDictationHeading('Assessment/Plan: no change.')).toBe('no change.');
    // Never empties the quote, and never strips twice.
    expect(stripLeadingDictationHeading('A: ')).toBe('A: ');
    expect(stripLeadingDictationHeading('One: Two: three')).toBe('Two: three');
    for (const q of [
      'At 10:30 the patient denied chest pain.',
      'Plan: no further imaging is required.',
      'Assessment/Plan: no change.',
      'No evidence of pulmonary embolism.',
      ':leading colon',
    ]) {
      expect(q.endsWith(stripLeadingDictationHeading(q))).toBe(true);
    }
  });

  // ⚠️ REBUILT FOR #157(c) Q1. THE PREDECESSOR OF THIS ARM WAS A CONTROL AIMED
  // WHERE THE ANSWER WAS PREDETERMINED, AND THAT IS THE REASON IT IS REBUILT.
  //
  // All five of its KEEP fixtures were `DENIAL_VOCABULARY` tokens and the guard
  // was built from exactly that list, so the arm measured its own target.
  // Mutating the guard out left every OTHER denial shape byte-identical and the
  // arm still went green. Measured afterwards: of fourteen negating headings the
  // old guard kept TWO and STRIPPED TWELVE, each of which then printed its own
  // inverse into a signed note.
  //
  // ⚠️ SO THE KEEP SET IS NOW OUT OF VOCABULARY BY CONSTRUCTION, AND THE ARM
  // ASSERTS THAT IT IS. Each out-of-vocabulary row also asserts
  // `EXPLICIT_DENIAL.test(heading) === false`, so the fixtures cannot silently
  // drift back onto the guard's own list and re-predetermine the answer.
  it('(1f) ⚠️ A HEADING THAT CARRIES THE NEGATION IS NEVER STRIPPED — OUT-OF-VOCABULARY FIXTURES', () => {
    // ── KEEP · OUT OF VOCABULARY. `EXPLICIT_DENIAL` cannot see any of these.
    const OUT_OF_VOCABULARY = [
      'Absent: fever, chills, or night sweats.',
      'Ruled out: pulmonary embolism.',
      'Free of: chest pain.',
      'Not currently taking: warfarin, aspirin, or clopidogrel.',
      'None: drug allergies.',
      'Nil: acute distress.',
      'Unremarkable: cardiovascular exam.',
      'Within normal limits: respiratory exam.',
      'Negative: melena.',
      'Excluded: pulmonary embolism.',
      'Not present: hepatomegaly.',
      'Clear of: consolidation.',
      'Resolved: pneumonia.',
      'WNL: neurological exam.',
    ];
    for (const quote of OUT_OF_VOCABULARY) {
      const heading = `${quote.slice(0, quote.indexOf(':') + 1)}`;
      // ⚠️ THE ARM IS NOT MEASURING ITS OWN TARGET — asserted, per row.
      expect([heading, EXPLICIT_DENIAL.test(heading)]).toEqual([heading, false]);
      expect([quote, stripLeadingDictationHeading(quote)]).toEqual([quote, quote]);
    }

    // ── KEEP · IN VOCABULARY. These are the five the predecessor carried, plus
    // the two the census found. They must ALSO still be kept — a rebuilt guard
    // that traded the old cases for new ones has fixed nothing.
    for (const quote of [
      'Negative for: diabetes, hypertension, and coronary artery disease.',
      'Patient denies: chest pain and dyspnea.',
      'Not taking: warfarin, aspirin, or clopidogrel.',
      'No history of: diabetes, hypertension.',
      'Without: fever, chills, or night sweats.',
      'Denied: chest pain.',
      'No longer taking: warfarin.',
    ]) {
      expect([quote, stripLeadingDictationHeading(quote)]).toEqual([quote, quote]);
    }

    // ── REFUSE · ORDINARY HEADINGS MUST STILL BE STRIPPED. Without this set the
    // arm passes for a guard that has simply disabled the allowance, which
    // would delete rule (1)'s one formatting concession rather than fix it.
    const STRIPPED: ReadonlyArray<readonly [string, string]> = [
      ['Allergies: no known drug allergies', 'no known drug allergies'],
      ['Indication: screening colonoscopy.', 'screening colonoscopy.'],
      ['Plan: no further imaging is required.', 'no further imaging is required.'],
      ['Assessment/Plan: no change.', 'no change.'],
      ['Impression: pneumonia.', 'pneumonia.'],
      ['Past medical history: diabetes.', 'diabetes.'],
      ['Chief complaint: chest pain.', 'chest pain.'],
      ['Medications: warfarin.', 'warfarin.'],
      ['Review of systems: fatigue.', 'fatigue.'],
      ['Physical exam: normal.', 'normal.'],
      ['Nose: patent.', 'patent.'],
      ['Neuro: intact.', 'intact.'],
    ];
    for (const [quote, expected] of STRIPPED) {
      expect([quote, stripLeadingDictationHeading(quote)]).toEqual([quote, expected]);
    }
  });

  it('(1g) ⚠️ A STATED-POLARITY DENIAL ON AN AFFIRMATIVE QUOTE RENDERS BLANK — THE #157(b) FALSIFICATION', async () => {
    // ⚠️ THIS IS THE HARM THAT FALSIFIED RULE (1) AS WRITTEN, AND NO HEADING IS
    // INVOLVED. L3 states polarity as a REQUIRED enum
    // (03-extract-entities.ts:193), is INSTRUCTED that "absence of the word
    // 'no' is not absence of a denial" (:446), and a stated polarity BYPASSES
    // the vocabulary entirely (encounter-facts/index.ts:507). So a fact is
    // `denied` on a sentence that reads as an ASSERTION, and "print the quote
    // verbatim" printed its opposite under `valid: true`.
    const facts = statedPolarityRos();
    expect(facts).toHaveLength(1);
    expect(facts[0]!.polarity).toBe('denied');
    expect(facts[0]!.concept).toBe('ros.constitutional');
    // ⚠️ NON-VACUITY: the quote carries no negation the SHIPPED vocabulary can
    // see either, so this fixture is not one that was denied by its own words.
    expect(EXPLICIT_DENIAL.test(facts[0]!.evidenceQuote)).toBe(false);

    const driven = await drive({ omit: ['ros.constitutional'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Review of systems');
    expect(field.kind).toBe('narrative_text');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.reasonCode).toBe('denial_quote_not_self_negating');
    // The citation SURVIVES — the manifest can still say what was denied.
    expect(resolution.sourceFactIds).toHaveLength(1);

    // ⚠️ AND RULE (3) IS UNTOUCHED: the document still renders and nothing
    // blocks. Q1 converts a false assertion into a VISIBLE ABSENCE, never into
    // a refused export.
    const xml = await driven.render();
    expect(renderedTextOf(controlById(xml, '307'))).toBe(BLANK);
    expect(xml).not.toContain('Fever, chills, and night sweats.');
    expect(xml).not.toContain('<w:t>Fever</w:t>');
  });

  it('(1h) ⚠️ AN OUT-OF-VOCABULARY NEGATING HEADING REACHES THE DOCUMENT INTACT — END TO END', async () => {
    // The strip guard's own end-to-end row, and it is NOT the same claim as
    // (1g). (1g) proves a print is REFUSED when the text carries no negation;
    // this proves a print is PRESERVED when the negation lives in the prefix
    // that the allowance would otherwise remove. Mutating either one out reds
    // exactly one of these two arms — which is what makes them independent
    // rather than one property asserted twice.
    const quote = 'Absent: fever, chills, or night sweats.';
    const facts = projected(quote, {
      ros: [
        {
          system: 'constitutional',
          finding: 'Fever',
          polarity: 'denied',
          evidence_quote: quote,
        },
      ],
    });
    expect(facts[0]!.polarity).toBe('denied');
    expect(EXPLICIT_DENIAL.test('Absent:')).toBe(false); // out of vocabulary

    const driven = await drive({ omit: ['ros.constitutional'], extraFacts: facts });
    const { resolution } = driven.byLabel('Review of systems');
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe(quote); // the heading is PART OF THE CLAIM
    expect(resolution.reasonCode).toBe('explicit_denial_dictated_quote');

    const printed = renderedTextOf(controlById(await driven.render(), '307'));
    expect(printed).toBe(quote);
    // BOTH PROPERTIES, again: a suffix of the quote, AND carrying its negation.
    expect(quote.endsWith(printed)).toBe(true);
    const cue = selfNegationScopingFinding(printed, facts[0]!.value);
    expect(cue).not.toBeNull();
    expect(printed.includes(cue!.match)).toBe(true);
    // ⚠️ THE INVERSION THAT SHIPPED: without the guard the strip leaves
    // "fever, chills, or night sweats." — a suffix of the doctor's own quote,
    // so the zero-composition property is TRUE for it, and it says the
    // OPPOSITE. Property (ii) is the only thing that can see this.
    expect(quote.endsWith('fever, chills, or night sweats.')).toBe(true);
    expect(
      selfNegationScopingFinding('fever, chills, or night sweats.', 'Fever'),
    ).toBeNull();
  });

  it('(1j) ⚠️ A NEGATION IN ANOTHER CLAUSE DOES NOT SCOPE THE FINDING — END TO END', async () => {
    // ⚠️ CONTAINMENT ALONE IS NOT THE PREDICATE, AND THIS IS THE ROW THAT
    // PROVES IT. The quote carries a real negation — "No acute distress." — and
    // it negates something else entirely. A containment test prints the whole
    // sentence under a DENIED fact, which asserts the fever the record denies.
    // Only the clause test can tell the two apart, and mutating the clause
    // bounds out reds exactly here and at (1i).
    const quote = 'No acute distress. Fever, chills, and night sweats.';
    const facts = projected(quote, {
      ros: [
        {
          system: 'constitutional',
          finding: 'Fever',
          polarity: 'denied',
          evidence_quote: quote,
        },
      ],
    });
    expect(facts).toHaveLength(1);
    expect(facts[0]!.polarity).toBe('denied');
    // NON-VACUITY: the quote really does carry a negation. Without this the arm
    // could pass because the fixture had no cue at all — which is (1g)'s case,
    // not this one.
    expect(selfNegationCues(quote).length).toBeGreaterThan(0);

    const driven = await drive({ omit: ['ros.constitutional'], extraFacts: facts });
    const { resolution } = driven.byLabel('Review of systems');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.reasonCode).toBe('denial_quote_not_self_negating');

    const xml = await driven.render();
    expect(renderedTextOf(controlById(xml, '307'))).toBe(BLANK);
    expect(xml).not.toContain('Fever, chills, and night sweats.');
    expect(xml).not.toContain('No acute distress.');
  });

  it('(1i) THE DISCRIMINATOR ITSELF — KEEP, REFUSE, and the limits it fails toward BLANK on', () => {
    // ⚠️ THE UNIT-LEVEL TABLE, so a regression names the shape rather than one
    // rendered document. Every KEEP row is a sentence a doctor would recognise
    // as a denial; every REFUSE row must BLANK.
    const KEEP: ReadonlyArray<readonly [string, string]> = [
      ['Absent fever, chills, or night sweats.', 'Fever'],
      ['Ruled out pulmonary embolism.', 'Pulmonary embolism'],
      ['Free of chest pain.', 'Chest pain'],
      ['None of the above symptoms.', 'Symptoms'],
      ['Nil acute distress.', 'Acute distress'],
      ['Cardiovascular exam unremarkable.', 'Cardiovascular abnormality'],
      ['Respiratory exam within normal limits.', 'Respiratory abnormality'],
      ['Melena negative.', 'Melena'],
      ['Chest pain was denied by the patient.', 'Chest pain'],
      ['The study rules out pulmonary embolism.', 'Pulmonary embolism'],
      ['No longer taking warfarin.', 'Warfarin'],
      ['The pneumonia has resolved.', 'Pneumonia'],
      ['Hepatomegaly is not present.', 'Hepatomegaly'],
      ['Absence of pulmonary embolism.', 'Pulmonary embolism'],
      ['Pulmonary embolism excluded.', 'Pulmonary embolism'],
      ['Lungs clear of consolidation.', 'Consolidation'],
      ['Troponin -ve.', 'Troponin elevation'],
      ['Never a smoker.', 'Smoking'],
      ['Patient denies chest pain.', 'Chest pain'],
      ['Without fever or chills.', 'Fever'],
      ['Negative for melena.', 'Melena'],
      ['Not currently taking anticoagulation.', 'Anticoagulation'],
      ['The patient has no history of diabetes.', 'Diabetes'],
      ['no known drug allergies', 'No known drug allergies'],
    ];
    for (const [text, finding] of KEEP) {
      const cue = selfNegationScopingFinding(text, finding);
      expect([text, cue === null]).toEqual([text, false]);
      // The reported token is REALLY IN the text — that is what lets the
      // rendering arms assert property (ii) rather than take a boolean on trust.
      expect([text, text.includes(cue!.match)]).toEqual([text, true]);
    }

    const REFUSE: ReadonlyArray<readonly [string, string, string]> = [
      // THE R1 HARM — a denied fact whose quote carries no negation at all.
      ['Fever, chills, and night sweats.', 'Fever', 'no negation token'],
      ['Findings consistent with pneumonia.', 'Pneumonia', 'no negation token'],
      ['The patient has a history of diabetes.', 'Diabetes', 'no negation token'],
      // BARE `not` IS NOT A NEGATION TOKEN — the counterexample, pinned.
      ['It is not severe, but it is there.', 'Chest pain', 'bare not'],
      // THE HEADING-STRIP RESIDUE — every one of these is a strict SUFFIX of a
      // real dictation and every one of them says the opposite of it.
      ['warfarin, aspirin, or clopidogrel.', 'Warfarin', 'strip residue'],
      ['fever, chills, or night sweats.', 'Fever', 'strip residue'],
      ['diabetes, hypertension, and coronary artery disease.', 'Diabetes', 'strip residue'],
      ['chest pain and dyspnea.', 'Chest pain', 'strip residue'],
      ['pulmonary embolism.', 'Pulmonary embolism', 'strip residue'],
      // SCOPE — the cue belongs to another clause.
      ['No acute findings. Pneumonia is present.', 'Pneumonia', 'other clause'],
      ['No fever. Patient smokes daily.', 'Smoking', 'unlocatable, two clauses'],
      // ⚠️ RECORDED HONEST LIMITS, NOT OVERSIGHTS. A hedge is not a denial and
      // an ambiguous object is not a denial, so both FAIL TOWARD BLANK. A blank
      // is a visible absence; an inverted sentence is a signed assertion.
      ['Doubt pulmonary embolism.', 'Pulmonary embolism', 'hedge — refused by choice'],
      ['Cannot identify a lesion.', 'Lesion', 'ambiguous object — refused by choice'],
    ];
    for (const [text, finding, why] of REFUSE) {
      expect([why, text, selfNegationScopingFinding(text, finding)]).toEqual([
        why,
        text,
        null,
      ]);
    }
  });

  // ── RULE 2 — selection-shaped fields never select on a denial ─────────────

  it('(2a) SINGLE_SELECT (dropDownList) — a denial selects NOTHING and prints no option', async () => {
    const driven = await drive({ denied: ['exam.side'] });
    const { field, resolution } = driven.byLabel('Exam side');
    expect(field.kind).toBe('single_select');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.selectedOptionOrdinal).toBeNull();
    expect(resolution.reasonCode).toBe('denial_withheld_selection_asserts_presence');

    const control = controlById(await driven.render(), '100');
    // ⚠️ THE PREDECESSOR GATE ASSERTED THE OPPOSITE OF THIS LINE — it pinned
    // `toContain('<w:t>Right</w:t>')` for a denied dropdown and called it "a
    // named residual, an OWNER QUESTION". #157(b) IS that owner answer.
    expect(control).not.toContain('<w:t>Right</w:t>');
    expect(control).not.toContain('<w:t>R</w:t>');
    // Blank, exactly as an honest `not_mentioned` field is blank — see (pre-4).
    expect(renderedTextOf(control)).toBe(BLANK);
    expect(control).not.toContain('Choose an item.');
  });

  it('(2b) SINGLE_SELECT (comboBox) — the same, on the other choice control', async () => {
    const driven = await drive({ denied: ['encounter.category'] });
    const { field, resolution } = driven.byLabel('Encounter category');
    expect(field.kind).toBe('single_select');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.selectedOptionOrdinal).toBeNull();

    const control = controlById(await driven.render(), '101');
    expect(control).not.toContain('<w:t>Follow-up</w:t>');
    expect(control).not.toContain('<w:t>Initial</w:t>');
    expect(renderedTextOf(control)).toBe(BLANK);
  });

  it('(2c) ROW PROTOTYPE — a denied repeating section expands NO row', async () => {
    const driven = await drive({ denied: [ROW_CONCEPT] });
    const { field, resolution } = driven.byLabel('Repeat finding');
    expect(field.rowPrototype).toBe(true);
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.reasonCode).toBe('denial_withheld_repeating_rows_assert_presence');

    const section = controlById(await driven.render(), '106');
    expect(section).not.toContain('<w:t>Hepatomegaly</w:t>');
    expect(section).not.toContain('<w:t>Splenomegaly</w:t>');
    expect(renderedTextOf(section)).toBe(BLANK);
  });

  it('(2d) MULTI_SELECT — measured as structurally unreachable, and covered at the contract', async () => {
    // ⚠️ STATED, NOT SKIPPED. `compileTemplateDocx` contains ZERO occurrences of
    // 'multi_select' and can never emit one, so there is no end-to-end route.
    // Asserting it as a property of the compiled IR rather than as a claim:
    const { ir } = await compiledSource();
    expect(ir.fields.some((f) => f.kind === 'multi_select')).toBe(false);

    const multi = {
      fieldId: `ttf_${'a'.repeat(24)}`,
      kind: 'multi_select' as const,
      rowPrototype: false,
      criticality: 'routine' as const,
      clinicallyMaterial: true,
      allowedOptions: [{ ordinal: 1, value: 'Reflux', displayText: 'Reflux' }],
    } as unknown as TemplateField;
    const fact = handBuilt(99, 'exam', 'Reflux', 'There is no reflux.', 'denied');

    for (const behavior of [
      'value_only',
      'affirmative_only',
      'explicit_denial_allowed',
    ] as const) {
      const outcome = denialOutcome(
        multi,
        { polarityBehavior: behavior } as SemanticMapping,
        [fact],
      );
      expect([behavior, outcome.status]).toEqual([behavior, 'denial_withheld']);
      expect([behavior, outcome.value]).toEqual([behavior, null]);
    }
    // And the RENDERER's own wall refuses a multi_select denial carrying values,
    // whoever hands it over.
    expect(isPrintableDenial(multi, ['Reflux'])).toBe(false);
  });

  it('(2e) CHECKBOX — value === false still renders unchecked: UNCHANGED', async () => {
    const driven = await drive({ denied: ['medication.review'] });
    const { field, resolution } = driven.byLabel('Medication reviewed');
    expect(field.kind).toBe('checkbox');
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe(false);
    expect(resolution.reasonCode).toBe('explicit_denial_supported');

    const box = controlById(await driven.render(), '104');
    expect(box).toContain('w14:checked w14:val="0"');
    expect(box).toContain('☐');
  });

  it('(2f) ⚠️ THE BRIDGE OVERLAY CANNOT OVERWRITE A WITHHELD DENIAL', async () => {
    // ⚠️ RULE (2) IS DECIDED IN THE RESOLVER AND WAS UNDONE ONE FUNCTION LATER.
    // `mergeFieldResolutions` asked "is the baseline UNFILLED?" as
    //
    //     current.value === null || UNFILLED.has(current.status)
    //
    // and `denial_withheld` carries `value === null` BY SCHEMA CONSTRUCTION —
    // `ir.ts`'s refine makes any other shape unrepresentable. So the FIRST
    // clause was true for every withheld denial there can ever be, an overlay
    // pick overwrote it, and the dropdown rendered THE VERY FINDING THE
    // ENCOUNTER DENIED: validation green, the note's own pick cited, every
    // count blank. WITHHOLDING IS A DECISION; ABSENCE IS NOT.
    //
    // ⚠️ AND THE ASSERTION IS ON THE RENDERED `word/document.xml`, NOT ON THE
    // MERGED OBJECT. A merge that returns the right resolution and a renderer
    // that prints the wrong option are different claims, and only the second
    // one is what a doctor signs.
    const driven = await drive({
      denied: ['exam.side'],
      omit: ['encounter.category'],
    });
    expect(driven.validation.valid).toBe(true);
    const side = driven.byLabel('Exam side');
    const category = driven.byLabel('Encounter category');

    // THE TWO BASELINE PRECONDITIONS, ASSERTED RATHER THAN ASSUMED — they are
    // what make the pair below a CONTRAST rather than two unrelated rows.
    //   · Exam side is WITHHELD — blank because the encounter denied it.
    //   · Encounter category is GENUINELY UNFILLED — blank because nothing was
    //     said. Both carry `value === null`, which is precisely why the old
    //     predicate could not tell them apart.
    expect(side.resolution.status).toBe('denial_withheld');
    expect(side.resolution.value).toBeNull();
    expect(category.resolution.status).toBe('not_mentioned');
    expect(category.resolution.value).toBeNull();

    // THE REAL BRIDGE, driven the way `fill-engine` drives it: the compiled
    // marker text, the adopted note that answered both markers, and the
    // resolver's own baseline.
    const markerText = [
      'Exam side: {{one of: Left|Right|Bilateral}}',
      'Encounter category: {{one of: Initial|Follow-up}}',
    ].join('\n');
    const filledNote = ['Exam side: Right', 'Encounter category: Follow-up'].join('\n');
    const bridged = bridgeTemplateFill({
      facts: driven.facts,
      mappings: driven.mappings,
      ir: driven.ir,
      markerText,
      filledNote,
      baseline: driven.resolutions,
    });

    // ⚠️ NON-VACUITY ON THE OVERLAY ITSELF, AND IT IS THE LOAD-BEARING ROW.
    // `bridgeChoiceSlotPicks` mints one provenance fact per ACCEPTED pick,
    // before the merge runs — so two facts prove the bridge really did recover
    // a pick FOR THE DENIED DROPDOWN and the MERGE is what refused it. Without
    // this the arm goes green whenever the note fails to align and nothing is
    // overlaid at all, which is the one way it could pass while proving
    // nothing.
    expect(bridged.facts.map((f) => f.concept).sort()).toEqual([
      'encounter.category',
      'exam.side',
    ]);
    expect(bridged.facts.map((f) => f.value).sort()).toEqual(['R', 'follow_up']);

    const merged = (label: string): FieldResolution => {
      const field = driven.byLabel(label).field;
      const found = bridged.resolutions.find((r) => r.fieldId === field.fieldId);
      if (!found) throw new Error(`no merged resolution for ${label}`);
      return found;
    };

    // THE DENIAL SURVIVES THE MERGE, UNCHANGED — status, value, ordinal and the
    // named reason.
    expect(merged('Exam side').status).toBe('denial_withheld');
    expect(merged('Exam side').value).toBeNull();
    expect(merged('Exam side').selectedOptionOrdinal).toBeNull();
    expect(merged('Exam side').reasonCode).toBe(
      'denial_withheld_selection_asserts_presence',
    );
    // THE CONTROL — the overlay DOES still fill a genuinely unfilled field, or
    // this arm proves only that the bridge is broken.
    expect(merged('Encounter category').status).toBe('supported');
    expect(merged('Encounter category').value).toBe('follow_up');
    expect(merged('Encounter category').reasonCode).toBe('choice_slot_pick');

    // ── AND NOW THE DOCUMENT ────────────────────────────────────────────────
    // The picks' provenance facts travel WITH the resolutions; a citation to a
    // fact outside the manifest's fact set is untraceable and the validator
    // says so.
    const validation = validateTemplateTwin({
      fields: driven.ir.fields,
      mappings: driven.mappings,
      facts: [...driven.facts, ...bridged.facts],
      resolutions: bridged.resolutions,
      tables: driven.ir.tables,
      unsupported: driven.ir.unsupported,
      certifiedFieldIds: driven.ir.fields.map((f) => f.fieldId),
      now: '2026-01-01T00:00:00.000Z',
    });
    expect(
      validation.issues
        .filter((i) => i.severity === 'blocking')
        .map((i) => `${i.fieldId}:${i.code}`),
    ).toEqual([]);
    expect(validation.valid).toBe(true);
    const rendered = await renderTemplateDocx({
      source: driven.source,
      ir: driven.ir,
      resolutions: bridged.resolutions,
      validation,
    });
    expect(rendered.verification.verified).toBe(true);
    const xml = documentXmlOf(rendered.document);

    // ⚠️ THE HARM, ASSERTED WHERE IT LANDS. `Right` is what the renderer prints
    // for option `R` (`displayText`), so this is the exact string a doctor
    // would have signed under a dictation that DENIED that side.
    const deniedControl = controlById(xml, '100');
    expect(deniedControl).not.toContain('<w:t>Right</w:t>');
    expect(deniedControl).not.toContain('<w:t>R</w:t>');
    expect(renderedTextOf(deniedControl)).toBe(BLANK);
    // And the control's other half, on the document: the honest fill rendered.
    expect(renderedTextOf(controlById(xml, '101'))).toBe('Follow-up');
  });

  // ── RULE 3 — no denial may refuse an export ──────────────────────────────

  for (const behavior of [
    'value_only',
    'affirmative_only',
    'explicit_denial_allowed',
  ] as const) {
    it(`(3a) EVERY KIND DENIED AT ONCE under \`${behavior}\` — nothing blocks, the document renders`, async () => {
      const driven = await drive({ denied: ALL_CONCEPTS, behavior });

      // Not one blocking issue anywhere in the fill.
      expect(
        driven.validation.issues
          .filter((i) => i.severity === 'blocking')
          .map((i) => `${i.fieldId}:${i.code}`),
      ).toEqual([]);
      expect(driven.validation.valid).toBe(true);

      // ⚠️ THE DOCUMENT ITSELF. `validation.valid` is only the FIRST of two
      // refusal doors — `fill-engine.ts` returns `render: null` on it, and
      // `renderer.ts` throws VALIDATION_REQUIRED independently. This awaits the
      // second one.
      const xml = await driven.render();
      expect(xml.length).toBeGreaterThan(0);

      // Every planned field resolved to an HONEST per-field outcome — the
      // quote, the false state, or a blank carrying a NAMED reason. Never a
      // status that blocks.
      for (const label of Object.keys(PLAN)) {
        const { resolution } = driven.byLabel(label);
        expect([label, resolution.status]).toEqual([
          label,
          resolution.status === 'explicitly_denied'
            ? 'explicitly_denied'
            : 'denial_withheld',
        ]);
        expect([label, resolution.reasonCode.length > 0]).toEqual([label, true]);
        if (resolution.status === 'denial_withheld') {
          // ⚠️ TWO PREFIXES, NOT ONE, AND THE SECOND IS DELIBERATE. #157(c)'s
          // Q1 token is spelled `denial_quote_not_self_negating` — the
          // ruling's own wording — so a prefix assertion naming only the
          // sibling family would red on a correct token. Recorded here rather
          // than "tidied" into line, because the ruling names the identifier.
          expect([
            label,
            resolution.reasonCode.startsWith('denial_withheld_') ||
              resolution.reasonCode === 'denial_quote_not_self_negating',
          ]).toEqual([label, true]);
        }
      }
    });
  }

  it('(3b) THE MULTI-FACT HARM — two denied facts, ONE dictated sentence, RENDERS', async () => {
    // ⚠️ THIS IS THE MEASURED 28-of-31 KILLED-DOCUMENTS CASE. Before #157(b) the
    // `!allDenied` guard at resolver/index.ts diverted an accumulating denied
    // narrative into `multiple_distinct_supported_values` -> FIELD_CONFLICT
    // (always blocking) -> the renderer threw VALIDATION_REQUIRED and the doctor
    // lost the WHOLE DOCUMENT because of one negative sentence.
    const text = 'The patient has no history of diabetes or hypertension.';
    const facts = projected(text, {
      past_medical_history: [
        { condition: 'Diabetes', evidence_quote: text },
        { condition: 'Hypertension', evidence_quote: text },
      ],
    });
    expect(facts).toHaveLength(2);
    expect(facts.every((f) => f.polarity === 'denied')).toBe(true);
    expect(new Set(facts.map((f) => f.evidenceQuote)).size).toBe(1);

    const driven = await drive({
      omit: ['past_medical_history'],
      extraFacts: facts,
    });
    const { resolution } = driven.byLabel('Past medical history');
    expect(resolution.status).toBe('explicitly_denied');
    expect(resolution.value).toBe(text);
    expect(resolution.sourceFactIds).toHaveLength(2);

    const control = controlById(await driven.render(), '302');
    expect(renderedTextOf(control)).toBe(text);
    // ZERO COMPOSITION survives the multi-fact case: two facts, ONE sentence,
    // and no separator anywhere.
    expect(text.endsWith(renderedTextOf(control))).toBe(true);
    expect(control).not.toContain('; ');
    expect(control).not.toContain('<w:t>Diabetes</w:t>');
    expect(control).not.toContain('<w:t>Hypertension</w:t>');
  });

  it('(3c) TWO DISTINCT denied sentences — WITHHELD with a named reason, and it still RENDERS', async () => {
    // There is no verbatim rendering of two different sentences: joining them
    // is a composition, and rule (1) forbids one absolutely. So the honest
    // outcome is a NAMED BLANK — never a refused export, and never a
    // manufactured sentence.
    const facts = projected('No history of diabetes. The patient denies hypertension.', {
      past_medical_history: [
        { condition: 'Diabetes', evidence_quote: 'No history of diabetes.' },
        { condition: 'Hypertension', evidence_quote: 'The patient denies hypertension.' },
      ],
    });
    expect(new Set(facts.map((f) => f.evidenceQuote)).size).toBe(2);

    const driven = await drive({ omit: ['past_medical_history'], extraFacts: facts });
    const { resolution } = driven.byLabel('Past medical history');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.reasonCode).toBe('denial_withheld_multiple_distinct_quotes');
    expect(resolution.sourceFactIds).toHaveLength(2); // the citation SURVIVES

    const control = controlById(await driven.render(), '302');
    expect(renderedTextOf(control)).toBe(BLANK);
    expect(control).not.toContain('No history of diabetes.');
    expect(control).not.toContain('The patient denies hypertension.');
  });

  it('(3d) THE ISOLATING CONTROL — the SAME two facts affirmed still join and render', async () => {
    // Polarity is the only difference between this and (3c). Without this row,
    // (3c) could pass because the fixture was broken rather than because the
    // denial was withheld.
    const facts = projected('History of diabetes. The patient reports hypertension.', {
      past_medical_history: [
        { condition: 'Diabetes', evidence_quote: 'History of diabetes.' },
        { condition: 'Hypertension', evidence_quote: 'The patient reports hypertension.' },
      ],
    });
    expect(facts.every((f) => f.polarity === 'affirmed')).toBe(true);

    const driven = await drive({ omit: ['past_medical_history'], extraFacts: facts });
    const { resolution } = driven.byLabel('Past medical history');
    expect(resolution.status).toBe('supported');
    expect(resolution.reasonCode).toBe('list_valued_narrative_joined');
    expect(resolution.value).toBe('Diabetes; Hypertension');
    expect(renderedTextOf(controlById(await driven.render(), '302'))).toBe(
      'Diabetes; Hypertension',
    );
  });

  it('(3e) ⚠️ AN AFFIRMED BYSTANDER IN THE WIDER EVIDENCE SET MUST NOT KILL THE EXPORT', async () => {
    // ⚠️ THE RESOLUTION CITES `judged`, NOT `temporalCandidates` — AND THE
    // VALIDATOR RE-ASKS THE QUESTION OF THE SET THE RESOLUTION CITES.
    //
    // `allDenied` is computed from `judged` — for a select, the EXACT-OPTION
    // subset — because a fact that cannot fill this dropdown is not evidence
    // about it. The denial branch then handed `temporalCandidates` to
    // `makeResolution`, so the resolution advertised evidence it had never
    // judged. `DENIAL_WITHHELD_WITHOUT_DENIAL` is BLOCKING and asks exactly the
    // right question of exactly the wrong set:
    //
    //     citedFacts.some((fact) => fact.polarity !== 'denied')   -> true
    //     -> blocking -> VALIDATION_REQUIRED -> THE WHOLE EXPORT IS LOST
    //
    // …for a document in which ONE dropdown was dictated in the negative while
    // an unrelated sentence about the same coarse concept was dictated in the
    // positive. Production carries 28 single_selects mapped to coarse concepts
    // (`exam.vascular` and the like) that every sentence in the section shares,
    // so the bystander is the NORMAL case, not the exotic one.
    //
    // THE TRIPLE BELOW IS THE ISOLATION: (A) and (H) render on both sides of
    // the fix, and only (B) — the AFFIRMED bystander — separates them. Without
    // them, (B) could pass because the fixture never reached the denial branch.
    const { ir } = await compiledSource();
    const side = ir.fields.find((f) => f.originalLabel === 'Exam side')!;

    // A BYSTANDER IS A BYSTANDER BECAUSE IT IS NOT ONE OF THIS FIELD'S OWN
    // OPTIONS — that is exactly what puts it INSIDE `temporalCandidates` and
    // OUTSIDE `judged`. Asserted, because if it were an exact option the triple
    // would be a polarity CONFLICT and would test something else entirely.
    const BYSTANDER_VALUE = 'Technically adequate';
    const BYSTANDER_QUOTE = 'The study was technically adequate.';
    expect(side.allowedOptions.map((o) => o.value)).not.toContain(BYSTANDER_VALUE);
    expect(side.allowedOptions.map((o) => o.displayText)).not.toContain(BYSTANDER_VALUE);
    // And the absence assertions below cannot be satisfied by the quote itself.
    expect(BYSTANDER_QUOTE.includes(BYSTANDER_VALUE)).toBe(false);

    const bystander = (polarity: 'affirmed' | 'denied'): EncounterFact =>
      handBuilt(11, 'exam.side', BYSTANDER_VALUE, BYSTANDER_QUOTE, polarity);

    const CASES = [
      { name: 'A — the denial ALONE', extra: [] as EncounterFact[], wider: 1 },
      { name: 'B — plus an AFFIRMED bystander', extra: [bystander('affirmed')], wider: 2 },
      { name: 'H — plus the SAME bystander, DENIED', extra: [bystander('denied')], wider: 2 },
    ] as const;

    for (const row of CASES) {
      const driven = await drive({ denied: ['exam.side'], extraFacts: [...row.extra] });
      const { field, resolution } = driven.byLabel('Exam side');

      // NON-VACUITY: the bystander really did reach the resolver's candidate
      // set. If it were dropped at the concept or temporality filter the wider
      // set would be 1 and B would be a duplicate of A.
      expect([row.name, driven.factsFor('exam.side').length]).toEqual([
        row.name,
        row.wider,
      ]);

      // The denial is decided from `judged` and is unchanged by the bystander.
      expect([row.name, resolution.status]).toEqual([row.name, 'denial_withheld']);
      expect([row.name, resolution.value]).toEqual([row.name, null]);
      expect([row.name, resolution.reasonCode]).toEqual([
        row.name,
        'denial_withheld_selection_asserts_presence',
      ]);

      // ⚠️ THE D2 PROPERTY ITSELF: the CITATION is `judged` — the one denied
      // fact that could actually have filled this dropdown — and never the
      // wider set. This is the row that moves when the fix is reverted.
      expect([row.name, resolution.sourceFactIds]).toEqual([row.name, [factId(1)]]);
      expect([row.name, resolution.evidenceAnchorIds]).toEqual([
        row.name,
        ['gate157b-anchor-1'],
      ]);

      // NOT ONE BLOCKING ISSUE — and the field's own issue list is exactly the
      // non-blocking one rule (3) prescribes.
      expect([
        row.name,
        driven.validation.issues
          .filter((i) => i.severity === 'blocking')
          .map((i) => `${i.fieldId}:${i.code}`),
      ]).toEqual([row.name, []]);
      expect([
        row.name,
        driven.validation.issues
          .filter((i) => i.fieldId === field.fieldId)
          .map((i) => `${i.code}:${i.severity}`),
      ]).toEqual([row.name, ['FIELD_DENIAL_WITHHELD:warning']]);

      // ⚠️ AND THE DOCUMENT SURVIVES. `validation.valid` is only the FIRST
      // refusal door; `render()` awaits the renderer's independent
      // VALIDATION_REQUIRED throw as well.
      const control = controlById(await driven.render(), '100');
      expect([row.name, renderedTextOf(control)]).toEqual([row.name, BLANK]);
      expect([row.name, control.includes('<w:t>Right</w:t>')]).toEqual([row.name, false]);
      expect([row.name, control.includes(BYSTANDER_VALUE)]).toEqual([row.name, false]);
    }
  });

  // ── RULE 4 — each polarity behaviour regains a distinct meaning ───────────

  it('(4) value_only -> BLANK, affirmative_only -> BLANK, explicit_denial_allowed -> THE QUOTE', async () => {
    const expected = [
      {
        behavior: 'value_only',
        status: 'denial_withheld',
        value: null,
        reason: 'denial_withheld_value_only',
      },
      {
        behavior: 'affirmative_only',
        status: 'denial_withheld',
        value: null,
        reason: 'denial_withheld_affirmative_only',
      },
      {
        behavior: 'explicit_denial_allowed',
        status: 'explicitly_denied',
        value: 'no known drug allergies',
        reason: 'explicit_denial_dictated_quote',
      },
    ] as const;
    for (const row of expected) {
      const behavior: Behavior = row.behavior;
      const driven = await drive({ denied: ['allergy.substance'], behavior });
      const { resolution } = driven.byLabel('Allergies');
      expect([behavior, resolution.status]).toEqual([behavior, row.status]);
      expect([behavior, resolution.value]).toEqual([behavior, row.value]);
      expect([behavior, resolution.reasonCode]).toEqual([behavior, row.reason]);
      // The citation is retained under EVERY behaviour — a withheld denial that
      // discarded its facts would make the manifest unable to say why.
      expect([behavior, resolution.sourceFactIds.length]).toEqual([behavior, 1]);

      const control = controlById(await driven.render(), '301');
      expect([behavior, renderedTextOf(control)]).toEqual([
        behavior,
        behavior === 'explicit_denial_allowed' ? 'no known drug allergies' : BLANK,
      ]);
    }
  });

  // ── THE MANIFEST MUST NOT BE SILENT ──────────────────────────────────────

  it('(5a) a withheld denial is COUNTED — needsReview and criticalUnresolved, never `filled`', async () => {
    const driven = await drive({ denied: ['allergy.substance'], behavior: 'value_only' });
    const { field, resolution } = driven.byLabel('Allergies');
    expect(resolution.status).toBe('denial_withheld');

    const counts = templateTwinCounts(driven.resolutions, driven.ir.fields);
    const withheld = driven.resolutions.filter((r) => r.status === 'denial_withheld');
    expect(withheld.length).toBeGreaterThan(0);
    expect(counts.needsReview).toBeGreaterThanOrEqual(withheld.length);
    // The Allergies field is `criticality: 'allergy'` — not routine — so it
    // reaches the critical bucket too.
    expect(field.criticality).not.toBe('routine');
    expect(counts.criticalUnresolved).toBeGreaterThanOrEqual(1);
    // And it is NOT counted as filled: `filled` keys on `value !== null`.
    expect(
      driven.resolutions.filter((r) => r.value !== null).map((r) => r.fieldId),
    ).not.toContain(resolution.fieldId);
  });

  it('(5b) the validation issue exists, names the field, and is NEVER blocking', async () => {
    for (const behavior of ['value_only', 'affirmative_only'] as const) {
      const driven = await drive({ denied: ['allergy.substance'], behavior });
      const { field } = driven.byLabel('Allergies');
      const mine = driven.validation.issues.filter((i) => i.fieldId === field.fieldId);
      expect([behavior, mine.map((i) => i.code)]).toEqual([
        behavior,
        ['FIELD_DENIAL_WITHHELD'],
      ]);
      expect([behavior, mine[0]!.severity]).toEqual([behavior, 'warning']);
      // ⚠️ AND IT IS A WARNING EVEN THOUGH THE FIELD IS BOTH CLINICALLY MATERIAL
      // AND NON-ROUTINE — the exact combination that makes FIELD_AMBIGUOUS
      // blocking. That conditional severity is what killed the document.
      expect(field.clinicallyMaterial).toBe(true);
      expect(field.criticality).not.toBe('routine');
    }
  });

  it('(5c) CERTIFICATION CANNOT GO GREEN with a clinically material section silently blank', async () => {
    // ⚠️ REWRITTEN FOR #157(c) Q2, AND THE FIXTURE CHANGE IS THE POINT. This
    // arm used a `value_only` denial — which Q2 now EXEMPTS, because a mapping
    // that correctly refuses to carry a denial is behaving exactly as ruled and
    // must not be unable to certify for it. So the blocker is now proved with a
    // NON-EXEMPT token: two genuinely different denied sentences have no
    // verbatim rendering, the section blanks, and THAT is a hole a certificate
    // must not attest.
    const facts = projected('No history of diabetes. The patient denies hypertension.', {
      past_medical_history: [
        { condition: 'Diabetes', evidence_quote: 'No history of diabetes.' },
        { condition: 'Hypertension', evidence_quote: 'The patient denies hypertension.' },
      ],
    });
    const driven = await drive({ omit: ['past_medical_history'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Past medical history');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.reasonCode).toBe('denial_withheld_multiple_distinct_quotes');
    expect(CERTIFICATION_EXEMPT_DENIAL_REASONS.has(resolution.reasonCode)).toBe(false);
    expect(field.clinicallyMaterial || field.criticality !== 'routine').toBe(true);

    // The certification gate reads THIS, and it is non-empty.
    const blocked = denialWithheldMaterialFieldIds(driven.ir.fields, driven.resolutions);
    expect(blocked).toContain(field.fieldId);

    // ⚠️ AND THE POINT OF THE NEW STATUS: certification's own relaxation does
    // NOT reach it. `allowUncertifiedForSyntheticTest` downgrades
    // FIELD_NEEDS_CLINICIAN_INPUT to a warning — which is why reusing that
    // status would have certified GREEN over a blank material section — while
    // the withheld-denial blocker is computed from the RESOLUTIONS and is
    // untouched by that flag.
    const relaxed = validateTemplateTwin({
      fields: driven.ir.fields,
      mappings: driven.mappings,
      facts: driven.facts,
      resolutions: driven.resolutions,
      tables: driven.ir.tables,
      unsupported: driven.ir.unsupported,
      allowUncertifiedForSyntheticTest: true,
      now: '2026-01-01T00:00:00.000Z',
    });
    expect(relaxed.valid).toBe(true); // the DOCUMENT is fine — rule (3)
    expect(
      denialWithheldMaterialFieldIds(driven.ir.fields, driven.resolutions),
    ).toEqual(blocked); // the CERTIFICATE is not

    // NON-VACUITY for this predicate: with nothing denied it returns nothing,
    // so a green here is a measurement rather than a constant.
    const affirmed = await drive();
    expect(denialWithheldMaterialFieldIds(affirmed.ir.fields, affirmed.resolutions)).toEqual(
      [],
    );
  });

  // ══ OWNER RULING #157(c) Q2 — THE CERTIFICATION BLOCKER EXEMPTS AN
  // ENUMERATED ALLOWLIST, NEVER A BLANKET ═════════════════════════════════

  it('(7a) ⚠️ SET EQUALITY, BOTH DIRECTIONS — the exemption IS rule (4)’s approved list', async () => {
    // ⚠️ THE TWO SIDES COME FROM DIFFERENT PLACES, WHICH IS THE ONLY THING THAT
    // MAKES THIS A GATE RATHER THAN A TAUTOLOGY. One side is the CONSTANT the
    // blocker reads. The other is derived by DRIVING the real pipeline for
    // every behaviour #157(c) Q2 names and collecting the reason token the
    // resolver actually emitted. Comparing the constant with a copy of itself
    // would pass for any pair of values.
    //
    //   · a future token added to the constant that no approved behaviour
    //     produces -> the constant is a superset -> RED
    //   · an approved behaviour that starts emitting a new token -> the driven
    //     set is a superset -> RED
    const emitted = new Set<string>();

    // rule (4): value_only -> BLANK, affirmative_only -> BLANK
    for (const behavior of ['value_only', 'affirmative_only'] as const) {
      const driven = await drive({ denied: ['allergy.substance'], behavior });
      const { resolution } = driven.byLabel('Allergies');
      expect([behavior, resolution.status]).toEqual([behavior, 'denial_withheld']);
      emitted.add(resolution.reasonCode);
    }
    // rule (2): the selection-shaped withholding
    {
      const driven = await drive({ denied: ['exam.side'] });
      const { resolution } = driven.byLabel('Exam side');
      expect(resolution.status).toBe('denial_withheld');
      emitted.add(resolution.reasonCode);
    }
    // Q1: the quote that does not negate itself
    {
      const driven = await drive({
        omit: ['ros.constitutional'],
        extraFacts: statedPolarityRos(),
      });
      const { resolution } = driven.byLabel('Review of systems');
      expect(resolution.status).toBe('denial_withheld');
      emitted.add(resolution.reasonCode);
    }

    expect([...emitted].sort()).toEqual([...CERTIFICATION_EXEMPT_DENIAL_REASONS].sort());
    // NON-VACUITY: four distinct tokens, not one token measured four times.
    expect(emitted.size).toBe(4);
  });

  it('(7b) EVERY denial reason token is exempt or blocking, and the enumeration RECONCILES', async () => {
    // ⚠️ THE ARITHMETIC IS THE POINT. A thirteenth token added to
    // `denial-contract.ts` and to nothing else would join neither column, and
    // the reconciliation below is what makes that a RED rather than a silence.
    // The scan is over quoted TOKEN LITERALS in the module's own source — an
    // identifier check, not a prose-spelling check.
    const EXEMPT = [
      'denial_withheld_value_only',
      'denial_withheld_affirmative_only',
      'denial_withheld_selection_asserts_presence',
      'denial_quote_not_self_negating',
    ];
    const BLOCKING = [
      'denial_withheld_quote_not_dictated',
      'denial_withheld_fact_not_denied',
      'denial_withheld_quote_empty_after_heading_strip',
      'denial_withheld_quote_unrenderable',
      'denial_withheld_kind_cannot_carry_denial',
      'denial_withheld_no_cited_denial',
      'denial_withheld_multiple_distinct_quotes',
      // ⚠️ RECORDED AS AN OPEN QUESTION, NOT AS A SETTLED ANSWER. #157(c) Q2
      // names "the selection-shaped withholding", singular; a repeating row
      // asserts presence by the same rule-(2) logic, and the ruling does not
      // say whether it joins the exemption. It keeps blocking because that is
      // the direction that costs a certificate rather than attesting a hole.
      'denial_withheld_repeating_rows_assert_presence',
    ];

    // ⚠️ `import.meta.url` IS NOT A `file:` URL UNDER THIS RUNNER — measured,
    // `fileURLToPath` throws "The URL must be of scheme file". So the path is
    // resolved from the process cwd and the resolution is ASSERTED: a guess
    // that landed on nothing would make the scan below return an empty set and
    // the whole reconciliation vacuous.
    const candidates = [
      'src/lib/template-twin/denial-contract.ts',
      'apps/transcribe-md/src/lib/template-twin/denial-contract.ts',
    ].map((relative) => resolve(process.cwd(), relative));
    const resolved = candidates.filter((path) => existsSync(path));
    expect(resolved).toHaveLength(1);
    const source = readFileSync(resolved[0]!, 'utf8');
    const scanned = new Set(
      [...source.matchAll(/'(denial_(?:withheld|quote)_[a-z_]+)'/g)].map((m) => m[1]!),
    );
    // POSITIVE CONTROL for the scanner itself: a pattern that finds nothing is
    // indistinguishable from a module with no tokens.
    expect(scanned.size).toBeGreaterThan(0);
    expect([...scanned].sort()).toEqual([...EXEMPT, ...BLOCKING].sort());
    expect(EXEMPT.length + BLOCKING.length).toBe(scanned.size);
    expect(new Set([...EXEMPT, ...BLOCKING]).size).toBe(EXEMPT.length + BLOCKING.length);

    // And each column behaves as its name claims, through the real predicate on
    // a real clinically material field.
    const driven = await drive({ denied: ['allergy.substance'], behavior: 'value_only' });
    const { field } = driven.byLabel('Allergies');
    expect(field.clinicallyMaterial || field.criticality !== 'routine').toBe(true);
    for (const reasonCode of [...EXEMPT, ...BLOCKING]) {
      const patched = withResolution(driven, field.fieldId, { reasonCode });
      const blocked = denialWithheldMaterialFieldIds(driven.ir.fields, patched);
      expect([reasonCode, blocked.includes(field.fieldId)]).toEqual([
        reasonCode,
        !EXEMPT.includes(reasonCode),
      ]);
    }
  });

  it('(7c) an EXEMPT withheld field stops BLOCKING and never counts toward the FILL FLOOR', async () => {
    const driven = await drive({ denied: ['allergy.substance'], behavior: 'value_only' });
    const { field, resolution } = driven.byLabel('Allergies');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.reasonCode).toBe('denial_withheld_value_only');

    // HALF ONE — it no longer blocks certification. This is the change.
    expect(denialWithheldMaterialFieldIds(driven.ir.fields, driven.resolutions)).toEqual([]);

    // HALF TWO — and it STILL does not count as filled. Asserted at the SCHEMA,
    // not merely at the count: `ir.ts`'s refine makes "withheld AND holding a
    // value" unrepresentable, so this half cannot regress through the resolver.
    // It could only regress if somebody relaxed that refine, which is what the
    // second assertion watches.
    expect(resolution.value).toBeNull();
    const forged = FieldResolutionSchema.safeParse({ ...resolution, value: 'anything' });
    expect(forged.success).toBe(false);
    expect(JSON.stringify(forged.error?.issues ?? [])).toContain(
      'A withheld denial must carry no value',
    );

    // ⚠️ HONEST LIMIT, RECORDED RATHER THAN GLOSSED: the filled predicate below
    // is MIRRORED from `certification-lifecycle.ts:763` (`r != null && r.value
    // !== null`) rather than imported. Importing that module drags `next-auth`
    // into the test environment and breaks it outright — the same reason
    // `certification-thresholds.ts` exists as a leaf. The THRESHOLD is imported
    // from that leaf, so at least the number cannot drift; the predicate is a
    // mirror and is not byte-faithful.
    const filled = driven.resolutions.filter((r) => r != null && r.value !== null);
    expect(filled.map((r) => r.fieldId)).not.toContain(field.fieldId);
    expect(MIN_CERTIFIED_FILLED_FIELDS).toBe(10);
    // NON-VACUITY for that predicate: the affirmed run DOES fill this field, so
    // "not in the filled set" is a measurement rather than a constant.
    const affirmed = await drive();
    expect(
      affirmed.resolutions.filter((r) => r.value !== null).map((r) => r.fieldId),
    ).toContain(field.fieldId);
  });

  // ══ OWNER RULING #157(c) Q3 — MIXED POLARITY RESOLVES PER FACT ══════════

  it('(8a) ⚠️ THE DOCUMENT-KILLER DIES — one affirmed + one denied fact RENDER, per fact', async () => {
    // Before this change: status=conflict, reason=polarity_conflict,
    // valid=false, blocking=[FIELD_CONFLICT], renderTemplateDocx REJECTED.
    // One affirmed fact plus one denied fact in one narrative field and the
    // doctor lost the whole document.
    const facts = projected(MIXED_TEXT, MIXED_ENTITIES);
    expect(facts.map((f) => f.polarity)).toEqual(['affirmed', 'denied']);
    expect(facts.map((f) => f.value)).toEqual(['Pneumonia', 'Pulmonary embolism']);

    const driven = await drive({ omit: ['assessment'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Impression');
    expect(field.kind).toBe('narrative_text');
    expect(resolution.status).toBe('supported');
    expect(resolution.reasonCode).toBe('mixed_polarity_per_fact');
    expect(resolution.sourceFactIds).toHaveLength(2);
    expect(driven.validation.issues.filter((i) => i.severity === 'blocking')).toEqual([]);

    // THE EXACT RENDERED TEXT, out of a really-rendered word/document.xml.
    const printed = renderedTextOf(controlById(await driven.render(), '304'));
    expect(printed).toBe('Pneumonia; No evidence of pulmonary embolism.');

    // ⚠️ ZERO COMPOSITION, ASSERTED PER SEGMENT — because it CANNOT be asserted
    // over the whole field. The joined string is a substring of no single
    // quote, so a field-level `endsWith` would be either vacuous or wrong. Each
    // segment is checked against the fact it came from, and the only
    // house-authored characters in the entire value are the separator the
    // affirmed path has always used.
    const segments = printed.split('; ');
    expect(segments).toHaveLength(2);
    expect(segments.join('; ')).toBe(printed); // nothing lives between segments
    // segment 0 — the AFFIRMED fact's DERIVED VALUE, exactly.
    expect(segments[0]).toBe(facts[0]!.value);
    // segment 1 — a SUFFIX of the DENIED fact's own quote (nothing manufactured)
    // AND carrying a negation scoping the finding (nothing destroyed). BOTH.
    expect(facts[1]!.evidenceQuote.endsWith(segments[1]!)).toBe(true);
    const cue = selfNegationScopingFinding(segments[1]!, facts[1]!.value);
    expect(cue).not.toBeNull();
    expect(segments[1]!.includes(cue!.match)).toBe(true);
  });

  it('(8b) DICTATION ORDER IS PRESERVED — proved by a reversal control', async () => {
    // Reading the code cannot prove an ordering. Reversing the INPUT and
    // measuring the OUTPUT can, and it is the only thing that distinguishes
    // "kept the order" from "happened to sort that way".
    const forward = await drive({
      omit: ['assessment'],
      extraFacts: projected(MIXED_TEXT, MIXED_ENTITIES),
    });
    expect(renderedTextOf(controlById(await forward.render(), '304'))).toBe(
      'Pneumonia; No evidence of pulmonary embolism.',
    );

    const reversedText =
      'No evidence of pulmonary embolism. Findings consistent with pneumonia.';
    const reversed = await drive({
      omit: ['assessment'],
      extraFacts: projected(reversedText, {
        assessment_discussed: [
          {
            finding: 'Pulmonary embolism',
            evidence_quote: 'No evidence of pulmonary embolism.',
          },
          { finding: 'Pneumonia', evidence_quote: 'Findings consistent with pneumonia.' },
        ],
      }),
    });
    expect(renderedTextOf(controlById(await reversed.render(), '304'))).toBe(
      'No evidence of pulmonary embolism.; Pneumonia',
    );
  });

  it('(8c) A NON-SELF-NEGATING DENIAL IN A MIXED FIELD CONTRIBUTES NOTHING BUT ITS TOKEN', async () => {
    // ⚠️ THE OWNER'S OWN ROS IS MIXED-POLARITY, AND ROS IS THE ONE ENTITY TYPE
    // THAT STATES POLARITY — so this is the exact shape Q1 and Q3 meet in.
    const facts = projected(
      'Fatigue and malaise. Fever, chills, and night sweats.',
      {
        ros: [
          {
            system: 'constitutional',
            finding: 'Fatigue',
            polarity: 'affirmed',
            evidence_quote: 'Fatigue and malaise.',
          },
          {
            system: 'constitutional',
            finding: 'Fever',
            polarity: 'denied',
            evidence_quote: 'Fever, chills, and night sweats.',
          },
        ],
      },
    );
    expect(facts.map((f) => f.polarity)).toEqual(['affirmed', 'denied']);

    const driven = await drive({ omit: ['ros.constitutional'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Review of systems');
    expect(resolution.status).toBe('supported');
    // THE AFFIRMED HALF PRINTS; THE DENIAL CONTRIBUTES ONLY ITS REASON TOKEN.
    expect(resolution.value).toBe('Fatigue');
    expect(resolution.reasonCode).toBe(
      'mixed_polarity_per_fact:denial_quote_not_self_negating',
    );
    expect(resolution.sourceFactIds).toHaveLength(2); // the citation SURVIVES

    // THE MANIFEST IS NOT SILENT — and the issue is a WARNING, never blocking.
    const mine = driven.validation.issues.filter((i) => i.fieldId === field.fieldId);
    expect(mine.map((i) => i.code)).toEqual(['FIELD_MIXED_POLARITY_DENIAL_WITHHELD']);
    expect(mine[0]!.severity).toBe('warning');
    expect(mine[0]!.message).toContain('denial_quote_not_self_negating');

    const xml = await driven.render();
    expect(renderedTextOf(controlById(xml, '307'))).toBe('Fatigue');
    // THE AFFIRMATIVE SENTENCE REACHES NO PART OF THE PACKAGE.
    expect(xml).not.toContain('Fever, chills, and night sweats.');
    expect(xml).not.toContain('<w:t>Fever</w:t>');
  });

  it('(8d) THE NEVER-BETTER-THAN-AFFIRMED-ALONE INVARIANT — a refusal leaves the field where it was', async () => {
    // Two DISTINCT affirmed values on a narrative that is not an accumulating
    // SECTION are a genuine conflict, and adding a denial must not launder them
    // into a rendered field. `ros.*` is deliberately absent from
    // `ACCUMULATING_NARRATIVE_CONCEPTS`, so this is the live shape.
    const ros = (
      rows: ReadonlyArray<{ finding: string; polarity: string; quote: string }>,
    ) =>
      projected(rows.map((r) => r.quote).join(' '), {
        ros: rows.map((r) => ({
          system: 'constitutional',
          finding: r.finding,
          polarity: r.polarity,
          evidence_quote: r.quote,
        })),
      });

    const AFFIRMED_TWO = [
      { finding: 'Fatigue', polarity: 'affirmed', quote: 'Fatigue and malaise.' },
      { finding: 'Headache', polarity: 'affirmed', quote: 'Headache since Tuesday.' },
    ];
    const DENIED_ONE = {
      finding: 'Fever',
      polarity: 'denied',
      quote: 'No fever or chills.',
    };

    // WITH the denial -> the mixed contract REFUSES and the field is exactly
    // the conflict it already was.
    const mixed = await drive({
      omit: ['ros.constitutional'],
      extraFacts: ros([...AFFIRMED_TWO, DENIED_ONE]),
    });
    const withDenial = mixed.byLabel('Review of systems').resolution;
    expect(withDenial.status).toBe('conflict');
    expect(withDenial.reasonCode).toBe('polarity_conflict');

    // ⚠️ THE ISOLATING CONTROL, AND IT IS THE WHOLE ARM. Without the denial the
    // SAME two affirmed facts conflict too — so the mixed path took nothing
    // away. A refusal that merely looked correct would pass the row above.
    const affirmedOnly = await drive({
      omit: ['ros.constitutional'],
      extraFacts: ros(AFFIRMED_TWO),
    });
    const noDenial = affirmedOnly.byLabel('Review of systems').resolution;
    expect(noDenial.status).toBe('conflict');
    expect(noDenial.reasonCode).toBe('multiple_distinct_supported_values');

    // Both are blocking, in both runs, exactly as before this ruling.
    for (const run of [mixed, affirmedOnly]) {
      const { field } = run.byLabel('Review of systems');
      expect(
        run.validation.issues
          .filter((i) => i.fieldId === field.fieldId && i.severity === 'blocking')
          .map((i) => i.code),
      ).toEqual(['FIELD_CONFLICT']);
    }
  });

  it('(8f) NON-DIRECT EVIDENCE REFUSES THE MIXED PATH — no `supported` status that blocks', async () => {
    // ⚠️ FOUND BY ADVERSARIAL PASS ON THIS SLICE, NOT BY THE RULING. A
    // `conflicting`-quality fact composed a value, the resolution became
    // `supported`, and `SUPPORTED_STATUS_CONFLICTS_WITH_QUALITY` then blocked
    // it — a field carrying a VALUE while blocked, through a code that has
    // nothing to do with polarity. The mixed contract refuses instead, which
    // leaves the case exactly where this ruling found it.
    const facts = projected(MIXED_TEXT, MIXED_ENTITIES);
    const conflicting = facts.map((fact, index) =>
      index === 0
        ? ({
            ...fact,
            quality: { ...fact.quality, evidence: 'conflicting' as const },
          } as EncounterFact)
        : fact,
    );
    expect(conflicting.map((f) => f.quality.evidence)).toEqual(['conflicting', 'direct']);
    expect(mixedPolarityNarrative(FIELD_STUB, MAPPING_STUB, conflicting)).toEqual({
      kind: 'refused',
    });
    // ISOLATING CONTROL — the SAME facts at `direct` quality DO compose, so the
    // refusal above is about the quality and not about the fixture.
    expect(mixedPolarityNarrative(FIELD_STUB, MAPPING_STUB, facts)).toEqual({
      kind: 'text',
      text: 'Pneumonia; No evidence of pulmonary embolism.',
      reasonCode: 'mixed_polarity_per_fact',
      withheldReasonCodes: [],
    });
  });

  it('(8e) THE EVIDENCE RAIL REACHES THE MIXED VALUE — a value that is not the shared derivation is BLOCKED', async () => {
    const driven = await drive({
      omit: ['assessment'],
      extraFacts: projected(MIXED_TEXT, MIXED_ENTITIES),
    });
    const { field, resolution } = driven.byLabel('Impression');
    expect(resolution.value).toBe('Pneumonia; No evidence of pulmonary embolism.');

    for (const forged of [
      'No evidence of pulmonary embolism.; Pneumonia', // right parts, WRONG ORDER
      'Pneumonia; No pulmonary embolism.', // a plausible synthesis
      'Pneumonia', // the denial silently DROPPED
      'Pneumonia; Findings consistent with pneumonia.', // the affirmed quote
      'Pneumonia;No evidence of pulmonary embolism.', // one character of drift
    ]) {
      const validation = validateTemplateTwin({
        fields: driven.ir.fields,
        mappings: driven.mappings,
        facts: driven.facts,
        resolutions: withResolution(driven, resolution.fieldId, { value: forged }),
        tables: driven.ir.tables,
        unsupported: driven.ir.unsupported,
        certifiedFieldIds: driven.ir.fields.map((f) => f.fieldId),
        now: '2026-01-01T00:00:00.000Z',
      });
      expect([forged, validation.valid]).toEqual([forged, false]);
      expect([
        forged,
        validation.issues
          .filter((i) => i.fieldId === field.fieldId && i.severity === 'blocking')
          .map((i) => i.code),
      ]).toEqual([forged, ['ASSERTION_NOT_SUPPORTED']]);
    }

    // ⚠️ MUTATE TOWARD SUCCESS TOO. The correct value must still be ACCEPTED,
    // or the four rows above would pass on a rail that refuses everything.
    const honest = validateTemplateTwin({
      fields: driven.ir.fields,
      mappings: driven.mappings,
      facts: driven.facts,
      resolutions: withResolution(driven, resolution.fieldId, {
        value: 'Pneumonia; No evidence of pulmonary embolism.',
      }),
      tables: driven.ir.tables,
      unsupported: driven.ir.unsupported,
      certifiedFieldIds: driven.ir.fields.map((f) => f.fieldId),
      now: '2026-01-01T00:00:00.000Z',
    });
    expect(honest.issues.filter((i) => i.severity === 'blocking')).toEqual([]);
    expect(honest.valid).toBe(true);
  });

  // ── THE WALLS THAT MUST STILL REFUSE ─────────────────────────────────────

  it('(6a) NON-VACUITY — a checkbox `explicitly_denied` + true still refuses the DOCUMENT', async () => {
    const driven = await drive({ denied: ['medication.review'] });
    const { resolution } = driven.byLabel('Medication reviewed');
    await expect(
      renderTemplateDocx({
        source: driven.source,
        ir: driven.ir,
        resolutions: withResolution(driven, resolution.fieldId, { value: true }),
        validation: driven.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
  });

  it('(6b) THE RULE-2 WALL — a dropdown `explicitly_denied` + an option still refuses', async () => {
    // The resolver can no longer produce this pair, which is exactly why the
    // renderer must still refuse it: a regression that reintroduced the
    // predecessor gate's behaviour would be caught HERE even if every resolver
    // arm above were deleted.
    const driven = await drive({ denied: ['exam.side'] });
    const { resolution } = driven.byLabel('Exam side');
    await expect(
      renderTemplateDocx({
        source: driven.source,
        ir: driven.ir,
        resolutions: withResolution(driven, resolution.fieldId, {
          status: 'explicitly_denied',
          value: 'R',
          selectedOptionOrdinal: 1,
        }),
        validation: driven.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
  });

  it('(6c) ARM A IS UNTOUCHED — `explicitly_denied` carrying NO value still refuses', async () => {
    const driven = await drive({ denied: ['allergy.substance'] });
    const { resolution } = driven.byLabel('Allergies');
    await expect(
      renderTemplateDocx({
        source: driven.source,
        ir: driven.ir,
        resolutions: withResolution(driven, resolution.fieldId, {
          value: null,
          sourceFactIds: [],
          evidenceAnchorIds: [],
        }),
        validation: driven.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
  });

  it('(6d) ARM B IS UNTOUCHED — a value under a non-populated status still refuses', async () => {
    const driven = await drive({ denied: ['allergy.substance'] });
    const { resolution } = driven.byLabel('Allergies');
    for (const status of [
      'ambiguous',
      'conflict',
      'needs_clinician_input',
      'not_mentioned',
    ] as const) {
      await expect(
        renderTemplateDocx({
          source: driven.source,
          ir: driven.ir,
          resolutions: withResolution(driven, resolution.fieldId, { status }),
          validation: driven.validation,
        }),
      ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
    }
  });

  it('(6e) THE EVIDENCE RAIL — a denial value that is NOT the contract’s derivation is BLOCKED', async () => {
    // The rail that makes rule (1) safe. `assertionSupported` re-derives the
    // denial through `denialOutcome`, so text the doctor did not dictate — even
    // text assembled from their own words — is refused.
    const driven = await drive({ denied: ['allergy.substance'] });
    const { field, resolution } = driven.byLabel('Allergies');
    for (const forged of [
      'No known drug allergies', // the ENTITY — the falsified #157's output
      'Allergies: no known drug allergies', // the UNSTRIPPED quote
      'no known drug allergies.', // one character of composition
      'No allergies', // a plausible synthesis
    ]) {
      const forgedResolutions = withResolution(driven, resolution.fieldId, {
        value: forged,
      });
      const validation = validateTemplateTwin({
        fields: driven.ir.fields,
        mappings: driven.mappings,
        facts: driven.facts,
        resolutions: forgedResolutions,
        tables: driven.ir.tables,
        unsupported: driven.ir.unsupported,
        certifiedFieldIds: driven.ir.fields.map((f) => f.fieldId),
        now: '2026-01-01T00:00:00.000Z',
      });
      expect([forged, validation.valid]).toEqual([forged, false]);
      expect([
        forged,
        validation.issues
          .filter((i) => i.fieldId === field.fieldId && i.severity === 'blocking')
          .map((i) => i.code),
      ]).toEqual([forged, ['ASSERTION_NOT_SUPPORTED']]);
    }
  });

  it('(6f) A WITHHELD DENIAL THAT DOES NOT CITE A DENIAL IS BLOCKED', async () => {
    // The status ASSERTS "this blank is a denial". A false reason in the
    // manifest is worse than no reason.
    const driven = await drive({ denied: ['exam.side'] });
    const { field, resolution } = driven.byLabel('Exam side');
    expect(resolution.status).toBe('denial_withheld');
    const affirmedFacts = driven.facts.map((fact) =>
      fact.concept === 'exam.side' ? { ...fact, polarity: 'affirmed' as const } : fact,
    );
    const validation = validateTemplateTwin({
      fields: driven.ir.fields,
      mappings: driven.mappings,
      facts: affirmedFacts,
      resolutions: driven.resolutions,
      tables: driven.ir.tables,
      unsupported: driven.ir.unsupported,
      certifiedFieldIds: driven.ir.fields.map((f) => f.fieldId),
      now: '2026-01-01T00:00:00.000Z',
    });
    expect(
      validation.issues
        .filter((i) => i.fieldId === field.fieldId && i.severity === 'blocking')
        .map((i) => i.code),
    ).toEqual(['DENIAL_WITHHELD_WITHOUT_DENIAL']);
  });

  it('(6g) THE SCHEMA REFUSES A WITHHELD DENIAL CARRYING A VALUE', () => {
    const base = {
      fieldId: `ttf_${'a'.repeat(24)}`,
      status: 'denial_withheld',
      value: null,
      sourceFactIds: [factId(1)],
      evidenceAnchorIds: ['gate157b-anchor-1'],
      selectedOptionOrdinal: null,
      reasonCode: 'denial_withheld_value_only',
      clinicianReviewed: false,
    };
    expect(FieldResolutionSchema.safeParse(base).success).toBe(true);
    expect(
      FieldResolutionSchema.safeParse({ ...base, value: 'anything' }).success,
    ).toBe(false);
    expect(
      FieldResolutionSchema.safeParse({ ...base, selectedOptionOrdinal: 1 }).success,
    ).toBe(false);
  });
});

