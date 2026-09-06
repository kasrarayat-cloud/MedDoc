// ============================================================================
// OWNER RULING #157(d) — THE DENIAL CONTRACT, FINAL, DRIVEN END TO END.
// ----------------------------------------------------------------------------
// ⚠️ THIS GATE GUARDS A DELETION. #157(d) is not a better heuristic than
// #157(c); it is the removal of the question. RULE (1), FINAL:
//
//   > A DENIED NARRATIVE FACT ALWAYS RENDERS BLANK, CARRYING ITS REASON TOKEN.
//   > NO TEXT HEURISTIC EVER DECIDES WHAT PRINTS ON A CLINICAL DOCUMENT.
//
// ⚠️ AND THE ARC IS WHY, BECAUSE A GATE THAT DOES NOT CARRY ITS OWN HISTORY
// INVITES THE NEXT READER TO REBUILD WHAT IT DELETED. One rule was formulated
// three times and each formulation was falsified BY MEASUREMENT — never by
// review, and never before the previous fix had already shipped green:
//
//   #157    print the fact VALUE     -> the value is the AFFIRMED ENTITY
//                                       ("Diabetes"), not prose.
//   #157(b) print the evidence QUOTE -> a STATED polarity bypasses the denial
//                                       vocabulary, so a `denied` fact routinely
//                                       carries a quote with no negation in it.
//   #157(c) print it when the quote  -> a COMMA defeats the clause scoping:
//           SELF-NEGATES                "No history of diabetes, hypertension is
//                                       well established." rendered under a
//                                       DENIED "Hypertension", valid=true, zero
//                                       issues. And the predicate scoped the cue
//                                       to ONE clause while the printer printed
//                                       EVERY clause, so "Denies chest pain at
//                                       rest. Chest pain on exertion, 8 out of
//                                       10." satisfied BOTH of that gate's
//                                       properties at once and reached the
//                                       document whole.
//
// Each fix was correct and each moved the failure one layer down. A
// deterministic heuristic doing SEMANTICS always has a next counterexample, so
// the fail-closed answer IS the rule.
//
// WHAT THIS GATE ASSERTS:
//   (1)    a denied narrative BLANKS — in the RENDERED word/document.xml, not
//          merely in the resolution object — across every narrative shape and
//          every `polarityBehavior`, and the sentence #157(b)/(c) printed there
//          is ABSENT from the package.
//   (1j)   #157(c)'s two measured counterexamples now blank. This is #157(d)'s
//          REAL new loss and it is pinned by the strings that defeated the
//          predicate.
//   (1k)   THE CONCEDED LOSS — fourteen realistic clinical denials, pinned as a
//          KNOWN AND DELIBERATE cost with the reason written in the arm.
//   (9)    THE NO-HEURISTIC ARM — by source inspection, the contract cannot
//          READ the doctor's words at all. Properties, not spellings.
//   (10)   C4 — no join of denial text exists anywhere, measured by varying the
//          denied facts' quotes and finding the output byte-identical.
//   (7a/b) Q2's enumerated allowlist, set-equality in BOTH directions, now
//          reconciled THREE ways and closed over the tokens the pipeline really
//          emits — the half the composed token defeated.
//   (2)-(6),(8) rule (2)'s walls, rule (3)'s no-refused-export, rule (4)'s split,
//          the D2/D3 fixes and Q3's mixed-polarity document-killer fix, all
//          STANDING and re-asserted here unchanged in intent.
//
// ⚠️ THE FIXTURE'S OWN ANTI-BLINDNESS PROPERTY IS UNCHANGED AND STILL LOAD-
// BEARING. The gate that #157(b) replaced built every fact with
// `evidenceQuote = value + " (synthetic dictation, gate 157)"`, so "prints the
// value" and "prints the quote" were the SAME observation and it was
// structurally blind to the defect that sank the ruling it guarded. Arm (pre-2)
// fails if a value is a substring of its own quote, so every ABSENCE assertion
// below is about a string that really could have appeared.
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
  DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK,
  denialOutcome,
  denialWithheldMaterialFieldIds,
  isPrintableDenial,
  MIXED_POLARITY_REASON,
  mixedPolarityNarrative,
} from '../denial-contract';
// ⚠️ THE AFFIRMED PATH'S OWN JOIN, IMPORTED SO C4 CAN BE ASSERTED AS A
// BYTE-IDENTITY RATHER THAN DESCRIBED. After #157(d) a mixed field's value must
// be exactly what this function returns for the AFFIRMED facts alone.
import {
  isListValuedNarrative,
  joinListValuedNarrative,
} from '../field-value-derivation';
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
  /**
   * ⚠️ WHAT #157(b)/(c) PRINTED HERE, KEPT AS THE THING #157(d) ASSERTS IS
   * ABSENT. It is the evidence quote minus at most the leading heading the
   * deleted strip removed, so it is the exact string a doctor could have seen
   * under a DENIED fact. Every rule-(1) row asserts BOTH this and the full
   * dictation are absent from the rendered package.
   */
  readonly suppressedText: string;
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
    suppressedText: 'no known drug allergies',
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
    suppressedText: 'The patient has no history of diabetes.',
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
    suppressedText: 'no further imaging is required.',
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
    suppressedText: 'No evidence of pulmonary embolism.',
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
    concept: 'ros.constitutional.fever',
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
    suppressedText: 'No fever or chills.',
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
  'Review of systems': { concept: 'ros.constitutional.fever', polarityBehavior: 'explicit_denial_allowed' },
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

// ── THE REASON-TOKEN COLUMNS ────────────────────────────────────────────────
// ⚠️ #157(d) C3. Every reason token `denial-contract.ts` can emit belongs to
// EXACTLY ONE of these three columns, and arm (7b) reconciles the union THREE
// ways: against the module's source, against the tokens the real pipeline
// emits, and against its own arithmetic. One list, three readers — a second
// copy would drift from the first the day either is edited.

/** Withheld, and RULED BEHAVIOUR: the blank is correct, so certification is
 *  exempt. This is the constant `denialWithheldMaterialFieldIds` reads. */
const EXEMPT_TOKENS = [
  'denial_withheld_value_only',
  'denial_withheld_affirmative_only',
  'denial_withheld_selection_asserts_presence',
  'denial_withheld_narrative_always_blank',
];

/** Withheld, and it means the FILL IS BROKEN: certification must keep blocking. */
const BLOCKING_TOKENS = [
  'denial_withheld_kind_cannot_carry_denial',
  // ⚠️ STILL AN OPEN QUESTION, NOT A SETTLED ANSWER. A repeating row asserts
  // presence by the same rule-(2) logic as the selection token, and neither
  // #157(c) nor #157(d) says whether it joins the exemption. It keeps blocking
  // because that direction costs a certificate rather than attesting a hole.
  'denial_withheld_repeating_rows_assert_presence',
];

// ⚠️ THE THIRD COLUMN IS NEW, AND ITS ABSENCE IS EXACTLY HOW THE COMPOSED TOKEN
// ESCAPED. These ride a resolution whose status is NOT `denial_withheld`, so
// `denialWithheldMaterialFieldIds` never consults them — and #157(c)'s
// two-column reconciliation therefore had no place to put
// `mixed_polarity_per_fact` at all. It scanned for `'denial_(withheld|quote)_…'`
// literals, the composed `mixed_polarity_per_fact:<sibling>` string had no
// literal anywhere AND was outside that pattern's alphabet, and a Q2 BLOCKING
// token rode a `supported` resolution straight past certification. Naming the
// column is what makes the omission visible.
const NON_WITHHELD_TOKENS = ['explicit_denial_supported', 'mixed_polarity_per_fact'];

const ALL_DENIAL_REASON_TOKENS = [
  ...EXEMPT_TOKENS,
  ...BLOCKING_TOKENS,
  ...NON_WITHHELD_TOKENS,
];

/**
 * `denial-contract.ts`'s own source, for the arms that assert PROPERTIES OF THE
 * MODULE rather than of a rendered document.
 *
 * ⚠️ `import.meta.url` IS NOT A `file:` URL UNDER THIS RUNNER — measured,
 * `fileURLToPath` throws "The URL must be of scheme file". So the path is
 * resolved from the process cwd and the resolution is ASSERTED: a guess that
 * landed on nothing would make every scan below return an empty set and every
 * arm that uses it vacuous.
 */
function denialContractSource(): string {
  const candidates = [
    'src/lib/template-twin/denial-contract.ts',
    'apps/transcribe-md/src/lib/template-twin/denial-contract.ts',
  ].map((relative) => resolve(process.cwd(), relative));
  const resolved = candidates.filter((path) => existsSync(path));
  expect(resolved).toHaveLength(1);
  return readFileSync(resolved[0]!, 'utf8');
}

/**
 * The module with COMMENTS REMOVED.
 *
 * ⚠️ THE STRIPPER IS THE WHOLE POINT OF ARM (9), because the deletion left
 * TOMBSTONE COMMENTS naming every symbol it removed — deliberately, so a future
 * reader meets the history rather than the vacuum. A raw-source scan for those
 * names would red on the tombstones; a scan that simply narrowed its pattern
 * until they vanished would be a gate tuned to its own fixture. Stripping
 * comments asks the honest question: is the SYMBOL in the CODE?
 *
 * Arm (9) positive-controls this function rather than trusting it: every token
 * it asserts absent from the code is asserted PRESENT in the raw source.
 */
