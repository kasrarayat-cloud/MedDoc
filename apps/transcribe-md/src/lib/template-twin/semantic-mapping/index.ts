// ============================================================================
// Template Twin — semantic mapping proposal helper
// ----------------------------------------------------------------------------
// Deterministic OOXML extraction owns structure. The model is used only to
// propose semantics for the exact extracted field set. Proposals can never
// certify a field, add/remove a field, alter options, or invent a default.
// ============================================================================

import {
  classifyFieldSource,
  isSubConcept,
  conceptOverrideFor,
  veinGridCellConcept,
  isRegisteredConcept,
  synonymsFor,
  REGISTRY_CONCEPTS,
  type MappingSourceType,
} from '../concept-registry';
import { RECORD_DERIVED_CONCEPTS } from '../visit-metadata';
import { isUnnamedRosConcept, ROS_SYSTEMS, symptomsFor } from '../ros-lexicon';
import { withoutPlaceholderOptions } from '../../note-template-docx/placeholder-option';
import { z } from 'zod';

import {
  modelClient,
  delimiterSystemSuffix,
  wrapAsData,
  type ModelClient,
} from '@meddoc/ai';

import {
  SemanticMappingProposalSchema,
  SemanticMappingSchema,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
  type TemplateTwinFieldKind,
} from '../ir';

const DEFAULT_MODEL =
  process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';

const ModelSemanticMappingSchema = SemanticMappingSchema.extend({
  // Defaults must be entered and approved by a physician, never authored by AI.
  practiceDefault: z.null(),
  // Certification is a separate authenticated physician action.
  status: z.enum(['recognized', 'needs_confirmation']),
  // ⚠️ #192 — THE MODEL MAY NOT AUTHOR A RENDER POLICY, FOR THE SAME REASON IT
  // MAY NOT AUTHOR A `practiceDefault` TWO LINES ABOVE.
  //
  // This schema EXTENDS `SemanticMappingSchema`, and `anthropic.ts` turns it
  // into the tool's `input_schema`, so ANY field added there is silently handed
  // to the model as settable. `unmentionedPolicy` arrived that way: an enum the
  // model could set, with no mention in the system prompt, deciding whether a
  // template's own sentence prints on a signed note. Measured end to end with
  // no human anywhere and validation GREEN: 11 of 11 proposals came back
  // `keep`, and a control containing `Enter assessment` rendered that string
  // into the note -- the exact harm #192 exists to prevent, arriving through
  // the one channel the ruling never considered, because "never inferred from
  // content" was aimed at the RENDERER and the model infers from content too.
  //
  // ⚠️ AND NOTHING DOWNSTREAM WOULD HAVE CAUGHT IT: `planAutoConfirm` spreads
  // the whole mapping into `status: 'certified'`, so the default path
  // certifies a model-authored policy with no physician present.
  //
  // ⚠️ OMITTED RATHER THAN FORCED TO NULL, which is stronger than the
  // `practiceDefault` treatment beside it: the field never appears in the tool
  // schema at all, so there is no value for the model to choose and nothing to
  // re-assert after parsing. Forcing `z.null()` would still SHOW it, and would
  // make the model's omission a parse error rather than a non-event.
})
  .omit({ unmentionedPolicy: true })
  .strict()
  /**
   * ⚠️ #208 — `conceptScope` IS A MAPPING, NOT A RENDER POLICY, SO THE MODEL MAY
   * PROPOSE IT — AND IT IS VALIDATED HERE RATHER THAN OMITTED ABOVE.
   *
   * The distinction is the whole ruling, and this file already embodies both
   * halves of it: `unmentionedPolicy` is a RENDER POLICY — what the machine does
   * when nothing was dictated — and is `omit`ted two lines up, because the model
   * may never author one. `clinicalConcept` and `conceptScope` are MAPPINGS —
   * which concept a field MEANS, which concepts a clause COVERS — and the model
   * proposes those, under validation and a human confirmation.
   *
   * A session read the two as colliding (#192/#193 forbid the model a policy;
   * #179(3) hands it a scope to propose) and escalated it as undecidable. There
   * is no collision; there is a category it had not separated.
   *
   * ⚠️ REFUSED AT PARSE, NOT DROPPED TO NULL — and that is deliberately UNLIKE
   * the `clinicalConcept` treatment in the reconciler below, which silently
   * nulls an off-registry proposal and leaves the field `needs_confirmation`.
   * A scope is a CLAIM ABOUT COVERAGE: silently shrinking it would leave a
   * clause asserting it covers fewer symptoms than the doctor will read on the
   * confirm list, and silently keeping it would let an unmatchable token sit in
   * a certified mapping. Neither is honest, so the proposal is rejected and the
   * model retries with the error — which is a MAPPING proposal, regenerable and
   * carrying no clinical content.
   *
   * ⚠️ AND THAT IS WHY THIS IS NOT THE L3 MISTAKE, WHICH LOOKS IDENTICAL. An
   * array-level refusal at L3 discarded a whole VISIT — chief complaint,
   * medications, allergies — because the payload was the patient's encounter and
   * the loss was clinical. Here the payload is a template's proposed mappings:
   * a refusal costs a retry, and the terminal fallback is
   * `fallbackSemanticMappings`, every row `needs_confirmation`. Refusing is
   * fail-closed on this seam and was fail-OPEN on that one.
   */
  .superRefine((mapping, ctx) => {
    const scope = mapping.conceptScope;
    if (!scope || scope.length === 0) return;
    scope.forEach((concept, index) => {
      if (!isRegisteredConcept(concept)) {
        ctx.addIssue({
          code: 'custom',
          path: ['conceptScope', index],
          message:
            `conceptScope entry "${concept}" is not a registered concept; ` +
            `a clause cannot declare coverage of something no fact can carry`,
        });
        return;
      }
      // ⚠️ AND AN UNNAMED ROS CONCEPT CANNOT BE IN A SCOPE, WHICH #179's OWN
      // BODY RULES: `ros.<system>.other` is "excluded from every declared scope
      // by construction". `conceptMatches` already refuses it at MATCH time, so
      // refusing it here makes the two readers agree instead of leaving a token
      // that parses, certifies, and can never match anything.
      if (isUnnamedRosConcept(concept)) {
        ctx.addIssue({
          code: 'custom',
          path: ['conceptScope', index],
          message:
            `conceptScope entry "${concept}" names no specific symptom; ` +
            `a scope is a list of named symptoms and the matcher refuses this`,
        });
      }
    });
  });

