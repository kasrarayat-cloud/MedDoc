// ============================================================================
// Template Twin — semantic mapping proposal helper
// ----------------------------------------------------------------------------
// Deterministic OOXML extraction owns structure. The model is used only to
// propose semantics for the exact extracted field set. Proposals can never
// certify a field, add/remove a field, alter options, or invent a default.
// ============================================================================

import { isRegisteredConcept, synonymsFor, REGISTRY_CONCEPTS } from '../concept-registry';
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
}).strict();

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
  'social_history.occupation',
  'ros.<system>',
  'exam.<system>',
  'test.name',
  'test.<test_name>.result',
  'assessment',
  'plan',
] as const;

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
 * Deterministic provider-failure fallback. It is structurally complete enough
 * for the physician review UI, but intentionally contains no inferred concept,
 * synonym, default, or certified status. It therefore cannot activate or fill
 * a production document without explicit physician mapping approval.
 */
export function fallbackSemanticMappings(
  ir: Pick<TemplateDocIR, 'fields'>,
): SemanticMapping[] {
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
      return SemanticMappingSchema.parse({
        fieldId: field.fieldId,
        clinicalConcept: null,
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
        approvedSynonyms: [],
        required: field.required,
        blankPolicy: field.unknownPolicy,
        unknownPolicy: field.unknownPolicy,
        practiceDefault: null,
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
    allowedOptions: field.allowedOptions.map((option) => ({
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

    // Compiler uncertainty always wins over a model's optimistic recognition.
    // Nothing from this helper can become certified or carry a default.
    return SemanticMappingSchema.parse({
      ...mapping,
      expectedDataType: compilerDataType,
      // REGISTRY CONSTRAINT. A concept the extractor never emits can never be
      // matched by any fact, so the field would be permanently unfillable —
      // this is exactly how `filledCount=0` survived four sessions of fixes
      // downstream. Off-registry proposals are dropped to null here, which
      // leaves the mapping visibly `needs_confirmation` (see status below)
      // rather than certifying a dead field. Approved synonyms come from the
      // registry, not the model.
      clinicalConcept:
        mapping.clinicalConcept && isRegisteredConcept(mapping.clinicalConcept)
          ? mapping.clinicalConcept
          : null,
      approvedSynonyms:
        mapping.clinicalConcept && isRegisteredConcept(mapping.clinicalConcept)
          ? [...new Set([...(mapping.approvedSynonyms ?? []), ...synonymsFor(mapping.clinicalConcept)])]
          : [],
      practiceDefault: null,
      status:
        mapping.clinicalConcept === null ||
        !isRegisteredConcept(mapping.clinicalConcept) ||
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