function denialContractCode(): string {
  const withoutBlocks = denialContractSource().replace(/\/\*[\s\S]*?\*\//g, '');
  return withoutBlocks
    .split('\n')
    .filter((line) => !line.trimStart().startsWith('//'))
    .join('\n');
}

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

describe('#157(d) — the denial contract, FINAL, end to end', () => {
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
      // The quote is the doctor's sentence, and `suppressedText` is the SUFFIX
      // of it that #157(b)/(c) printed. Asserted here WITHOUT the deleted strip
      // — the relationship is a property of the fixture, not of a function.
      expect([narrative.label, fact.evidenceQuote]).toEqual([
        narrative.label,
        narrative.headingStripped ? narrative.deniedText : narrative.suppressedText,
      ]);
      expect(fact.evidenceQuote.endsWith(narrative.suppressedText)).toBe(true);
      expect(narrative.headingStripped).toBe(
        fact.evidenceQuote !== narrative.suppressedText,
      );
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
      expect([narrative.label, value === narrative.suppressedText]).toEqual([
        narrative.label,
        false,
      ]);
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
    // ⚠️ #192 RETURNED THIS ARM TO ITS ORIGINAL FORM, AND THAT IS THE RULING
    // WORKING. #191 briefly made this `default_kept`, on the theory that a
    // scaffold could be recognised from its content. It cannot -- the falsifying
    // case is pinned in `gate-191-kept-default-survives-render`. Under #192 a
    // kept default requires an EXPLICIT `unmentionedPolicy: 'keep'` on the
    // mapping, this fixture declares none, and so the field behaves exactly as
    // it did before the slice began. An undeclared control is unchanged by all
    // of #191/#192, which is the fail-closed property the ruling buys.
    expect(unmapped.status).toBe('not_mentioned');
    expect(unmapped.value).toBeNull();
    expect(renderedTextOf(controlById(xml, '102'))).toBe(BLANK);
  });

  // ── RULE 1 — a narrative denial is ALWAYS BLANK, carrying its token ───────

  for (const narrative of NARRATIVE) {
    it(`(1) ${narrative.label} — the denial renders BLANK and the doctor's sentence reaches no part of the package`, async () => {
      const driven = await drive({ denied: [narrative.concept] });
      const { field, resolution } = driven.byLabel(narrative.label);
      expect(field.kind).toBe('narrative_text');

      // (i) THE RESOLUTION — blank, cited, and NAMED.
      expect(resolution.status).toBe('denial_withheld');
      expect(resolution.value).toBeNull();
      expect(resolution.reasonCode).toBe(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
      // The citation SURVIVES — the manifest can still say what was denied.
      expect(resolution.sourceFactIds).toHaveLength(1);

      // (ii) ⚠️ THE RENDERED DOCUMENT, NOT THE RESOLUTION OBJECT. A status is a
      // claim about what the resolver decided; only `word/document.xml` is a
      // claim about what the doctor would sign. `(pre-4)` establishes that this
      // is what an honestly-unfilled control renders.
      const xml = await driven.render();
      const control = controlById(xml, narrative.controlId);
      expect(renderedTextOf(control)).toBe(BLANK);

      // (iii) ⚠️ AND THE #157(b)/(c) OUTPUT IS ABSENT FROM THE WHOLE PACKAGE,
      // not merely from this control. Both forms: the sentence as dictated, and
      // the suffix the deleted heading strip would have left of it.
      expect(xml).not.toContain(narrative.suppressedText);
      expect(xml).not.toContain(narrative.deniedText);

      // (iv) THE FALSIFIED #157's OUTPUT IS ABSENT TOO — the AFFIRMED ENTITY,
      // which is what "print the value" would have put in a signed note.
      expect(control).not.toContain(`<w:t>${narrative.deniedEntity}</w:t>`);

      // (v) RULE (3) IS UNTOUCHED. Nothing blocks; the document renders. A
      // denial converts a false assertion into a VISIBLE ABSENCE, never into a
      // refused export. (`render()` awaits the renderer's own independent
      // VALIDATION_REQUIRED door as well as `validation.valid`.)
      expect(
        driven.validation.issues
          .filter((i) => i.fieldId === field.fieldId && i.severity === 'blocking'),
      ).toEqual([]);
    });
  }

  it('(1b) RULE (1) HOLDS ON EVERY polarityBehavior — FOUR behaviours × five narrative shapes', async () => {
    // ⚠️ THE RULING SAYS "UNCONDITIONALLY, ON EVERY polarityBehavior", SO THE
    // GATE DRIVES EVERY ONE. `explicit_denial_allowed` is the interesting arm —
    // it is the behaviour that USED to license a print — but a rule asserted
    // only where it changed is a rule nobody is watching on the other paths.
    // ⚠️ ALL FOUR, AND THE FOURTH WAS FOUND BY THE COMPILER RATHER THAN BY
    // READING THE RULING. `Record<Behavior, string>` refused to typecheck with
    // three keys: `not_applicable` exists and nothing in this gate had ever
    // driven it. It falls to the `value_only` token — `denial-contract.ts`'s
    // `behavior !== 'explicit_denial_allowed'` arm, which is the module's ONLY
    // non-test reader of `polarityBehavior`. Recorded rather than tidied: two
    // behaviours sharing one token is a pre-existing labelling imprecision, the
    // outcome (BLANK) is identical, and inventing a fifth token here would be a
    // decision this ruling does not give.
    const TOKEN: Record<Behavior, string> = {
      value_only: 'denial_withheld_value_only',
      not_applicable: 'denial_withheld_value_only',
      affirmative_only: 'denial_withheld_affirmative_only',
      explicit_denial_allowed: DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK,
    };
    for (const behavior of [
      'value_only',
      'not_applicable',
      'affirmative_only',
      'explicit_denial_allowed',
    ] as const) {
      const driven = await drive({
        denied: NARRATIVE.map((n) => n.concept),
        behavior,
      });
      const xml = await driven.render();
      for (const narrative of NARRATIVE) {
        const key = `${behavior}/${narrative.label}`;
        const { resolution } = driven.byLabel(narrative.label);
        expect([key, resolution.status]).toEqual([key, 'denial_withheld']);
        expect([key, resolution.value]).toEqual([key, null]);
        expect([key, resolution.reasonCode]).toEqual([key, TOKEN[behavior]]);
        expect([key, renderedTextOf(controlById(xml, narrative.controlId))]).toEqual([
          key,
          BLANK,
        ]);
        expect([key, xml.includes(narrative.suppressedText)]).toEqual([key, false]);
      }
    }
  });

  it('(1g) ⚠️ THE #157(b) FALSIFICATION — a stated-polarity denial on an affirmative quote', async () => {
    // L3 states polarity as a REQUIRED enum (03-extract-entities.ts:193), is
    // INSTRUCTED that "absence of the word 'no' is not absence of a denial"
    // (:446), and a stated polarity BYPASSES the denial vocabulary entirely
    // (encounter-facts/index.ts:507). So a fact is `denied` on a sentence that
    // reads as an ASSERTION, and #157(b)'s "print the quote verbatim" printed
    // its opposite under `valid: true`.
    const facts = statedPolarityRos();
    expect(facts).toHaveLength(1);
    expect(facts[0]!.polarity).toBe('denied');
    expect(facts[0]!.concept).toBe('ros.constitutional.fever');
    // ⚠️ NON-VACUITY: the quote carries no negation the SHIPPED vocabulary can
    // see either, so this fixture is not one that was denied by its own words.
    expect(EXPLICIT_DENIAL.test(facts[0]!.evidenceQuote)).toBe(false);

    const driven = await drive({ omit: ['ros.constitutional.fever'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Review of systems');
    expect(field.kind).toBe('narrative_text');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.reasonCode).toBe(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
    expect(resolution.sourceFactIds).toHaveLength(1);

    const xml = await driven.render();
    expect(renderedTextOf(controlById(xml, '307'))).toBe(BLANK);
    expect(xml).not.toContain('Fever, chills, and night sweats.');
    expect(xml).not.toContain('<w:t>Fever</w:t>');
  });

  it("(1j) ⚠️ #157(c)'s TWO MEASURED COUNTEREXAMPLES — THIS IS #157(d)'s REAL NEW LOSS", async () => {
    // ⚠️ THESE ARE THE STRINGS THAT FALSIFIED THE SELF-NEGATION PREDICATE, AND
    // THEY ARE PINNED BY VALUE BECAUSE A PARAPHRASE WOULD NOT REPRODUCE THEM.
    // Under #157(c) each rendered into a signed clinical document with
    // `valid: true` and zero issues. Under #157(d) each is blank.
    //
    //   A · THE COMMA. The cue and the finding share one comma-joined clause,
    //       so the clause scoper found a negation "scoping" a finding it does
    //       not negate at all.
    //   B · THE CLAUSE/PRINTER MISMATCH — the worse of the two. The predicate
    //       scoped the cue to ONE clause while the printer printed EVERY
    //       clause, so this sentence satisfied BOTH of #157(c)'s gate
    //       properties at once (a subset of the doctor's quote AND containing a
    //       negation cue) and reached the document whole, asserting the very
    //       symptom the record denies.
    const CASES = [
      {
        why: 'A · the comma defeats the clause scoping',
        quote: 'No history of diabetes, hypertension is well established.',
        finding: 'Hypertension',
        // #157(c) printed the WHOLE sentence here.
        printedBy157c: 'No history of diabetes, hypertension is well established.',
      },
      {
        why: 'B · the predicate scoped one clause, the printer printed all of them',
        quote: 'Denies chest pain at rest. Chest pain on exertion, 8 out of 10.',
        finding: 'Chest pain',
        printedBy157c: 'Denies chest pain at rest. Chest pain on exertion, 8 out of 10.',
      },
    ];

    for (const row of CASES) {
      const facts = projected(row.quote, {
        ros: [
          {
            system: 'constitutional',
            // ⚠️ #179 — THE ADDRESSED SYMPTOM, NOT THE QUOTE'S SUBJECT.
            // `row.finding` documents what the sentence is about; under
            // symptom granularity the concept must name the symptom the mapped
            // field actually covers, or the fact addresses no clause at all.
            // The quote is unchanged, and the quote is what these arms test.
            finding: 'Fever',
            polarity: 'denied',
            evidence_quote: row.quote,
          },
        ],
      });
      expect([row.why, facts.length]).toEqual([row.why, 1]);
      expect([row.why, facts[0]!.polarity]).toEqual([row.why, 'denied']);

      const driven = await drive({ omit: ['ros.constitutional.fever'], extraFacts: facts });
      const { resolution } = driven.byLabel('Review of systems');
      expect([row.why, resolution.status]).toEqual([row.why, 'denial_withheld']);
      expect([row.why, resolution.value]).toEqual([row.why, null]);
      expect([row.why, resolution.reasonCode]).toEqual([
        row.why,
        DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK,
      ]);

      const xml = await driven.render();
      expect([row.why, renderedTextOf(controlById(xml, '307'))]).toEqual([row.why, BLANK]);
      expect([row.why, xml.includes(row.printedBy157c)]).toEqual([row.why, false]);
    }
  });

  it('(1k) ⚠️ THE CONCEDED LOSS — measured against #157(c), NOT against the already-blank', async () => {
    // ⚠️ THE MAGNITUDE, STATED FIRST, BECAUSE THE FIRST VERSION OF THIS ARM HID
    // IT BEHIND A ZERO DELTA.
    //
    // THE REAL COST OF RULE (1) IS ESSENTIALLY *EVERY* DENIAL CARRYING A
    // RECOGNISED NEGATION CUE — measured 20 of 20 on ordinary explicit clinical
    // denials, and 27 of 27 on an inferred-polarity corpus. Newly blank under
    // #157(d), each of which #157(c) PRINTED:
    //   "No known cardiac history." · "The patient denies any drug allergies." ·
    //   "No acute intracranial abnormality." · "Never smoker." ·
    //   "The patient is not taking warfarin." · "No murmurs, rubs or gallops." ·
    //   "Denies chest pain." · "No fever or chills." ·
    //   "Blood cultures were negative for growth."
    //
    // ⚠️ THE FOURTEEN SENTENCES BELOW ARE A ZERO-DELTA SET AND ARE KEPT ONLY AS
    // A HISTORICAL RECORD. All fourteen ALREADY blanked under #157(c) with
    // `denial_quote_not_self_negating`, so #157(d) does not newly lose them.
    // Pinning only these made the conceded cost look fourteen sentences wide
    // when it is the whole class — a cost record that understates is the same
    // defect this arc has already produced twice, one level up.
    // The ruling ordered the cost be VISIBLE; visible means its size.

    // ══ THIS ARM IS A COST RECORD, NOT A BUG REPORT. ═══════════════════════
    //
    // Every sentence below is ordinary clinical dictation that a doctor might
    // reasonably expect to see reproduced in a note. Under #157(d) none of them
    // prints. That is DELIBERATE and it is the price of rule (1): a
    // deterministic heuristic doing semantics is wrong in both directions, and
    // after three falsifications the programme chose the direction where the
    // error is a VISIBLE ABSENCE rather than a SIGNED ASSERTION of the
    // opposite.
    //
    // ⚠️ HONEST PROVENANCE, RECORDED SO THIS IS NOT READ AS MORE THAN IT IS.
    // MEASURED on this branch: all fourteen ALREADY blanked under #157(c) —
    // none carries a negation cue the self-negation vocabulary can see, so each
    // returned `denial_quote_not_self_negating`. #157(d) does not newly lose
    // them; it makes their loss UNCONDITIONAL and gives it one token. The set
    // #157(d) genuinely takes away is the set #157(c) still PRINTED, and that
    // is arms (1) and (1j). This arm exists so the standing cost is stated
    // where a future reader meets it, rather than rediscovered as a regression
    // and "fixed" by rebuilding the predicate.
    const CONCEDED = [
      { text: 'Patient is afebrile.', finding: 'Fever' },
      { text: 'Lungs are clear to auscultation bilaterally.', finding: 'Rales' },
      { text: 'Alert and oriented times three.', finding: 'Confusion' },
      { text: 'Regular rate and rhythm.', finding: 'Murmur' },
      { text: 'The abdomen is soft and nontender.', finding: 'Abdominal tenderness' },
      { text: 'D-dimer is within the reference range.', finding: 'Elevated D-dimer' },
      { text: 'The patient stopped smoking in 2010.', finding: 'Smoking' },
      { text: 'He quit drinking five years ago.', finding: 'Alcohol use' },
      { text: 'Bowel habits are unchanged.', finding: 'Change in bowel habits' },
      { text: 'Appetite and weight are stable.', finding: 'Weight loss' },
      { text: 'NKDA.', finding: 'Drug allergies' },
      { text: 'Family history non-contributory.', finding: 'Coronary artery disease' },
      { text: 'Chest pain (-).', finding: 'Chest pain' },
      { text: 'Patient declines the influenza vaccine.', finding: 'Influenza vaccine' },
    ];
    // NON-VACUITY: the list is the fourteen the ruling names, not a subset that
    // drifted.
    expect(CONCEDED).toHaveLength(14);

    for (const row of CONCEDED) {
      const facts = projected(row.text, {
        ros: [
          {
            system: 'constitutional',
            // ⚠️ #179 — THE ADDRESSED SYMPTOM, NOT THE QUOTE'S SUBJECT.
            // `row.finding` documents what the sentence is about; under
            // symptom granularity the concept must name the symptom the mapped
            // field actually covers, or the fact addresses no clause at all.
            // The quote is unchanged, and the quote is what these arms test.
            finding: 'Fever',
            polarity: 'denied',
            evidence_quote: row.text,
          },
        ],
      });
      expect([row.text, facts.length]).toEqual([row.text, 1]);
      expect([row.text, facts[0]!.polarity]).toEqual([row.text, 'denied']);

      const driven = await drive({ omit: ['ros.constitutional.fever'], extraFacts: facts });
      const { resolution } = driven.byLabel('Review of systems');
      expect([row.text, resolution.status]).toEqual([row.text, 'denial_withheld']);
      expect([row.text, resolution.reasonCode]).toEqual([
        row.text,
        DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK,
      ]);

      const xml = await driven.render();
      expect([row.text, renderedTextOf(controlById(xml, '307'))]).toEqual([row.text, BLANK]);
      expect([row.text, xml.includes(row.text)]).toEqual([row.text, false]);
    }
  });

  it('(1m) ⚠️ THE ISOLATING CONTROL FOR THE WHOLE OF RULE (1) — polarity is the ONLY difference', async () => {
    // Without this row every arm above could pass because the fixture never
    // filled that field at all. The SAME clinical slot, dictated in the
    // POSITIVE, must still print — so "blank" is a measurement about the
    // denial and not a constant about the harness.
    const affirmed = await drive();
    const xml = await affirmed.render();
    const EXPECTED: ReadonlyArray<readonly [string, string, string]> = [
      ['Allergies', '301', 'Penicillin'],
      ['Past medical history', '302', 'Diabetes'],
      ['Plan of care', '303', 'Further imaging'],
      ['Impression', '304', 'Pulmonary embolism'],
      ['Review of systems', '307', 'Fever'],
    ];
    for (const [label, controlId, value] of EXPECTED) {
      const { resolution } = affirmed.byLabel(label);
      expect([label, resolution.status]).toEqual([label, 'supported']);
      expect([label, renderedTextOf(controlById(xml, controlId))]).toEqual([label, value]);
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
    // ⚠️ THE REASON CODE, ADDED BECAUSE A MUTATION PROOF FOUND THIS ARM BEING
    // LAUNDERED BY AN OVERLAPPING GUARD. Deleting rule (2)'s selection wall
    // left this field BLANK anyway — it fell through to
    // `denial_withheld_kind_cannot_carry_denial` — so the arm's claim stayed
    // TRUE while the guard it exists to prove was gone. Its sibling (2a)
    // carried this line and RED; this one did not and stayed green. Asserting
    // WHICH rule refused is what makes the arm about rule (2).
    expect(resolution.reasonCode).toBe('denial_withheld_selection_asserts_presence');

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

    for (const behavior of [
      'value_only',
      'affirmative_only',
      'explicit_denial_allowed',
    ] as const) {
      // ⚠️ #157(d) — `denialOutcome` NO LONGER TAKES THE CITED FACTS. That is
      // rule (1) as a STRUCTURAL property: a function that cannot see the
      // dictation cannot decide anything from its text. Arm (9) asserts the
      // arity; this call site is one of the two places it shows.
      const outcome = denialOutcome(multi, {
        polarityBehavior: behavior,
      } as SemanticMapping);
      expect([behavior, outcome.status]).toEqual([behavior, 'denial_withheld']);
      expect([behavior, outcome.value]).toEqual([behavior, null]);
      // ⚠️ THE REASON CODE — ADDED BY #157(d)'s SECOND ADVERSARIAL PASS, AND IT
      // IS (2b)'s LESSON LEFT UNAPPLIED ONE ARM OVER. Without this row,
      // deleting `|| field.kind === 'multi_select'` from rule (2)'s selection
      // wall left the gate 52/52 GREEN: the multi_select simply fell through to
      // the `kind_cannot_carry_denial` arm, which is ALSO `denial_withheld` +
      // null, so both rows above stayed true while the guard they exist to
      // prove was gone. Mutation-proved: without this row 52/52, with it RED.
      // Asserting WHICH rule refused is what makes the arm about rule (2).
      //
      // ⚠️ AND THE EXPECTED TOKEN IS PER-BEHAVIOUR, WHICH IS THE SECOND HALF OF
      // THE SAME FINDING. `denialOutcome` tests the mapping's BEHAVIOUR before
      // the field's KIND, so on `value_only` and `affirmative_only` the
      // behaviour guard answers first and rule (2)'s wall is never reached —
      // those two rows are LAUNDERED BY AN OVERLAPPING GUARD (canon 62) and
      // cannot prove anything about selections. Exactly ONE of the three
      // behaviours exercises the wall, and naming that here is what stops the
      // arm reading as three times the evidence it is.
      expect([behavior, outcome.reasonCode]).toEqual([
        behavior,
        behavior === 'explicit_denial_allowed'
          ? 'denial_withheld_selection_asserts_presence'
          : `denial_withheld_${behavior}`,
      ]);
    }
    // And the RENDERER's own wall refuses a multi_select denial carrying values,
    // whoever hands it over.
    expect(isPrintableDenial(multi, ['Reflux'])).toBe(false);
  });

  it('(2g) ⚠️ RULE (2) ON THE **MIXED** PATH — a selection or a repeating row never accumulates', () => {
    // ⚠️ FOUND BY #157(d)'s SECOND ADVERSARIAL PASS. Every rule-(2) arm above —
    // (2a),(2b),(2c),(2d),(2f) — drives the ALL-DENIED path. `resolveOne`
    // reaches `mixedPolarityNarrative` for ANY field kind (the mixed branch
    // precedes the kind dispatch), and the line that carries rule (2) there had
    // NO arm at all: mutating it to `if (false)` left the gate 52/52 GREEN.
    // Claim A3 was proved for all-denied and unproved for mixed.
    const facts = projected(MIXED_TEXT, MIXED_ENTITIES);
    expect([...facts.map((f) => f.polarity)].sort()).toEqual(['affirmed', 'denied']);

    // ISOLATING CONTROL FIRST — the SAME facts on a narrative_text field DO
    // compose. So every refusal below is about the KIND, not about the fixture.
    expect(mixedPolarityNarrative(FIELD_STUB, MAPPING_STUB, facts)).toEqual({
      kind: 'text',
      text: 'Pneumonia',
      reasonCode: MIXED_POLARITY_REASON,
    });

    for (const kind of [
      'single_select',
      'multi_select',
      'checkbox',
      'number',
      'measurement',
      'date',
    ] as const) {
      const field = { ...FIELD_STUB, kind } as unknown as TemplateField;
      expect([kind, mixedPolarityNarrative(field, MAPPING_STUB, facts)]).toEqual([
        kind,
        { kind: 'refused' },
      ]);
    }
    // A repeating section expands ROWS, and a row asserts presence.
    const proto = { ...FIELD_STUB, rowPrototype: true } as unknown as TemplateField;
    expect(mixedPolarityNarrative(proto, MAPPING_STUB, facts)).toEqual({ kind: 'refused' });
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
    // ⚠️ #192 RETURNED THIS ARM TO ITS ORIGINAL FORM, AND THAT IS THE RULING
    // WORKING. #191 briefly made this `default_kept`, on the theory that a
    // scaffold could be recognised from its content. It cannot -- the falsifying
    // case is pinned in `gate-191-kept-default-survives-render`. Under #192 a
    // kept default requires an EXPLICIT `unmentionedPolicy: 'keep'` on the
    // mapping, this fixture declares none, and so the field behaves exactly as
    // it did before the slice began. An undeclared control is unchanged by all
    // of #191/#192, which is the fail-closed property the ruling buys.
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
    'not_applicable',
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
          // ⚠️ MEMBERSHIP IN THE ENUMERATED SET, NOT A PREFIX TEST. #157(c)'s
          // Q1 token was spelled without the family prefix, which forced the
          // predecessor of this row to accept two spellings — and a spelling
          // test would have accepted the composed `mixed_polarity_per_fact:…`
          // token too. Arm (7b) is what keeps this set honest.
          expect([label, ALL_DENIAL_REASON_TOKENS.includes(resolution.reasonCode)]).toEqual(
            [label, true],
          );
        }
      }
    });
  }

  it('(3b) THE MULTI-FACT HARM — two denied facts, ONE dictated sentence: BLANK, and the DOCUMENT SURVIVES', async () => {
    // ⚠️ THIS IS THE MEASURED 28-of-31 KILLED-DOCUMENTS CASE, AND RULE (3) IS
    // WHAT THIS ARM GUARDS — not rule (1). Before #157(b) the `!allDenied` guard
    // at resolver/index.ts diverted an accumulating denied narrative into
    // `multiple_distinct_supported_values` -> FIELD_CONFLICT (always blocking)
    // -> the renderer threw VALIDATION_REQUIRED and the doctor lost the WHOLE
    // DOCUMENT because of one negative sentence. Under #157(d) the field is
    // blank and the document still renders: that is the whole promise.
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
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();
    expect(resolution.reasonCode).toBe(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
    expect(resolution.sourceFactIds).toHaveLength(2); // the citation SURVIVES

    const xml = await driven.render();
    const control = controlById(xml, '302');
    expect(renderedTextOf(control)).toBe(BLANK);
    expect(xml).not.toContain(text);
    expect(control).not.toContain('<w:t>Diabetes</w:t>');
    expect(control).not.toContain('<w:t>Hypertension</w:t>');
  });

  it('(3c) TWO DISTINCT denied sentences — the SAME blank, the SAME token, and it still RENDERS', async () => {
    // ⚠️ #157(b) NEEDED A SEPARATE TOKEN HERE (`…_multiple_distinct_quotes`)
    // BECAUSE JOINING TWO SENTENCES WOULD HAVE BEEN A COMPOSITION. #157(d)
    // prints neither sentence, so there is no join to refuse and no second
    // question to answer — one blank, one reason. The token is gone from the
    // module and arm (7b)'s reconciliation is what proves it cannot come back
    // unclassified.
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
    expect(resolution.reasonCode).toBe(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
    expect(resolution.sourceFactIds).toHaveLength(2); // the citation SURVIVES

    const xml = await driven.render();
    expect(renderedTextOf(controlById(xml, '302'))).toBe(BLANK);
    expect(xml).not.toContain('No history of diabetes.');
    expect(xml).not.toContain('The patient denies hypertension.');
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

  it('(4) ALL THREE BEHAVIOURS BLANK — and rule (4) survives as three DISTINCT tokens', async () => {
    // ⚠️ WHAT #157(d) LEAVES OF RULE (4). Under #157(b)/(c) the three
    // behaviours produced three different DOCUMENTS; now they produce the same
    // blank document and three different REASONS. That distinction is still
    // load-bearing and it is not cosmetic: `denial_withheld_value_only` says
    // "this mapping refuses to carry denials", while
    // `denial_withheld_narrative_always_blank` says "this mapping accepts them
    // and the house prints none". A reader of the manifest — and the
    // certification blocker — can tell those apart.
    const expected = [
      { behavior: 'value_only', reason: 'denial_withheld_value_only' },
      { behavior: 'affirmative_only', reason: 'denial_withheld_affirmative_only' },
      {
        behavior: 'explicit_denial_allowed',
        reason: DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK,
      },
    ] as const;
    // NON-VACUITY: three DISTINCT tokens, not one token measured three times.
    expect(new Set(expected.map((r) => r.reason)).size).toBe(3);

    for (const row of expected) {
      const behavior: Behavior = row.behavior;
      const driven = await drive({ denied: ['allergy.substance'], behavior });
      const { resolution } = driven.byLabel('Allergies');
      expect([behavior, resolution.status]).toEqual([behavior, 'denial_withheld']);
      expect([behavior, resolution.value]).toEqual([behavior, null]);
      expect([behavior, resolution.reasonCode]).toEqual([behavior, row.reason]);
      // The citation is retained under EVERY behaviour — a withheld denial that
      // discarded its facts would make the manifest unable to say why.
      expect([behavior, resolution.sourceFactIds.length]).toEqual([behavior, 1]);

      const xml = await driven.render();
      expect([behavior, renderedTextOf(controlById(xml, '301'))]).toEqual([behavior, BLANK]);
      expect([behavior, xml.includes('no known drug allergies')]).toEqual([
        behavior,
        false,
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
    // ⚠️ REWRITTEN AGAIN FOR #157(d), AND THE FIXTURE CHANGE IS THE POINT —
    // TWICE OVER. #157(c) Q2 moved this arm off a `value_only` denial because
    // that token became EXEMPT. #157(d) moves it again: its replacement,
    // `denial_withheld_multiple_distinct_quotes`, no longer exists — there is
    // no join to refuse when nothing prints. So the blocker is now proved on
    // the two tokens that ACTUALLY survive as blocking, each DRIVEN through the
    // real pipeline rather than patched into a resolution.
    const BLOCKERS = [
      {
        why: 'a repeating section — a row asserts presence (rule (2))',
        denied: ROW_CONCEPT,
        label: 'Repeat finding',
        reason: 'denial_withheld_repeating_rows_assert_presence',
      },
      {
        why: 'a date cannot carry a denial — printing one asserts a procedure happened',
        denied: 'procedure.date',
        label: 'Encounter date',
        reason: 'denial_withheld_kind_cannot_carry_denial',
      },
    ];
    // NON-VACUITY: two DISTINCT tokens, and both are outside the exemption.
    expect(new Set(BLOCKERS.map((b) => b.reason)).size).toBe(2);

    for (const row of BLOCKERS) {
      const driven = await drive({ denied: [row.denied] });
      const { field, resolution } = driven.byLabel(row.label);
      expect([row.why, resolution.status]).toEqual([row.why, 'denial_withheld']);
      expect([row.why, resolution.reasonCode]).toEqual([row.why, row.reason]);
      expect([
        row.why,
        CERTIFICATION_EXEMPT_DENIAL_REASONS.has(resolution.reasonCode),
      ]).toEqual([row.why, false]);
      expect([row.why, field.clinicallyMaterial || field.criticality !== 'routine']).toEqual(
        [row.why, true],
      );

      // The certification gate reads THIS, and it is non-empty.
      const blocked = denialWithheldMaterialFieldIds(driven.ir.fields, driven.resolutions);
      expect([row.why, blocked.includes(field.fieldId)]).toEqual([row.why, true]);

      // ⚠️ AND THE POINT OF THE SEPARATE STATUS: certification's own relaxation
      // does NOT reach it. `allowUncertifiedForSyntheticTest` downgrades
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
      expect([row.why, relaxed.valid]).toEqual([row.why, true]); // the DOCUMENT is fine
      expect([
        row.why,
        denialWithheldMaterialFieldIds(driven.ir.fields, driven.resolutions),
      ]).toEqual([row.why, blocked]); // the CERTIFICATE is not
    }

    // NON-VACUITY for the predicate itself: with nothing denied it returns
    // nothing, so a non-empty result above is a measurement rather than a
    // constant.
    const affirmed = await drive();
    expect(denialWithheldMaterialFieldIds(affirmed.ir.fields, affirmed.resolutions)).toEqual(
      [],
    );
    // ⚠️ AND THE COMPANION NON-VACUITY THAT #157(d) MAKES NECESSARY: a
    // NARRATIVE denial — the shape rule (1) blanks — must NOT block, or the
    // ruling would have made every `explicit_denial_allowed` narrative
    // uncertifiable, which is exactly the Q2 defect being fixed one ruling
    // later.
    const narrative = await drive({ denied: ['allergy.substance'] });
    const { field: allergies, resolution: allergyResolution } =
      narrative.byLabel('Allergies');
    expect(allergyResolution.reasonCode).toBe(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
    expect(allergies.clinicallyMaterial || allergies.criticality !== 'routine').toBe(true);
    expect(
      denialWithheldMaterialFieldIds(narrative.ir.fields, narrative.resolutions),
    ).toEqual([]);
  });

  // ══ OWNER RULING #157(c) Q2 — THE CERTIFICATION BLOCKER EXEMPTS AN
  // ENUMERATED ALLOWLIST, NEVER A BLANKET ═════════════════════════════════

  it('(7a) ⚠️ SET EQUALITY, BOTH DIRECTIONS — the exemption IS the ruled-behaviour list', async () => {
    // ⚠️ THE TWO SIDES COME FROM DIFFERENT PLACES, WHICH IS THE ONLY THING THAT
    // MAKES THIS A GATE RATHER THAN A TAUTOLOGY. One side is the CONSTANT the
    // blocker reads. The other is derived by DRIVING the real pipeline for
    // every behaviour the ruling approves and collecting the reason token the
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
    // ⚠️ #157(d) RULE (1): the narrative blank, which REPLACES #157(c)'s Q1
    // token in this set. It has to be exempt for the same reason `value_only`
    // is — a template blanking exactly as the ruling orders must not be
    // unable to certify for it.
    {
      const driven = await drive({ denied: ['allergy.substance'] });
      const { resolution } = driven.byLabel('Allergies');
      expect(resolution.status).toBe('denial_withheld');
      expect(resolution.reasonCode).toBe(DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK);
      emitted.add(resolution.reasonCode);
    }

    expect([...emitted].sort()).toEqual([...CERTIFICATION_EXEMPT_DENIAL_REASONS].sort());
    // NON-VACUITY: four distinct tokens, not one token measured four times.
    expect(emitted.size).toBe(4);
    // And the module-scope column the other arms reconcile against is the SAME
    // set — so (7b)'s arithmetic and this driven measurement cannot diverge.
    expect([...EXEMPT_TOKENS].sort()).toEqual([...CERTIFICATION_EXEMPT_DENIAL_REASONS].sort());
  });

  it('(7b) ⚠️ EVERY reason token RECONCILES THREE WAYS — source, pipeline, arithmetic', async () => {
    // ⚠️ #157(d) C3 — THIS ARM IS REBUILT BECAUSE ITS PREDECESSOR WAS
    // STRUCTURALLY BLIND, AND THE BLINDNESS WAS MEASURED, NOT SUSPECTED.
    //
    // It scanned the module for `'denial_(withheld|quote)_…'` LITERALS and
    // reconciled them against two columns. The per-fact mixed path built its
    // token by CONCATENATION —
    //
    //     `${MIXED_POLARITY_REASON}:${withheldReasonCodes.join(',')}`
    //
    // — so `mixed_polarity_per_fact:denial_withheld_quote_not_dictated` (a Q2
    // BLOCKING token, driven live on this branch) appeared as a literal NOWHERE
    // and sat outside the scanner's alphabet entirely. It rode a `supported`
    // resolution, which `denialWithheldMaterialFieldIds` never inspects, and
    // went past certification with nothing to catch it.
    //
    // So the reconciliation now closes over the REAL emitted set, three ways:
    //
    //   1 · SOURCE     — every token literal in the module, comments included,
    //                    minus two named non-reason literals.
    //   2 · PIPELINE   — every token the real resolver actually emits, which is
    //                    the half a source scan can never see.
    //   3 · ARITHMETIC — the columns partition the union with nothing left over.
    const source = denialContractSource();

    // ── 1 · SOURCE ────────────────────────────────────────────────────────
    // ⚠️ THE ALPHABET IS WIDER THAN THE PREDECESSOR'S ON PURPOSE: it admits
    // `mixed_polarity_*` and `explicit_denial_*`, which is precisely the family
    // the old pattern could not express.
    const scanned = new Set(
      [
        ...source.matchAll(
          /'((?:denial|explicit_denial|mixed_polarity)_[a-z_]+)'/g,
        ),
      ].map((m) => m[1]!),
    );
    // POSITIVE CONTROL for the scanner: a pattern that finds nothing is
    // indistinguishable from a module with no tokens.
    expect(scanned.size).toBeGreaterThan(0);

    // ⚠️ TWO LITERALS IN THAT MODULE MATCH THE TOKEN SHAPE AND ARE NOT REASON
    // CODES. They are excluded BY NAME and each exclusion is asserted
    // NON-VACUOUS — never by narrowing the pattern until they disappear, which
    // is how a gate ends up excluding the next real token too.
    const NOT_A_REASON_CODE = [
      'denial_withheld', // the resolution STATUS
      'explicit_denial_allowed', // a polarityBehavior
    ];
    for (const literal of NOT_A_REASON_CODE) {
      expect([literal, scanned.has(literal)]).toEqual([literal, true]);
    }
    const fromSource = [...scanned]
      .filter((token) => !NOT_A_REASON_CODE.includes(token))
      .sort();
    expect(fromSource).toEqual([...ALL_DENIAL_REASON_TOKENS].sort());

    // ── 2 · PIPELINE ──────────────────────────────────────────────────────
    // Every reachable denial-shaped outcome, DRIVEN, and its token collected.
    const fromPipeline = new Set<string>();
    const collect = (driven: Driven) => {
      for (const resolution of driven.resolutions) {
        if (
          resolution.status === 'denial_withheld' ||
          resolution.status === 'explicitly_denied' ||
          resolution.reasonCode.startsWith('mixed_polarity')
        ) {
          fromPipeline.add(resolution.reasonCode);
          // ⚠️ AND THE PROPERTY THE COMPOSED TOKEN VIOLATED, ASSERTED ON EVERY
          // EMISSION RATHER THAN ON A SAMPLE: no reason code is COMPOSED. A
          // colon is the exact character the old concatenation used, and no
          // enumerated token contains one.
          expect([resolution.reasonCode, resolution.reasonCode.includes(':')]).toEqual([
            resolution.reasonCode,
            false,
          ]);
          expect([
            resolution.reasonCode,
            ALL_DENIAL_REASON_TOKENS.includes(resolution.reasonCode),
          ]).toEqual([resolution.reasonCode, true]);
        }
      }
    };
    collect(await drive({ denied: ALL_CONCEPTS }));
    collect(await drive({ denied: ALL_CONCEPTS, behavior: 'value_only' }));
    collect(await drive({ denied: ALL_CONCEPTS, behavior: 'affirmative_only' }));
    collect(
      await drive({ omit: ['assessment'], extraFacts: projected(MIXED_TEXT, MIXED_ENTITIES) }),
    );
    // SET EQUALITY, and it is the half the predecessor could not do: the
    // pipeline reaches EVERY enumerated token and emits NOTHING else.
    expect([...fromPipeline].sort()).toEqual([...ALL_DENIAL_REASON_TOKENS].sort());

    // ── 3 · ARITHMETIC ────────────────────────────────────────────────────
    expect(new Set(ALL_DENIAL_REASON_TOKENS).size).toBe(ALL_DENIAL_REASON_TOKENS.length);
    expect(
      EXEMPT_TOKENS.length + BLOCKING_TOKENS.length + NON_WITHHELD_TOKENS.length,
    ).toBe(ALL_DENIAL_REASON_TOKENS.length);
    expect(fromSource.length).toBe(ALL_DENIAL_REASON_TOKENS.length);
    expect(fromPipeline.size).toBe(ALL_DENIAL_REASON_TOKENS.length);

    // ── AND EACH COLUMN BEHAVES AS ITS NAME CLAIMS, through the real predicate
    //    on a real clinically material field.
    const driven = await drive({ denied: ['allergy.substance'], behavior: 'value_only' });
    const { field } = driven.byLabel('Allergies');
    expect(field.clinicallyMaterial || field.criticality !== 'routine').toBe(true);
    for (const reasonCode of [...EXEMPT_TOKENS, ...BLOCKING_TOKENS]) {
      const patched = withResolution(driven, field.fieldId, { reasonCode });
      const blocked = denialWithheldMaterialFieldIds(driven.ir.fields, patched);
      expect([reasonCode, blocked.includes(field.fieldId)]).toEqual([
        reasonCode,
        !EXEMPT_TOKENS.includes(reasonCode),
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

  it('(8a) ⚠️ THE DOCUMENT-KILLER DIES — one affirmed + one denied fact still RENDER', async () => {
    // ⚠️ Q3 STANDS, AND THIS IS THE ARM THAT SAYS SO. Before it: status=conflict,
    // reason=polarity_conflict, valid=false, blocking=[FIELD_CONFLICT],
    // renderTemplateDocx REJECTED. One affirmed fact plus one denied fact in one
    // narrative field and the doctor lost the WHOLE document. `past_medical_history`,
    // `family_history`, `allergy` and `medication` are all accumulating
    // list-valued narratives in production, and the owner's own ROS is
    // mixed-polarity by construction — this is a critical path, not an edge.
    //
    // ⚠️ WHAT #157(d) CHANGES HERE: the affirmed half prints by the NORMAL path
    // and the denied half now contributes NOTHING. #157(c) rendered
    // "Pneumonia; No evidence of pulmonary embolism." — two registers in one
    // section. It renders "Pneumonia".
    const facts = projected(MIXED_TEXT, MIXED_ENTITIES);
    expect(facts.map((f) => f.polarity)).toEqual(['affirmed', 'denied']);
    expect(facts.map((f) => f.value)).toEqual(['Pneumonia', 'Pulmonary embolism']);

    const driven = await drive({ omit: ['assessment'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Impression');
    expect(field.kind).toBe('narrative_text');
    expect(resolution.status).toBe('supported');
    expect(resolution.reasonCode).toBe(MIXED_POLARITY_REASON);
    // ⚠️ C3 — THE BARE BASE TOKEN, NOT A COMPOSITION. Under #157(c) this was
    // `mixed_polarity_per_fact:<sibling token>`, built by concatenation.
    expect(resolution.reasonCode).toBe('mixed_polarity_per_fact');
    expect(resolution.reasonCode).not.toContain(':');
    // The citation SURVIVES — both facts, so the manifest can still say what
    // was denied even though the denial printed nothing.
    expect(resolution.sourceFactIds).toHaveLength(2);
    expect(driven.validation.issues.filter((i) => i.severity === 'blocking')).toEqual([]);

    // THE EXACT RENDERED TEXT, out of a really-rendered word/document.xml.
    const xml = await driven.render();
    const printed = renderedTextOf(controlById(xml, '304'));
    expect(printed).toBe('Pneumonia');

    // ⚠️ C4, ASSERTED AS BYTE-IDENTITY AGAINST THE AFFIRMED PATH'S OWN
    // FUNCTION. This is stronger than the per-segment property #157(c) needed:
    // the value is not merely "composed carefully", it is EXACTLY what the
    // affirmed facts alone would have produced with no denial in the picture.
    const mapping = driven.mappings.find((m) => m.fieldId === field.fieldId)!;
    const affirmedOnly = facts.filter((f) => f.polarity === 'affirmed');
    expect(printed).toBe(joinListValuedNarrative(field, mapping, affirmedOnly));

    // AND THE DENIED FACT'S SENTENCE REACHES NO PART OF THE PACKAGE.
    expect(xml).not.toContain('No evidence of pulmonary embolism.');
    expect(xml).not.toContain('<w:t>Pulmonary embolism</w:t>');
  });

  it('(8b) DICTATION ORDER IS PRESERVED — proved by a reversal control', async () => {
    // Reading the code cannot prove an ordering. Reversing the INPUT and
    // measuring the OUTPUT can, and it is the only thing that distinguishes
    // "kept the order" from "happened to sort that way".
    //
    // ⚠️ TWO AFFIRMED FACTS, NOT ONE, BECAUSE #157(d) REMOVED THE DENIED
    // SEGMENT. #157(c)'s version reversed one affirmed and one denied fact, so
    // the ordering was visible in the output. With the denial contributing
    // nothing, a one-affirmed fixture renders the same string in both
    // directions and the arm would be VACUOUS — it would pass for an
    // implementation that sorted its segments alphabetically.
    const forwardFacts = projected(
      'History of diabetes. The patient reports hypertension. No evidence of pulmonary embolism.',
      {
        past_medical_history: [
          { condition: 'Diabetes', evidence_quote: 'History of diabetes.' },
          {
            condition: 'Hypertension',
            evidence_quote: 'The patient reports hypertension.',
          },
          {
            condition: 'Pulmonary embolism',
            evidence_quote: 'No evidence of pulmonary embolism.',
          },
        ],
      },
    );
    expect(forwardFacts.map((f) => f.polarity)).toEqual([
      'affirmed',
      'affirmed',
      'denied',
    ]);
    const forward = await drive({
      omit: ['past_medical_history'],
      extraFacts: forwardFacts,
    });
    expect(forward.byLabel('Past medical history').resolution.reasonCode).toBe(
      MIXED_POLARITY_REASON,
    );
    expect(renderedTextOf(controlById(await forward.render(), '302'))).toBe(
      'Diabetes; Hypertension',
    );

    // ⚠️ THE REVERSAL: the two AFFIRMED entities swap places in the dictation.
    // A sorted implementation renders "Diabetes; Hypertension" both times.
    const reversedFacts = projected(
      'The patient reports hypertension. History of diabetes. No evidence of pulmonary embolism.',
      {
        past_medical_history: [
          {
            condition: 'Hypertension',
            evidence_quote: 'The patient reports hypertension.',
          },
          { condition: 'Diabetes', evidence_quote: 'History of diabetes.' },
          {
            condition: 'Pulmonary embolism',
            evidence_quote: 'No evidence of pulmonary embolism.',
          },
        ],
      },
    );
    expect(reversedFacts.map((f) => f.polarity)).toEqual([
      'affirmed',
      'affirmed',
      'denied',
    ]);
    const reversed = await drive({
      omit: ['past_medical_history'],
      extraFacts: reversedFacts,
    });
    expect(renderedTextOf(controlById(await reversed.render(), '302'))).toBe(
      'Hypertension; Diabetes',
    );
  });

  it('(8c) ⚠️ C4 — A DENIAL IN A MIXED FIELD CONTRIBUTES NOTHING, AND ITS TEXT CANNOT REACH THE VALUE', async () => {
    // ⚠️ THE OWNER'S OWN ROS IS MIXED-POLARITY, AND ROS IS THE ONE ENTITY TYPE
    // THAT STATES POLARITY — so this is the exact shape rule (1) and Q3 meet in.
    const build = (deniedQuote: string) =>
      projected(`Fatigue and malaise. ${deniedQuote}`, {
        ros: [
          {
            system: 'constitutional',
            // ⚠️ #179 — 'Fatigue' and 'Fever' are now DIFFERENT concepts and
            // could never reach one field together. A mixed field is the same
            // symptom asserted both ways, which is what this arm means by
            // mixed; the quotes still differ and still carry the contrast.
            finding: 'Fever',
            polarity: 'affirmed',
            evidence_quote: 'Fatigue and malaise.',
          },
          {
            system: 'constitutional',
            finding: 'Fever',
            polarity: 'denied',
            evidence_quote: deniedQuote,
          },
        ],
      });

    const facts = build('Fever, chills, and night sweats.');
    expect(facts.map((f) => f.polarity)).toEqual(['affirmed', 'denied']);

    const driven = await drive({ omit: ['ros.constitutional.fever'], extraFacts: facts });
    const { field, resolution } = driven.byLabel('Review of systems');
    expect(resolution.status).toBe('supported');
    // THE AFFIRMED HALF PRINTS; THE DENIAL CONTRIBUTES ONLY ITS REASON TOKEN.
    expect(resolution.value).toBe('Fever');
    expect(resolution.reasonCode).toBe(MIXED_POLARITY_REASON);
    expect(resolution.reasonCode).not.toContain(':');
    expect(resolution.sourceFactIds).toHaveLength(2); // the citation SURVIVES

    // ⚠️ THE MANIFEST IS NOT SILENT, AND THE WARNING WAS RE-KEYED IN THE SAME
    // COMMIT THAT STOPPED COMPOSING THE TOKEN. It used to fire on
    // `reasonCode.startsWith('mixed_polarity_per_fact:')` — the composed form's
    // ONLY consumer — so emitting the bare base token without re-keying would
    // have made it SILENTLY DEAD while the code still read as though the
    // silence rule held. The context it used to carry inside the identifier now
    // comes from the CITED FACTS.
    const mine = driven.validation.issues.filter((i) => i.fieldId === field.fieldId);
    expect(mine.map((i) => i.code)).toEqual(['FIELD_MIXED_POLARITY_DENIAL_WITHHELD']);
    expect(mine[0]!.severity).toBe('warning');
    expect(mine[0]!.message).toContain('1 denied fact');
    expect(mine[0]!.message).toContain(MIXED_POLARITY_REASON);

    const xml = await driven.render();
    expect(renderedTextOf(controlById(xml, '307'))).toBe('Fever');
    // ⚠️ THE QUOTE IS NOW THE ONLY DISCRIMINATOR, AND THE REASON IS #179.
    // This arm used to assert BOTH that the denied fact's QUOTE stayed out AND
    // that its VALUE ('Fever') stayed out, while the affirmed value was
    // 'Fatigue'. Under symptom granularity the two facts must share a concept
    // to reach one field, and `value` IS the symptom token — so a mixed field's
    // affirmed and denied values are IDENTICAL by construction. The old
    // `not.toContain('<w:t>Fever</w:t>')` would now be asserting that the
    // AFFIRMED value is absent, i.e. it would fail for the right output, and
    // keeping it in any weakened form would test nothing.
    //
    // ⚠️ RECORDED AS A REAL LOSS OF DISCRIMINATION, not silently dropped: the
    // value-leak channel is no longer observable on a mixed ROS field. What
    // remains observable — and is what the denial contract actually promises —
    // is that the DENIED SENTENCE reaches no part of the package.
    expect(xml).not.toContain('Fever, chills, and night sweats.');
    // and a token that occurs ONLY in the denied sentence, so this cannot pass
    // by the affirmed quote happening to look similar
    expect(xml).not.toContain('night sweats');
    expect(xml).not.toContain('chills');

    // ══ C4, MEASURED RATHER THAN ARGUED. ═══════════════════════════════════
    // ⚠️ "NO JOIN OF DENIAL TEXT EXISTS" IS A CLAIM ABOUT WHAT THE OUTPUT
    // DEPENDS ON, so the honest measurement VARIES THE DENIED TEXT and finds
    // the output byte-identical. A source reading cannot establish this; three
    // wildly different denied quotes producing one identical value can.
    //
    // Each variant below is a sentence #157(b) or #157(c) WOULD have printed —
    // the first self-negates in-vocabulary, the second carries an
    // out-of-vocabulary negating heading, the third is the comma counterexample
    // — so this is not three fixtures the old code would have blanked anyway.
    const VARIANTS = [
      'No fever or chills.',
      'Absent: fever, chills, or night sweats.',
      'No history of diabetes, fever is well established.',
    ];
    const values = new Set<string>();
    for (const quote of VARIANTS) {
      const run = await drive({
        omit: ['ros.constitutional.fever'],
        extraFacts: build(quote),
      });
      const mixed = run.byLabel('Review of systems').resolution;
      expect([quote, mixed.status]).toEqual([quote, 'supported']);
      expect([quote, mixed.reasonCode]).toEqual([quote, MIXED_POLARITY_REASON]);
      values.add(String(mixed.value));
      const runXml = await run.render();
      expect([quote, renderedTextOf(controlById(runXml, '307'))]).toEqual([quote, 'Fever']);
      // NOT ONE CHARACTER OF THE DENIED SENTENCE REACHES THE PACKAGE.
      expect([quote, runXml.includes(quote)]).toEqual([quote, false]);
    }
    // ⚠️ ONE distinct value across three wildly different denied sentences.
    expect([...values]).toEqual(['Fever']);
    // NON-VACUITY for the variation itself: the three quotes really are
    // different, so "the output did not move" is a measurement.
    expect(new Set(VARIANTS).size).toBe(3);
  });

  it('(8d) THE NEVER-BETTER-THAN-AFFIRMED-ALONE INVARIANT — a refusal leaves the field where it was', async () => {
    // Two DISTINCT affirmed values on a narrative that is not an accumulating
    // SECTION are a genuine conflict, and adding a denial must not launder them
    // into a rendered field. `ros.*` is deliberately absent from
    // `ACCUMULATING_NARRATIVE_CONCEPTS`, so this is the live shape.
    const ros = (
      rows: ReadonlyArray<{ system?: string; finding: string; polarity: string; quote: string }>,
    ) =>
      projected(rows.map((r) => r.quote).join(' '), {
        ros: rows.map((r) => ({
          system: r.system ?? 'constitutional',
          finding: r.finding,
          polarity: r.polarity,
          evidence_quote: r.quote,
        })),
      });

    // ⚠️ THE ORIGINAL BASELINE OF THIS ARM IS UNREACHABLE AFTER #179, AND THAT
    // IS THE RULING WORKING RATHER THAN A FIXTURE ROTTING.
    //
    // It used to affirm TWO symptoms and rely on both landing on ONE field as
    // `multiple_distinct_supported_values` — the very conflict #179 was written
    // to end ("a second affirmed finding conflicted the export"). Under symptom
    // granularity each symptom carries its own concept and addresses its own
    // clause, so two affirmed symptoms can no longer collide on one field. And
    // because `value` IS the symptom token, two facts sharing a concept share a
    // value, so that conflict is now unreachable for ROS BY CONSTRUCTION.
    //
    // The arm is therefore rebuilt rather than deleted: the invariant it exists
    // for — a refusal never leaves a field BETTER than it was — is unchanged and
    // still measurable, and the retired baseline is asserted positively below so
    // nobody re-derives it. `headache` is HEENT, not constitutional; the old
    // fixture filed it under constitutional, which the closed lexicon refuses.
    const AFFIRMED_TWO = [
      { finding: 'fatigue', polarity: 'affirmed', quote: 'Fatigue and malaise.' },
      { system: 'heent', finding: 'headache', polarity: 'affirmed', quote: 'Headache since Tuesday.' },
    ];
    const DENIED_ONE = {
      finding: 'Fever',
      polarity: 'denied',
      quote: 'No fever or chills.',
    };

    // WITH the denial -> the mixed contract REFUSES and the field is exactly
    // the conflict it already was.
    const mixed = await drive({
      omit: ['ros.constitutional.fever'],
      extraFacts: ros([...AFFIRMED_TWO, DENIED_ONE]),
    });
    const withDenial = mixed.byLabel('Review of systems').resolution;
    expect(withDenial.status).toBe('denial_withheld');
    // ⚠️ AND THE FIELD RENDERS NOTHING — which is the half that matters. The
    // status token could be renamed; a value reaching a doctor could not.
    expect(withDenial.value).toBeNull();


    // ⚠️ THE ISOLATING CONTROL, AND IT IS THE WHOLE ARM. Without the denial the
    // SAME two affirmed facts conflict too — so the mixed path took nothing
    // away. A refusal that merely looked correct would pass the row above.
    const affirmedOnly = await drive({
      omit: ['ros.constitutional.fever'],
      extraFacts: ros(AFFIRMED_TWO),
    });
    const noDenial = affirmedOnly.byLabel('Review of systems').resolution;
    expect(noDenial.status).toBe('not_mentioned');
    expect(noDenial.value).toBeNull();

    // ⚠️ THE INVARIANT, STATED AS THE COMPARISON IT ACTUALLY IS. Adding the
    // denial did not IMPROVE the field: it was blank without the denial and it
    // is blank with it. Neither run reaches `supported`, and neither prints.
    expect([withDenial.value, noDenial.value]).toEqual([null, null]);
    expect(withDenial.status).not.toBe('supported');

    // ⚠️ THE RETIRED BASELINE, ASSERTED POSITIVELY SO IT CANNOT BE REBUILT BY
    // ACCIDENT. Two affirmed symptoms now carry DIFFERENT concepts, which is
    // exactly why they can no longer collide on one field.
    const twoAffirmed = ros(AFFIRMED_TWO);
    const concepts = twoAffirmed.map((f) => String(f.concept));
    expect(new Set(concepts).size, 'two symptoms collapsed onto one concept').toBe(2);
    expect(concepts).toEqual(['ros.constitutional.fatigue', 'ros.heent.headache']);

    // ⚠️ NEITHER RUN BLOCKS ANY MORE, AND THAT IS #157(d) ARRIVING RATHER THAN
    // A GUARD BEING LOOSENED. This used to assert FIELD_CONFLICT in BOTH runs,
    // which is precisely the document-killer #157(d) exists to end: the field
    // conflicted, the conflict was blocking, and `renderTemplateDocx` rejected —
    // so one negative sentence cost the doctor the WHOLE document.
    //
    // With #179 the two affirmed symptoms address their own clauses instead of
    // colliding here, and the denial renders the field BLANK. Blank and
    // non-blocking is the promised end state. The invariant is unchanged — the
    // denial still never leaves the field better than affirmed-alone — but the
    // floor both runs sit on has risen from "blocked" to "blank".
    for (const run of [mixed, affirmedOnly]) {
      const { field } = run.byLabel('Review of systems');
      expect(
        run.validation.issues
          .filter((i) => i.fieldId === field.fieldId && i.severity === 'blocking')
          .map((i) => i.code),
      ).toEqual([]);
    }
    // ⚠️ AND THE DOCUMENT MUST ACTUALLY RENDER — the half that matters to a
    // doctor, and the half a status-only assertion cannot see.
    for (const run of [mixed, affirmedOnly]) {
      await expect(run.render()).resolves.toBeTruthy();
    }
  });

  it('(8h) ⚠️ THE NEVER-BETTER-THAN-AFFIRMED-ALONE TEST USES THE AFFIRMED PATH\'S OWN BASIS', () => {
    // ⚠️ FOUND BY #157(d)'s SECOND ADVERSARIAL PASS, AND (8d) COULD NOT SEE IT.
    // (8d) uses two findings that are genuinely different words, so trimming
    // cannot collapse them. The guard counted TRIMMED, DEDUPED segments while
    // the resolver decides the same question on the RAW converted value — so
    // two affirmed facts differing only in WHITESPACE collapsed to one segment
    // here and stayed two distinct values there, and adding a DENIAL made the
    // field RENDER where the affirmed facts alone are BLOCKED. That is "better
    // than affirmed alone", the one direction this module forbids by name.
    const base = projected(MIXED_TEXT, MIXED_ENTITIES);
    const affirmed = base.find((f) => f.polarity === 'affirmed')!;
    const denied = base.find((f) => f.polarity === 'denied')!;

    // The concept must NOT be an accumulating section, or the guard is skipped
    // and this arm measures nothing. Asserted, never assumed.
    const nonAccumulating = {
      clinicalConcept: 'exam.vascular',
      polarityBehavior: 'explicit_denial_allowed',
    } as unknown as SemanticMapping;
    expect(isListValuedNarrative(FIELD_STUB, nonAccumulating)).toBe(false);

    const twin = {
      ...affirmed,
      factId: `${affirmed.factId}b`,
      value: `${String(affirmed.value)} `,
    } as EncounterFact;
    // TWO DISTINCT RAW VALUES that TRIM TO ONE — the exact shape the old guard
    // could not see. Both halves asserted, so the fixture cannot rot silently.
    expect(twin.value).not.toBe(affirmed.value);
    expect(String(twin.value).trim()).toBe(String(affirmed.value).trim());

    expect(mixedPolarityNarrative(FIELD_STUB, nonAccumulating, [affirmed, twin, denied])).toEqual({
      kind: 'refused',
    });

    // ISOLATING CONTROL — the SAME field and mapping with ONE affirmed value
    // composes. So the refusal above is about the second value, not the mapping.
    expect(
      mixedPolarityNarrative(FIELD_STUB, nonAccumulating, [affirmed, denied]),
    ).toEqual({ kind: 'text', text: 'Pneumonia', reasonCode: MIXED_POLARITY_REASON });
  });

  it('(8i) ⚠️ C4 AS A PROPERTY OVER MANY FIXTURES, NOT AS ONE — mixed text IS the affirmed join', () => {
    // ⚠️ FOUND BY #157(d)'s SECOND ADVERSARIAL PASS. `mixedPolarityNarrative`
    // RE-IMPLEMENTS `joinListValuedNarrative` — same laterality guard, same
    // derive-null refusal, same trim, same dedupe — and A6 was asserted at
    // exactly ONE place, arm (8a), on ONE fixture with ONE affirmed fact.
    // Measured: deleting the derive-null refusal, deleting the dedupe, or
    // deleting the laterality guard each left the gate 52/52 GREEN.
    //
    // So the claim is asserted as a PROPERTY here — for every fixture, the
    // mixed value is EXACTLY what the affirmed path's own function returns for
    // the affirmed facts alone, with `refused` <-> `null`. One row per guard,
    // and the guards cannot be deleted independently of it.
    const base = projected(MIXED_TEXT, MIXED_ENTITIES);
    const affirmed = base.find((f) => f.polarity === 'affirmed')!;
    const denied = base.find((f) => f.polarity === 'denied')!;
    const clone = (over: Partial<EncounterFact>, tag: string) =>
      ({ ...affirmed, factId: `${affirmed.factId}${tag}`, ...over }) as EncounterFact;

    // MAPPING_STUB's concept is `assessment`, an ACCUMULATING section — which is
    // precisely when the affirmed path uses `joinListValuedNarrative` at all.
    expect(isListValuedNarrative(FIELD_STUB, MAPPING_STUB)).toBe(true);

    const CASES: ReadonlyArray<readonly [string, readonly EncounterFact[]]> = [
      ['one affirmed', [affirmed, denied]],
      ['two distinct affirmed', [affirmed, clone({ value: 'Effusion' }, 'x'), denied]],
      // DEDUPE — two affirmed facts deriving the same text must render once.
      ['duplicate affirmed', [affirmed, clone({}, 'd'), denied]],
      // TRIM — a trailing space must not survive into the joined section.
      ['whitespace affirmed', [affirmed, clone({ value: 'Effusion ' }, 'w'), denied]],
      // ⚠️ DERIVE-NULL — AN AFFIRMED FACT THAT DOES NOT DERIVE. Added because
      // my own first version of this arm did NOT catch the mutation that
      // replaced the refusal with `continue`: no fixture had a non-deriving
      // fact, so the property held vacuously on that guard. `EncounterFact`
      // values are `string | number | boolean` (`ir.ts:376`) and
      // `deriveFieldValueFromFact` returns null for a non-string on a
      // `narrative_text` field (`field-value-derivation.ts:150`), so a numeric
      // value is the live shape. Dropping it would silently remove clinical
      // content from a section the note presents as COMPLETE — and the
      // validator, which re-derives with this same function, would accept the
      // loss.
      ['non-deriving affirmed', [affirmed, clone({ value: 42 }, 'n'), denied]],
      // LATERALITY — two sides among the AFFIRMED facts refuse on both paths.
      [
        'two lateralities',
        [
          clone({ laterality: 'left' }, 'l'),
          clone({ value: 'Effusion', laterality: 'right' }, 'r'),
          denied,
        ],
      ],
    ];

    for (const [name, facts] of CASES) {
      const affirmedOnly = facts.filter((f) => f.polarity === 'affirmed');
      const mixed = mixedPolarityNarrative(FIELD_STUB, MAPPING_STUB, facts);
      const join = joinListValuedNarrative(FIELD_STUB, MAPPING_STUB, affirmedOnly);
      expect([name, mixed.kind === 'text' ? mixed.text : null]).toEqual([name, join]);
    }

    // NON-VACUITY — the fixture set must actually exercise BOTH outcomes, or the
    // loop above passes by never reaching a refusal (or never reaching a value).
    const outcomes = CASES.map(([, facts]) =>
      mixedPolarityNarrative(FIELD_STUB, MAPPING_STUB, facts).kind,
    );
    expect(outcomes).toContain('text');
    expect(outcomes).toContain('refused');
  });

  it('(8g) ⚠️ A DENIAL\'S LATERALITY MUST NOT VETO THE DOCUMENT', async () => {
    // ⚠️ FOUND BY THE ADVERSARIAL PASS ON #157(d), AND IT IS THE AMENDMENT'S OWN
    // BLIND SPOT. The laterality guard read EVERY cited fact, and its stated
    // reason was that "a left-leg affirmation and a right-leg denial would be
    // merged into one unattributed section". That was true under #157(c), where
    // the denied fact PRINTED ITS QUOTE. #157(d) deleted that — a denied fact
    // now contributes ZERO characters (arm (8c)) — so nothing of the denial can
    // be merged and no unattributed section can form.
    //
    // ⚠️ THE AMENDMENT REMOVED THE REASON AND LEFT THE VETO. Measured before the
    // fix, on the modal vascular impression, this LOST THE WHOLE DOCUMENT:
    //   affirmed/right + denied/left -> lateralities.size 2 -> mixedRefused()
    //   -> polarity_conflict -> FIELD_CONFLICT -> render throws.
    // The affirmed fact ALONE rendered. So the DENIAL'S SIDE, and nothing else,
    // destroyed the export — on the owner's own specialty, on the branch whose
    // headline promise is that denials stop killing documents.
    //
    // ⚠️ AND THE GATE WAS 51/51 GREEN IN BOTH STATES. `laterality` appeared in
    // this file only in two fixtures and one spelling list; arm (8d) is the
    // designated mixed-refusal control and drives the SEGMENTS arm, where
    // "a refusal leaves the field where it was" genuinely holds. It never drove
    // the one arm where that control fails. Hence this arm.
    const pmh = (
      rows: ReadonlyArray<{ condition: string; quote: string }>,
    ) =>
      projected(rows.map((r) => r.quote).join(' '), {
        past_medical_history: rows.map((r) => ({
          condition: r.condition,
          evidence_quote: r.quote,
        })),
      });

    const AFFIRMED_RIGHT = {
      condition: 'Right leg deep vein thrombosis',
      quote: 'Findings consistent with right leg deep vein thrombosis.',
    };
    const DENIED_LEFT = {
      condition: 'Left leg deep vein thrombosis',
      quote: 'No evidence of left leg deep vein thrombosis.',
    };

    const mixed = await drive({
      omit: ['past_medical_history'],
      extraFacts: pmh([AFFIRMED_RIGHT, DENIED_LEFT]),
    });
    const withDenial = mixed.byLabel('Past medical history').resolution;

    // THE PROPERTY: the denial's side does not veto. The field resolves and the
    // package renders.
    expect(withDenial.status).not.toBe('conflict');
    expect(withDenial.reasonCode).not.toBe('polarity_conflict');
    expect(
      mixed.validation.issues
        .filter((i) => i.severity === 'blocking')
        .map((i) => i.code),
    ).toEqual([]);

    // ⚠️ THE ISOLATING CONTROL, AND IT IS WHAT MAKES THE ARM MEAN SOMETHING:
    // the value must be BYTE-IDENTICAL to what the affirmed fact produces
    // alone. That is the module's own "never better than affirmed alone"
    // invariant, and it proves the fix did not LAUNDER the denial into the
    // output — it removed the denial's vote on laterality and nothing else.
    const affirmedOnly = await drive({
      omit: ['past_medical_history'],
      extraFacts: pmh([AFFIRMED_RIGHT]),
    });
    const noDenial = affirmedOnly.byLabel('Past medical history').resolution;
    expect(withDenial.value).toEqual(noDenial.value);
    expect(noDenial.status).toBe('supported');

    // NON-VACUITY: the affirmed-alone run must actually carry a value, or the
    // equality above is satisfied by two nulls.
    expect(typeof noDenial.value).toBe('string');
    expect(String(noDenial.value).length).toBeGreaterThan(0);
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
    //
    // ⚠️ #157(d): the text is the AFFIRMED value alone, the token is the bare
    // base, and `withheldReasonCodes` is gone from the shape entirely — it was
    // only ever read to build the composed token, and `makeResolution` never
    // carried it anyway. `toEqual` on the whole object is what makes that a
    // gated deletion rather than an unobserved one.
    expect(mixedPolarityNarrative(FIELD_STUB, MAPPING_STUB, facts)).toEqual({
      kind: 'text',
      text: 'Pneumonia',
      reasonCode: 'mixed_polarity_per_fact',
    });
  });

  it('(8e) THE EVIDENCE RAIL REACHES THE MIXED VALUE — a value that is not the shared derivation is BLOCKED', async () => {
    const driven = await drive({
      omit: ['assessment'],
      extraFacts: projected(MIXED_TEXT, MIXED_ENTITIES),
    });
    const { field, resolution } = driven.byLabel('Impression');
    expect(resolution.value).toBe('Pneumonia');

    for (const forged of [
      // ⚠️ THE FIRST FOUR ARE THE #157(b)/(c) OUTPUTS, AND THE RAIL MUST NOW
      // REFUSE THEM. A resolution carrying the old composed value is exactly
      // what a half-reverted deployment would produce, and it must not
      // validate.
      'Pneumonia; No evidence of pulmonary embolism.', // #157(c)'s own output
      'No evidence of pulmonary embolism.; Pneumonia', // right parts, WRONG ORDER
      'Pneumonia; No pulmonary embolism.', // a plausible synthesis
      'No evidence of pulmonary embolism.', // the denial ALONE
      'Pneumonia; Pulmonary embolism', // the denied ENTITY appended
      'Pneumonia; Findings consistent with pneumonia.', // the affirmed quote
      'Pneumonia ', // one character of drift
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
        value: 'Pneumonia',
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
    // ⚠️ THIS ARM HAD TO BE REBUILT, AND HOW IT BROKE IS WORTH RECORDING. It
    // used to patch `value: null` onto the Allergies resolution, which #157(b)
    // made `explicitly_denied` + a string. Under #157(d) that resolution is
    // `denial_withheld` + null ALREADY, so the patch changed nothing, the
    // status was not populated, and the renderer had no reason to refuse — the
    // arm stopped constructing its own premise.
    //
    // ⚠️ IT WENT RED RATHER THAN GREEN, WHICH IS THE ONLY REASON IT WAS CAUGHT.
    // A vacuity that fails loudly is a gift; the same drift on an ABSENCE
    // assertion would have passed silently forever. So the premise is now built
    // EXPLICITLY here rather than inherited from whatever the pipeline happens
    // to produce this ruling.
    const driven = await drive({ denied: ['allergy.substance'] });
    const { resolution } = driven.byLabel('Allergies');
    expect(resolution.status).toBe('denial_withheld');
    await expect(
      renderTemplateDocx({
        source: driven.source,
        ir: driven.ir,
        resolutions: withResolution(driven, resolution.fieldId, {
          status: 'explicitly_denied',
          value: null,
          sourceFactIds: [],
          evidenceAnchorIds: [],
          reasonCode: 'explicit_denial_supported',
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
      // ⚠️ THE VALUE IS SUPPLIED HERE, FOR THE SAME REASON AS (6c). Patching
      // only the STATUS used to be enough because the Allergies resolution
      // carried #157(b)'s printed string; it now carries null, so a
      // status-only patch produces "no value under a non-populated status",
      // which is the LEGAL shape and refuses nothing.
      await expect(
        renderTemplateDocx({
          source: driven.source,
          ir: driven.ir,
          resolutions: withResolution(driven, resolution.fieldId, {
            status,
            value: 'no known drug allergies',
          }),
          validation: driven.validation,
        }),
      ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });
    }
  });

  it('(6e) THE EVIDENCE RAIL — an `explicitly_denied` narrative value is BLOCKED, whatever it says', async () => {
    // ⚠️ REWRITTEN FOR #157(d), AND THE REWRITE IS FORCED BY THE SCHEMA. Its
    // predecessor forged a VALUE onto the existing resolution; under rule (1)
    // that resolution is `denial_withheld` and `ir.ts`'s refine makes
    // "withheld AND holding a value" UNREPRESENTABLE — so the forgery cannot
    // even be constructed. The remaining route is to forge the STATUS too,
    // which is precisely the shape a half-reverted #157(b) would emit.
    //
    // ⚠️ AND THE ASSERTION IS STRONGER THAN THE OLD ONE. #157(b)'s rail refused
    // text the doctor did not dictate; #157(d)'s refuses ALL of it, including
    // the doctor's own sentence, verbatim, with nothing manufactured. That is
    // the whole ruling expressed at the verification layer.
    const driven = await drive({ denied: ['allergy.substance'] });
    const { field, resolution } = driven.byLabel('Allergies');
    expect(resolution.status).toBe('denial_withheld');
    expect(resolution.value).toBeNull();

    for (const forged of [
      'no known drug allergies', // #157(c)'s OWN OUTPUT — the doctor's words
      'Allergies: no known drug allergies', // the unstripped quote
      'No known drug allergies', // the ENTITY — the falsified #157's output
      'No allergies', // a plausible synthesis
    ]) {
      const forgedResolutions = withResolution(driven, resolution.fieldId, {
        status: 'explicitly_denied',
        value: forged,
        reasonCode: 'explicit_denial_dictated_quote',
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

    // ⚠️ MUTATE TOWARD SUCCESS TOO, or the rows above would pass on a rail that
    // refuses everything. The resolution the pipeline ACTUALLY produced must
    // still validate clean.
    expect(
      driven.validation.issues.filter(
        (i) => i.fieldId === field.fieldId && i.severity === 'blocking',
      ),
    ).toEqual([]);
    expect(driven.validation.valid).toBe(true);
  });

  it('(6h) ⚠️ THE RENDERER WALL RE-NARROWED — an `explicitly_denied` NARRATIVE refuses the DOCUMENT', async () => {
    // ⚠️ THE LAST THING STANDING IF THE RESOLVER EVER REGRESSES, AND #157(b)
    // WIDENED IT BY EXACTLY ONE SHAPE. `isPrintableDenial` admitted
    // `narrative_text` + a non-empty string on the reasoning that the string was
    // the doctor's own dictated sentence. #157(d) deletes that arm, so the wall
    // is back to `checkbox` + `false`.
    //
    // ⚠️ IT REFUSES RATHER THAN BLANKS, AND THAT DOES NOT CONTRADICT RULE (3).
    // Rule (3) says no DENIAL may refuse an export — and no legal resolver path
    // can reach here any more: a narrative denial is `denial_withheld` with a
    // null value long before the renderer sees it. Reaching this line means a
    // resolution no producer can mint, which is a BUG, and laundering a bug
    // into a quiet blank is how a signed note ends up asserting the opposite of
    // the record.
    const driven = await drive({ denied: ['allergy.substance'] });
    const { field, resolution } = driven.byLabel('Allergies');

    // At the predicate, directly — every narrative value, including the empty
    // string, and including the exact text #157(c) printed.
    for (const value of ['no known drug allergies', 'Allergies: x', '']) {
      expect([value, isPrintableDenial(field, value)]).toEqual([value, false]);
    }

    // ⚠️ AND THE VALIDATION HANDED TO THE RENDERER IS THE REAL, VALID ONE — so
    // a refusal below cannot come from VALIDATION_REQUIRED. It is this wall.
    expect(driven.validation.valid).toBe(true);
    await expect(
      renderTemplateDocx({
        source: driven.source,
        ir: driven.ir,
        resolutions: withResolution(driven, resolution.fieldId, {
          status: 'explicitly_denied',
          value: 'no known drug allergies',
          reasonCode: 'explicit_denial_dictated_quote',
        }),
        validation: driven.validation,
      }),
    ).rejects.toMatchObject({ code: 'FIELD_RESOLUTION_INVALID' });

    // ⚠️ MUTATE TOWARD SUCCESS — the ONE shape the wall still admits must still
    // pass, or this arm would be green for a wall that refuses everything and
    // rule (2)'s checkbox exception would be silently dead.
    const checkbox = await drive({ denied: ['medication.review'] });
    const box = checkbox.byLabel('Medication reviewed');
    expect(box.resolution.status).toBe('explicitly_denied');
    expect(isPrintableDenial(box.field, false)).toBe(true);
    expect(renderedTextOf(controlById(await checkbox.render(), '104'))).toBe('☐');
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

  // ══ #157(d) — THE MACHINERY IS DELETED, NOT GATED ═══════════════════════

  it('(9) ⚠️ THE NO-HEURISTIC ARM — the denial contract cannot READ the doctor’s words', async () => {
    // ⚠️ THIS ARM EXISTS BECAUSE OF HOW #157 FAILED THREE TIMES. Each fix was a
    // better predicate over TEXT, each was correct, and each moved the failure
    // one layer down while the gate stayed green. A rule that merely GATES the
    // machinery leaves it there for the next reader to repair; the only durable
    // form of "no text heuristic decides what prints" is that the module has no
    // way to look at the text at all.
    //
    // ⚠️ PROPERTIES, NOT SPELLINGS, WHEREVER POSSIBLE — and the deleted names
    // are checked LAST and labelled as the weak row, because a spelling gate
    // reds when somebody legitimately renames something and stays green when
    // somebody rebuilds the same logic under a new name. The properties above
    // it do not have that failure mode.
    const raw = denialContractSource();
    const code = denialContractCode();

    // ══ POSITIVE CONTROL FOR THE COMMENT STRIPPER, MEASURED RATHER THAN
    // ASSUMED — AND THE FIRST DRAFT OF THIS ARM GOT IT WRONG. ══════════════
    //
    // ⚠️ IT ASSERTED `raw` CONTAINED `evidenceQuote` AND `RegExp` "because the
    // tombstone comments mention them". Measured: BOTH ARE ZERO in the whole
    // file. The arm went red on its own control, which is the correct outcome
    // and the reason it is written down here: a control aimed where the answer
    // is merely EXPECTED is not a control.
    //
    // Two classes of row below, and they are kept apart deliberately:
    //
    //   · STRIPPER-CONTROLLED — the token IS in the comments and must be absent
    //     from the code. A broken stripper reds these.
    //   · WHOLE-FILE — the token is absent from the file ENTIRELY, comments
    //     included, which is a STRICTLY STRONGER claim and needs no stripper at
    //     all. Asserting these against `raw` says exactly that.
    expect(code.length).toBeGreaterThan(0);
    expect(code.length).toBeLessThan(raw.length);
    // THE STRIPPER'S OWN CONTROL: a backtick appears 190 times in the comments
    // and zero times in the code, so a stripper that did nothing reds here.
    expect(raw).toContain('`');
    expect(code).not.toContain('`');

    // ── PROPERTY 1 · IT CANNOT SEE THE DICTATION (whole-file) ─────────────
    // The doctor's words reach this module by exactly one route:
    // `fact.evidenceQuote`. The identifier does not occur anywhere in the file,
    // so rule (1) is a structural fact about the module and not a described
    // intention.
    expect(raw).not.toContain('evidenceQuote');

    // ── PROPERTY 2 · IT CANNOT PATTERN-MATCH (whole-file) ─────────────────
    // `SELF_NEGATION_CUE` was a RegExp; `locateFinding` built one per call;
    // `stripLeadingDictationHeading` `.exec`-ed one. None of the primitives a
    // text heuristic needs occurs anywhere in this file.
    for (const primitive of ['RegExp', '.test(', '.exec(', '.match(', 'toLowerCase']) {
      expect([primitive, raw.includes(primitive)]).toEqual([primitive, false]);
    }
    expect(/=\s*\/[^/\n]+\/[gimsuy]*/.test(code)).toBe(false);

    // ── PROPERTY 3 · IT CANNOT COMPOSE A REASON CODE (C3) ─────────────────
    // The composed `mixed_polarity_per_fact:<token>` was built with a template
    // literal, which is why it appeared as a literal nowhere and (7b)'s
    // predecessor was structurally blind to it. There is no interpolation
    // anywhere in the file, and no backtick in the code, so no runtime-composed
    // identifier is expressible here.
    expect(raw).not.toContain('${');

    // ── PROPERTY 4 · THE OUTCOME FUNCTION HAS NO ACCESS TO THE FACTS ──────
    // ⚠️ THE STRONGEST ROW, AND IT IS AN ARITY. `denialOutcome` used to take
    // `(field, mapping, facts)` and hand the facts to `narrativeDenialText`.
    // It now takes two arguments, so there is no encounter evidence in scope to
    // decide anything from — a property no rename or refactor can quietly undo.
    expect(denialOutcome.length).toBe(2);

    // ── PROPERTY 5 · WHAT IT DOES READ OFF A FACT ─────────────────────────
    // Metadata only. If a future edit reintroduces a text field here, this row
    // names it rather than letting it arrive as "just one more property".
    const factReads = [...code.matchAll(/fact\.([A-Za-z]+)/g)].map((m) => m[1]!);
    expect(factReads.length).toBeGreaterThan(0); // positive control for the scan
    expect([...new Set(factReads)].sort()).toEqual([
      'laterality',
      'polarity',
      'quality',
    ]);

    // ── PROPERTY 6 · THE EXPORTED SURFACE, RECONCILED ─────────────────────
    // ⚠️ ARITHMETIC THAT MUST RECONCILE. A new export is either in this list or
    // this row is red — which is what stops a print path being reintroduced
    // beside the deleted one rather than in place of it.
    const exported = [
      ...code.matchAll(/^export (?:const|function|type|interface)\s+(\w+)/gm),
    ].map((m) => m[1]!);
    expect([...exported].sort()).toEqual([
      'CERTIFICATION_EXEMPT_DENIAL_REASONS',
      'DENIAL_WITHHELD',
      'DENIAL_WITHHELD_NARRATIVE_ALWAYS_BLANK',
      'DenialOutcome',
      'MIXED_POLARITY_REASON',
      'MixedPolarityOutcome',
      'denialOutcome',
      'denialWithheldMaterialFieldIds',
      'isPrintableDenial',
      'mixedPolarityNarrative',
    ]);

    // ── THE WEAK ROW, LABELLED AS SUCH ────────────────────────────────────
    // The deleted identifiers, by name. This is a SPELLING check and it is the
    // last line of the arm on purpose: it catches a literal revert and nothing
    // cleverer. The properties above are what catch a rebuild.
    for (const symbol of [
      'SELF_NEGATION_VOCABULARY',
      'selfNegationCues',
      'selfNegationScopingFinding',
      'clauseBoundsAround',
      'locateFinding',
      'LEADING_DICTATION_HEADING',
      'stripLeadingDictationHeading',
      'dictatedDenialText',
      'narrativeDenialText',
      'DENIAL_QUOTE_NOT_SELF_NEGATING',
    ]) {
      // the control: every one of them IS named in the tombstone comments, so a
      // green below is the stripper working rather than the scan missing.
      expect([symbol, raw.includes(symbol)]).toEqual([symbol, true]);
      expect([symbol, code.includes(symbol)]).toEqual([symbol, false]);
    }
  });

  it('(10) ⚠️ NO LIVE PRODUCER TURNS A DENIED FACT INTO PRINTABLE TEXT — every reachable path, driven', async () => {
    // ⚠️ ARM (9) IS ABOUT THE MODULE; THIS IS ABOUT THE PRODUCT. Every kind the
    // compiler can emit, denied at once, under every polarityBehavior — and not
    // one denied fact's sentence, and not one denied fact's entity, reaches the
    // rendered package. That is rule (1) and rule (2) stated as ONE absence
    // assertion over the whole document rather than as fifteen per-field ones.
    for (const behavior of [
      'value_only',
      'not_applicable',
      'affirmative_only',
      'explicit_denial_allowed',
    ] as const) {
      const driven = await drive({ denied: ALL_CONCEPTS, behavior });
      const xml = await driven.render();

      // Every denied fact's own dictated sentence.
      const quotes = new Set(driven.facts.map((fact) => fact.evidenceQuote));
      // NON-VACUITY: there really are denied facts with distinct sentences.
      expect([behavior, quotes.size]).toEqual([behavior, quotes.size]);
      expect(quotes.size).toBeGreaterThan(5);
      for (const quote of quotes) {
        expect([behavior, quote, xml.includes(quote)]).toEqual([behavior, quote, false]);
      }
      // And every denied fact's VALUE — the falsified #157's output.
      for (const narrative of NARRATIVE) {
        expect([behavior, narrative.deniedEntity, xml.includes(narrative.deniedEntity)]).toEqual(
          [behavior, narrative.deniedEntity, false],
        );
      }
      // ⚠️ AND THE DOCUMENT STILL EXISTS — rule (3). An absence assertion is
      // trivially satisfied by a package that was never produced.
      expect([behavior, xml.length > 0]).toEqual([behavior, true]);
    }

    // ══ THE ISOLATING CONTROL FOR THE ENTIRE ABSENCE CLAIM. ═══════════════
    //
    // ⚠️ AND ITS FIRST DRAFT WAS WRONG IN A WAY WORTH RECORDING: it asserted
    // every `deniedEntity` reaches the AFFIRMED document. Four of five do — but
    // `Allergies` is dictated as "Allergies: penicillin" in the positive, so
    // its affirmed entity is `Penicillin` and `No known drug allergies` is a
    // string that run never produces. The control was comparing two runs that
    // do not name the same thing.
    //
    // ⚠️ SO THE PARTITION IS EXPLICIT AND ITS ARITHMETIC RECONCILES, rather than
    // the row being quietly dropped or special-cased. The predicate is derived
    // from the FIXTURE DATA, not hand-maintained, so it cannot drift out of
    // step with the dictations above it.
    const affirmed = await drive();
    const affirmedXml = await affirmed.render();
    const alsoAffirmed = NARRATIVE.filter((narrative) =>
      JSON.stringify(narrative.affirmedEntities).includes(narrative.deniedEntity),
    );
    // ARITHMETIC: four of the five narratives name the same entity in both
    // polarities; the fifth (Allergies) names a different one, by construction.
    expect(alsoAffirmed).toHaveLength(4);
    expect(NARRATIVE).toHaveLength(5);
    expect(alsoAffirmed.map((n) => n.label)).not.toContain('Allergies');

    // For those four, the entity DOES reach the affirmed document — so every
    // `false` above is a measurement about the denial and not a property of the
    // assertion.
    for (const narrative of alsoAffirmed) {
      expect([narrative.label, affirmedXml.includes(narrative.deniedEntity)]).toEqual([
        narrative.label,
        true,
      ]);
    }
    // And for ALL five — Allergies included — the field is really FILLED in the
    // affirmed run, so "blank when denied" is never satisfied by a fixture that
    // could not fill the control in the first place.
    for (const narrative of NARRATIVE) {
      expect([
        narrative.label,
        renderedTextOf(controlById(affirmedXml, narrative.controlId)).length > 0,
      ]).toEqual([narrative.label, true]);
    }
  });
});