const ModelSemanticMappingProposalSchema = z
  .object({ mappings: z.array(ModelSemanticMappingSchema) })
  .strict();

export const TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE = [
  'chief_complaint',
  'hpi.onset',
  'hpi.duration',
  'hpi.quality',
  'hpi.severity',
  'hpi.location',
  'hpi.timing',
  'hpi.context',
  'hpi.modifying_factors',
  'hpi.associated_symptoms',
  'past_medical_history',
  'past_surgical_history',
  'medication.name',
  'medication.dose',
  'medication.route',
  'medication.frequency',
  'allergy.substance',
  'allergy.reaction',
  'family_history.relation',
  'family_history.condition',
  'social_history.smoking',
  'social_history.alcohol',
  'social_history.drugs',
  'social_history.marital_status',
  // #246 family 4 — registered AND offered. The pass found it in
  // REGISTRY_CONCEPTS but not here, so the proposer would never have suggested
  // it and a "Total minutes" control could only ever be mapped by hand.
  'total_time_minutes',
  'social_history.occupation',
  // #247 family 3 — THE DICTATED MEMBER, AND ONLY THE DICTATED MEMBER.
  //
  // ⚠️ `visit_metadata.patient_name` AND `.patient_age` ARE DELIBERATELY ABSENT
  // FROM THIS LIST. Their concept is decided by the COMPILER from the label
  // (`CONCEPT_LABEL_OVERRIDES`), which also decides
  // `sourceType: 'visit_metadata'`, so the proposer is not the route by which
  // they are mapped. Canon 136 says an unoffered registered concept is
  // unmappable; these two are mapped without the proposer, so it does not bite.
  //
  // ⚠️ AND THE FIRST VERSION OF THIS COMMENT CALLED THE OMISSION "THE SAFETY
  // PROPERTY", WHICH WAS FALSE — a refutation lens demonstrated it. It argued
  // that a model proposing a record concept on some other field would produce
  // "a mapping whose concept is record-derived and whose sourceType is
  // `extraction`, which no fact can ever satisfy: a permanently blank control".
  // The resolver never compares a MAPPING's sourceType to a FACT's. Measured,
  // with one legitimate `Patient` control present to mint the fact and one
  // mis-proposed `extraction` mapping on an HPI control: BOTH resolved
  // `record_derived` with value "Jane Alvarez", valid, zero issues — **the
  // patient's name printed into a clinical narrative control on the signed
  // form.** Prompt omission is a nudge, not a gate; the gate is
  // `isRegisteredConcept`, and this arc made it return true for both.
  //
  // The real gate is now `refuseRecordDerivedOnNonMetadata` below, which nulls
  // a record-derived concept on any mapping the compiler did not classify
  // `visit_metadata`. The omission stays because offering them is still
  // pointless, but it is no longer load-bearing.
  //
  // The referrer is different in kind: it is an ordinary L3 extraction, and a
  // form that says "Referred by" rather than "Referring MD" should still be
  // mappable. So it IS offered.
  'visit_metadata.referring_physician',
  // ⚠️ THREE PARTS, NOT TWO — AND THE TWO-PART FORM WAS THE ONLY THING THIS
  // COMPONENT EVER TAUGHT. #179(2) moved the projector to
  // `ros.<system>.<symptom>` and narrowed the registry pattern to match, so
  // the string below used to instantiate to a concept the registry REFUSES:
  // measured, `isRegisteredConcept('ros.gastrointestinal')` is FALSE while
  // `isRegisteredConcept('ros.gastrointestinal.heartburn')` is true. Every ROS
  // form field therefore landed `clinicalConcept: null`, which is why a
  // per-clause ROS control could never be certified at all.
  // ⚠️ `exam.<system>` is CORRECT and is deliberately left alone —
  // `isRegisteredConcept('exam.abdomen')` is true. Only ros went three-part,
  // so this is a one-line asymmetry and not a family-wide break.
  'ros.<system>.<symptom>',
  'exam.<system>',
  'test.name',
  'test.<test_name>.result',
  'assessment',
  'plan',
] as const;

