// ============================================================================
// Template Twin — semantic mapping proposal helper
// ----------------------------------------------------------------------------
// Deterministic OOXML extraction owns structure. The model is used only to
// propose semantics for the exact extracted field set. Proposals can never
// certify a field, add/remove a field, alter options, or invent a default.
// ============================================================================

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
  `Canonical concept vocabulary/patterns: ${TEMPLATE_TWIN_CANONICAL_CONCEPT_GUIDANCE.join(', ')}`,
  delimiterSystemSuffix('transcript'),
].join('\n');

/**
 * Ask the shared ModelClient for a constrained proposal, then independently
 * reconcile it against the compiler-owned field set.
 */
export async function proposeSemanticMappings(
  ir: Pick<TemplateDocIR, 'fields'>,
  context: ProposeSemanticMappingsContext,
): Promise<SemanticMapping[]> {
  const orderedFields = [...ir.fields].sort(
    (a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId),
  );
  const payload = JSON.stringify(
    { fields: orderedFields.map(fieldForModel) },
    null,
    2,
  );
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
    // Reuse the existing template-analysis accounting lane. A dedicated
    // purpose can be introduced later without bypassing ModelClient.
    purpose: 'tm_template_parse',
    provider: 'anthropic',
    model: context.model ?? DEFAULT_MODEL,
    system: SYSTEM_PROMPT,
    user: ['Compiler-owned field metadata:', wrapped.wrapped].join('\n'),
    schema: ModelSemanticMappingProposalSchema,
    // A full proposal for a large template (e.g. WM_IOV's 28 dropdowns) exceeds
    // 4096 output tokens; 8192 leaves headroom so the tool-use JSON is not truncated.
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
    if (!isMappingTypeCompatible(field, mapping)) {
      throw new SemanticMappingInvariantError(
        'TYPE_MISMATCH',
        `Mapping data type does not match compiler field kind for ${field.fieldId}.`,
      );
    }

    // Compiler uncertainty always wins over a model's optimistic recognition.
    // Nothing from this helper can become certified or carry a default.
    return SemanticMappingSchema.parse({
      ...mapping,
      practiceDefault: null,
      status:
        mapping.clinicalConcept === null ||
        field.detectionStatus !== 'recognized' ||
        mapping.status === 'needs_confirmation'
          ? 'needs_confirmation'
          : 'recognized',
    });
  });

  return SemanticMappingProposalSchema.parse({ mappings }).mappings;
}