/**
 * #247 — A RECORD-DERIVED CONCEPT ON A MAPPING THE COMPILER DID NOT CLASSIFY
 * `visit_metadata` IS REFUSED, AND THIS IS THE GATE THE PROMPT WAS PRETENDING
 * TO BE.
 *
 * ⚠️ FOUND BY A REFUTATION LENS, WHICH MEASURED THE HARM. `visit_metadata.
 * patient_name` and `.patient_age` are registered, so `isRegisteredConcept`
 * admits them; the resolver never compares a MAPPING's `sourceType` to a
 * FACT's; and `decideAutoConfirm` only refuses `sourceType === 'visit_metadata'`.
 * So a model proposing `visit_metadata.patient_name` for, say, an HPI control
 * produced a mapping that auto-confirmed as `{provenance: 'model'}` and then
 * **printed the patient's name into a clinical narrative box** — measured,
 * `record_derived`, valid, zero issues. Leaving those two concepts off the
 * proposer's guidance list was a nudge, not a gate.
 *
 * The compiler decides `visit_metadata` from the LABEL and from the field's
 * KIND, so a field it did not so classify has no business carrying an identity
 * concept, whoever proposed it. Nulling here leaves the mapping visibly
 * `needs_confirmation` — the same treatment an off-registry proposal gets —
 * rather than certifying a control that prints a name nobody asked it to.
 *
 * EXPORTED for its own arm: this is the kind of guard whose absence is
 * invisible, because a model rarely proposes it and the suite never does.
 */
export function refuseRecordDerivedOnNonMetadata(
  concept: string | null,
  sourceType: MappingSourceType,
): string | null {
  if (concept === null || sourceType === 'visit_metadata') return concept;
  const c = concept.trim().toLowerCase();
  return c === RECORD_DERIVED_CONCEPTS.name || c === RECORD_DERIVED_CONCEPTS.age
    ? null
    : concept;
}

export interface ProposeSemanticMappingsContext {
  practiceId: string;
  userId: string | null;
  model?: string;
  client?: Pick<ModelClient, 'complete'>;
}

export class SemanticMappingInvariantError extends Error {
  readonly code:
    | 'UNSAFE_DELIMITER'
    | 'FIELD_SET_MISMATCH'
    | 'DUPLICATE_FIELD'
    | 'TYPE_MISMATCH';

  constructor(
    code: SemanticMappingInvariantError['code'],
    message: string,
  ) {
    super(message);
    this.name = 'SemanticMappingInvariantError';
    this.code = code;
  }
}

export function expectedDataTypeForFieldKind(
  kind: TemplateTwinFieldKind,
): SemanticMapping['expectedDataType'] | null {
  switch (kind) {
    case 'narrative_text':
      return 'text';
    case 'single_select':
      return 'single_select';
    case 'multi_select':
      return 'multi_select';
    case 'checkbox':
      return 'boolean';
    case 'date':
      return 'date';
    case 'number':
      return 'number';
    case 'measurement':
      return 'measurement';
    case 'fixed_table':
    case 'repeating_table':
      return 'table';
    case 'static':
    case 'conditional_block':
    case 'unsupported':
      return null;
  }
}

export function isMappingTypeCompatible(
  field: TemplateField,
  mapping: SemanticMapping,
): boolean {
  return expectedDataTypeForFieldKind(field.kind) === mapping.expectedDataType;
}

/**
 * Table cells grouped by their row, so a cell can see its siblings. A vein grid
 * row is identified by containing a REFLUX TIME cell, which is what lets the
 * structure — rather than the model — decide the row's two concepts.
 */
export function tableCellsByRow(
  fields: readonly TemplateField[],
): Map<string, TemplateField[]> {
  const byRow = new Map<string, TemplateField[]>();
  for (const f of fields) {
    // ⚠️ OPTIONAL, THOUGH THE TYPE SAYS REQUIRED — and that is a behaviour
    // decision, not a convenience. This helper is reached from the FALLBACK
    // path, which runs precisely when the semantic provider is unavailable.
    // Throwing on a field with no binding would convert "the model is down, so
    // the mapping is unconfirmed" into "the upload fails" — strictly worse, and
    // a regression this refactor would otherwise have introduced. A field with
    // no binding is simply not a table cell.
    if (f.rendererBinding?.bindingType !== 'table_cell') continue;
    const key = `${f.tableId ?? ''}#${f.rendererBinding.rowIndex ?? -1}`;
    (byRow.get(key) ?? byRow.set(key, []).get(key)!).push(f);
  }
  return byRow;
}

/**
 * THE CONCEPT THE DOCUMENT ITSELF DECIDES — no model, no network, deterministic.
 *
 * A vein-grid structure or a label the compiler recognises names its own
 * concept. Returns null when the document decides nothing, leaving whatever the
 * caller has (a model proposal, or nothing at all).
 *
 * ⚠️ ONE IMPLEMENTATION, TWO CALLERS — the same doctrine the `sourceType`
 * comment below already records, and for the same reason. This logic used to
 * live inside `proposeSemanticMappings` alone, so `fallbackSemanticMappings`
 * hard-coded `clinicalConcept: null` for EVERY field and threw away 53 of 80
 * concepts on the real customer form that cost nothing to compute. That is the
 * `sourceType` defect one field over: the compiler's own answer available in
 * the model path and absent from the fallback.
 *
 * The registry check is deliberately NOT made here. The model path's precedence
 * is `grid ?? override ?? model proposal`, and one check at the end — folding it
 * in would let a compiler concept that failed the registry fall THROUGH to the
 * model's proposal instead of being dropped to null, which is a different
 * behaviour from the one that shipped.
 */
export function compilerDecidedConcept(
  field: TemplateField,
  rowCells: readonly TemplateField[],
): string | null {
  const gridConcept = veinGridCellConcept({
    originalLabel: field.originalLabel,
    isReflux: /reflux/i.test(field.originalLabel),
    rowHasRefluxCell: rowCells.some((c) => /reflux/i.test(c.originalLabel)),
    isRowLabelCell: field.labelSource === 'left_cell',
  });
  return gridConcept ?? conceptOverrideFor(field.originalLabel);
}

/**
 * Deterministic provider-failure fallback. It is structurally complete enough
 * for the physician review UI, and it carries the concept the DOCUMENT ITSELF
 * decides — but never an INFERRED one, never a default, and never a certified
 * status. It therefore cannot activate or fill a production document without
 * explicit physician mapping approval.
 *
 * ⚠️ THIS SENTENCE USED TO SAY "no inferred concept, synonym, default, or
 * certified status", and the concept/synonym half stopped being true the moment
 * the compiler's own answer started reaching this path. Corrected here rather
 * than left standing: a doc-comment describing an invariant the code no longer
 * holds is read as a description of the running system, which is the
 * `DEPLOYMENT_RUNBOOK.md` §5.6 failure in miniature. What did NOT change is the
 * part that matters — `status` is `needs_confirmation` for every field and
 * `practiceDefault` is null for every field.
 */
export function fallbackSemanticMappings(
  ir: Pick<TemplateDocIR, 'fields'>,
): SemanticMapping[] {
  const cellsByRow = tableCellsByRow(ir.fields);
  return [...ir.fields]
    .sort(
      (a, b) =>
        a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId),
    )
    .map((field) => {
      const expectedDataType = expectedDataTypeForFieldKind(field.kind);
      if (expectedDataType === null) {
        // TemplateFieldSchema excludes structural/static node kinds. Keep this
        // guard fail-closed in case an unparsed object reaches the helper.
        throw new SemanticMappingInvariantError(
          'TYPE_MISMATCH',
          `Compiler field kind has no fillable data type for ${field.fieldId}.`,
        );
      }
      // The document's own answer, registry-checked exactly as the model path
      // checks it. A concept here is a PROPOSAL — `status` below stays
      // `needs_confirmation` for every field, so nothing becomes certifiable
      // without the physician confirming it. What this removes is the busywork
      // of re-typing 53 concepts the form itself already determines.
      const rowKey = `${field.tableId ?? ''}#${field.rendererBinding?.rowIndex ?? -1}`;
      const decided = compilerDecidedConcept(field, cellsByRow.get(rowKey) ?? []);
      const clinicalConcept =
        decided && isRegisteredConcept(decided) ? decided : null;
      return SemanticMappingSchema.parse({
        fieldId: field.fieldId,
        clinicalConcept,
        expectedDataType,
        polarityBehavior:
          field.kind === 'checkbox' ? 'affirmative_only' : 'not_applicable',
        temporality: null,
        laterality: null,
        unitPolicy:
          field.kind === 'measurement'
            ? 'required'
            : field.kind === 'number'
              ? 'forbidden'
              : 'not_applicable',
        approvedSynonyms: clinicalConcept ? [...synonymsFor(clinicalConcept)] : [],
        required: field.required,
        blankPolicy: field.unknownPolicy,
        unknownPolicy: field.unknownPolicy,
        practiceDefault: null,
        // ⚠️ THE SAME CLASSIFIER THE MODEL PATH USES, FOR THE SAME REASON.
        // `classifyFieldSource` reads the COMPILER's label and the field's own
        // shape — it is not an inference, so it does not belong to the model
        // path alone. Omitting it here let the schema's `.default('extraction')`
        // silently label EVERY field `extraction`, including the enumerated
        // dropdowns whose values come from the note's constrained pick and the
        // manual fields that have no clinical concept BY CONSTRUCTION.
        //
        // That is not cosmetic. `MAPPINGS_NOT_READY` demands a concept for every
        // NON-manual field, so a manual field mislabelled `extraction` becomes
        // permanently unsatisfiable — and `concept-registry.ts` already records
        // what the enumerated half costs: classifying those as `extraction`
        // "left fourteen of them permanently blank on every real visit and
        // blocked the native export". The fallback path was still reproducing
        // the defect that comment was written about.
        //
        // One classifier, two callers. A second implementation would drift from
        // the first the day either is fixed.
        sourceType: classifyFieldSource(field.originalLabel, field),
        status: 'needs_confirmation',
      });
    });
}

function fieldForModel(field: TemplateField): Record<string, unknown> {
  return {
    fieldId: field.fieldId,
    originalLabel: field.originalLabel,
    labelSource: field.labelSource,
    kind: field.kind,
    // ⚠️ THE FOURTH READER, AND IT IS THE ONE THE ENUMERATION MISSED.
    //
    // This payload goes to `client.complete` (:355 below) as "Compiler-owned
    // field metadata" — so an unfiltered array TELLS THE MODEL that Word's
    // "Choose an item." is one of this field's enumerated clinical options,
    // on all 28 single-selects of the certified twin.
    //
    // Before the IR-stability fix the compiler stripped the placeholder, so
    // every downstream consumer inherited the exclusion for free and this line
    // was correct BY ACCIDENT. Persisting the array verbatim moved the
    // exclusion onto each reader — and moved it onto THIS one too, which the
    // "three readers" note did not count. `placeholder-option.ts`'s own header
    // records where that ends: the literal string rendered into an imaging
    // report on the laterality-critical SIDE OF EXAM control.
    //
    // The ordinal is UNCHANGED by the filter (see `withoutPlaceholderOptions`),
    // so the model still names the document's own index and a proposal keyed on
    // an ordinal stays addressable.
    allowedOptions: withoutPlaceholderOptions(field.allowedOptions).map((option) => ({
      ordinal: option.ordinal,
      displayText: option.displayText,
      value: option.value,
    })),
    requiredInSource: field.required,
    sourceUnknownPolicy: field.unknownPolicy,
    clinicallyMaterial: field.clinicallyMaterial,
    criticality: field.criticality,
    inTable: field.tableId !== null,
    rowPrototype: field.rowPrototype,
    detectionStatus: field.detectionStatus,
  };
}

const SYSTEM_PROMPT = [
  'You propose semantic mappings for fillable fields in a physician-owned Word template.',
  'The OOXML compiler is authoritative for structure. You MUST return exactly one mapping',
  'for every supplied fieldId and no other fieldId.',
  '',
  'You may propose: clinical concept, expected data type, polarity behavior, temporality,',
  'laterality, unit policy, synonyms, requiredness, blank/unknown policy, and whether the',
  'mapping is recognized or needs confirmation.',
  '',
  'You MUST NOT add/remove fields, change field IDs, change options, change layout, invent',
  'a practice default, or mark any mapping certified. If uncertain, use a null concept and',
  'needs_confirmation. Keep native dropdown options exactly as supplied.',
  '',
  // The extractor's REAL vocabulary, not a style hint. A concept outside it can
  // never be matched by any fact, so the field would be permanently unfillable —
  // which is exactly how 72/80 proposals came back unusable while looking, at
  // certification, like missing evidence. Constrain at GENERATION rather than
  // rejecting afterwards.
  'CLINICAL CONCEPT — CLOSED VOCABULARY. You MUST choose clinicalConcept from',
  'this list, or from one of the patterns below, or return null. A concept',
  'outside it is rejected and the field becomes permanently unfillable.',
  `  exact: ${REGISTRY_CONCEPTS.join(', ')}`,
  '  patterns: test.<snake_case_study>.result | exam.<snake_case_thing> | hpi.<snake_case_thing>',
  '            | ros.<system>.<symptom>',
  // ⚠️ GENERATED FROM THE SHIPPED LEXICON, NEVER HAND-COPIED. The model is
  // asked for a concept whose legal set is defined in `ros-lexicon.ts`; a
  // second hand-written list here is how the proposer and the registry drifted
  // apart in the first place. `symptomsFor` appends `other`, so the escape
  // hatch is taught by construction.
  `  ros systems: ${ROS_SYSTEMS.join(', ')}`,
  ...ROS_SYSTEMS.map((system) => `    ${system}: ${symptomsFor(system).join(', ')}`),
  'NEVER put anatomy, laterality, a segment name or a unit in the concept: a',
  'measurement concept is its KIND (measurement.diameter, measurement.reflux_time)',
  'and the vein, side and segment travel as structured data. One concept must be',
  'able to serve every row of a 26-row grid.',
  'If no listed concept fits the field, return null with needs_confirmation —',
  'that is a correct answer, not a failure.',
  `Additional guidance: ${TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE.join(', ')}`,
  delimiterSystemSuffix('transcript'),
].join('\n');

/**
 * Ask the shared ModelClient for a constrained proposal, then independently
 * reconcile it against the compiler-owned field set.
 */
/** Fields per model call. A single proposal for ALL fields of a large template
 *  (e.g. WM_IOV's 80 fields) blows past the 8192 output-token ceiling, truncating
 *  the tool-use JSON into a schema-fail + retry loop that never converges (a
 *  certify request just hangs). Chunking keeps every call's output small; chunks
 *  are disjoint + independent, so their proposals merge with no cross-talk. */
const MAPPING_CHUNK_SIZE = 20;

/** One model proposal over a subset of fields → its fieldId→mapping map. */
async function proposeMappingChunk(
  fields: readonly TemplateField[],
  context: ProposeSemanticMappingsContext,
): Promise<Map<string, SemanticMapping>> {
  const payload = JSON.stringify({ fields: fields.map(fieldForModel) }, null, 2);
  const wrapped = wrapAsData(payload, 'transcript');
  if (wrapped.injectionAttemptDetected) {
    throw new SemanticMappingInvariantError(
      'UNSAFE_DELIMITER',
      'Template field metadata contains a reserved data-boundary delimiter.',
    );
  }
  const client = context.client ?? modelClient;
  const proposed = await client.complete({
    practiceId: context.practiceId,
    visitId: null,
    userId: context.userId,
    purpose: 'tm_template_parse',
    provider: 'anthropic',
    model: context.model ?? DEFAULT_MODEL,
    system: SYSTEM_PROMPT,
    user: ['Compiler-owned field metadata:', wrapped.wrapped].join('\n'),
    schema: ModelSemanticMappingProposalSchema,
    maxTokens: 8192,
    temperature: 0,
    retryOnSchemaFail: true,
    useToolUse: {
      name: 'submit_template_twin_semantic_mappings',
      description:
        'Submit exactly one non-certified semantic mapping proposal for every supplied field ID.',
    },
  });
  const byId = new Map<string, SemanticMapping>();
  for (const raw of proposed.mappings) {
    if (byId.has(raw.fieldId)) {
      throw new SemanticMappingInvariantError(
        'DUPLICATE_FIELD',
        `The model returned duplicate mapping fieldId ${raw.fieldId}.`,
      );
    }
    byId.set(raw.fieldId, SemanticMappingSchema.parse(raw));
  }
  return byId;
}

export async function proposeSemanticMappings(
  ir: Pick<TemplateDocIR, 'fields'>,
  context: ProposeSemanticMappingsContext,
): Promise<SemanticMapping[]> {
  const orderedFields = [...ir.fields].sort(
    (a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId),
  );

  // Chunk the fields so each proposal stays well under the output-token ceiling;
  // run the (independent) chunks concurrently and merge. The full-set validation
  // below is unchanged — it still guarantees exactly one mapping per field.
  const chunks: TemplateField[][] = [];
  for (let i = 0; i < orderedFields.length; i += MAPPING_CHUNK_SIZE) {
    chunks.push(orderedFields.slice(i, i + MAPPING_CHUNK_SIZE));
  }
  const chunkMaps = await Promise.all(
    chunks.map((chunk) => proposeMappingChunk(chunk, context)),
  );

  const byId = new Map<string, SemanticMapping>();
  for (const chunkMap of chunkMaps) {
    for (const [fieldId, mapping] of chunkMap) {
      if (byId.has(fieldId)) {
        throw new SemanticMappingInvariantError(
          'DUPLICATE_FIELD',
          `The model returned duplicate mapping fieldId ${fieldId}.`,
        );
      }
      byId.set(fieldId, mapping);
    }
  }

  const expectedIds = new Set(orderedFields.map((field) => field.fieldId));
  const unexpected = [...byId.keys()].filter((fieldId) => !expectedIds.has(fieldId));
  const missing = orderedFields
    .map((field) => field.fieldId)
    .filter((fieldId) => !byId.has(fieldId));
  if (unexpected.length > 0 || missing.length > 0) {
    throw new SemanticMappingInvariantError(
      'FIELD_SET_MISMATCH',
      `Semantic mapping field set mismatch (missing=${missing.join(',') || 'none'}; unexpected=${unexpected.join(',') || 'none'}).`,
    );
  }

  // Cells grouped by their table row, so a cell can see its siblings — a vein
  // grid row is identified by containing a REFLUX TIME cell. Shared with the
  // fallback path; a second copy would drift the day either is fixed.
  const cellsByRow = tableCellsByRow(orderedFields);

  const mappings = orderedFields.map((field) => {
    const mapping = byId.get(field.fieldId);
    if (!mapping) {
      throw new SemanticMappingInvariantError(
        'FIELD_SET_MISMATCH',
        `Missing semantic mapping for ${field.fieldId}.`,
      );
    }
    // The renderable data type is DETERMINED by the compiler field kind, not the
    // model's guess — the model's job is the clinical concept/polarity/synonyms.
    // A large template makes the model occasionally propose e.g. `measurement`
    // for a narrative_text reflux cell; rather than hard-fail the whole draft on
    // that, the compiler kind is authoritative and we coerce expectedDataType to
    // it (fail-closed only if the kind has no fillable type, which the compiler
    // never emits for an ir.field).
    const compilerDataType = expectedDataTypeForFieldKind(field.kind);
    if (compilerDataType === null) {
      throw new SemanticMappingInvariantError(
        'TYPE_MISMATCH',
        `Compiler field kind has no fillable data type for ${field.fieldId}.`,
      );
    }

    // A structure or a label the compiler recognises decides its own concept;
    // otherwise the model's proposal stands, and either way it must be in the
    // registry.
    const rowKey = `${field.tableId ?? ''}#${field.rendererBinding.rowIndex ?? -1}`;
    const rowCells = cellsByRow.get(rowKey) ?? [];
    const candidate =
      compilerDecidedConcept(field, rowCells) ?? mapping.clinicalConcept;
    const registered = candidate && isRegisteredConcept(candidate) ? candidate : null;
    const sourceType = classifyFieldSource(field.originalLabel, field);
    const proposedConcept = refuseRecordDerivedOnNonMetadata(registered, sourceType);

    // Compiler uncertainty always wins over a model's optimistic recognition.
    // Nothing from this helper can become certified or carry a default.
    return SemanticMappingSchema.parse({
      ...mapping,
      expectedDataType: compilerDataType,
      // Classification is the COMPILER's label talking, not the model's guess —
      // the same doctrine as expectedDataType above. Read ONCE above, because
      // `refuseRecordDerivedOnNonMetadata` needs the same answer and two calls
      // are two readers of one rule.
      sourceType,
      // REGISTRY CONSTRAINT. A concept the extractor never emits can never be
      // matched by any fact, so the field would be permanently unfillable —
      // this is exactly how `filledCount=0` survived four sessions of fixes
      // downstream. Off-registry proposals are dropped to null here, which
      // leaves the mapping visibly `needs_confirmation` (see status below)
      // rather than certifying a dead field. Approved synonyms come from the
      // registry, not the model.
      clinicalConcept: proposedConcept,
      // ⚠️ THE MODEL'S SYNONYMS ARE FILTERED, AND THE LINE ABOVE IS WHY IT WAS
      // NOT OBVIOUS: the comment has always said "Approved synonyms come from
      // the registry, not the model", and the code has always unioned in the
      // model's array anyway. Harmless while every entry was a label guess
      // ("Drug Allergies"); NOT harmless once #159(b) registered the
      // sub-concepts, because `factSatisfiesMapping` matches on this exact set.
      // A model answering `medication` + `['medication.name','medication.dose',
      // …]` makes the bare family stand in for its members and the accumulator
      // joins one drug's ATTRIBUTES into a list of drugs — measured,
      // "Lisinopril; 10 mg; by mouth; daily; Amlodipine", supported, zero
      // blocking, a drug printed with NO DOSE. Found by the adversarial pass on
      // the finished diff, after the redesign had closed the same hole in
      // `synonymsFor` alone.
      approvedSynonyms: proposedConcept
        ? [
            ...new Set([
              ...(mapping.approvedSynonyms ?? []).filter((syn) => !isSubConcept(syn)),
              ...synonymsFor(proposedConcept),
            ]),
          ]
        : [],
      practiceDefault: null,
      status:
        proposedConcept === null ||
        field.detectionStatus !== 'recognized' ||
        mapping.status === 'needs_confirmation'
          ? 'needs_confirmation'
          : 'recognized',
    });
  });

  // Visible at PROPOSAL time, not discovered at certification time.
  const offRegistry = [
    ...new Set(
      mappings
        .filter((m) => m.clinicalConcept === null)
        .map((m) => m.fieldId),
    ),
  ];
  if (offRegistry.length > 0) {
    console.warn(
      `[template-twin:mappings] ${offRegistry.length}/${mappings.length} proposals were ` +
        'off-registry or unconcepted and are left unconfirmed: ' +
        `${offRegistry.slice(0, 10).join(',')}${offRegistry.length > 10 ? ',…' : ''}`,
    );
  }

  return SemanticMappingProposalSchema.parse({ mappings }).mappings;
}
