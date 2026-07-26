// ============================================================================
// Template Twin — versioned document IR, semantic mapping, and fill contracts
// ----------------------------------------------------------------------------
// These schemas are the single typed boundary shared by the deterministic
// OOXML compiler, physician certification, evidence resolver, renderer, and
// visit review. They deliberately contain no provider-specific types.
// ============================================================================

import { z } from 'zod';

export const TEMPLATE_TWIN_IR_SCHEMA_VERSION = 1 as const;
export const TEMPLATE_TWIN_COMPILER_VERSION = 'template-docx-compiler/1.0.0';
export const TEMPLATE_TWIN_RESOLVER_VERSION = 'template-field-resolver/1.0.0';
export const TEMPLATE_TWIN_RENDERER_VERSION = 'template-docx-renderer/1.0.0';

export const Sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);

export const TemplateTwinFieldKindSchema = z.enum([
  'static',
  'narrative_text',
  'single_select',
  'multi_select',
  'checkbox',
  'date',
  'number',
  'measurement',
  'fixed_table',
  'repeating_table',
  'conditional_block',
  'unsupported',
]);
export type TemplateTwinFieldKind = z.infer<typeof TemplateTwinFieldKindSchema>;

export const TemplateTwinDetectionStatusSchema = z.enum([
  'recognized',
  'needs_confirmation',
  'unsupported',
  'certified',
]);
export type TemplateTwinDetectionStatus = z.infer<
  typeof TemplateTwinDetectionStatusSchema
>;

export const TemplateOptionSchema = z.object({
  ordinal: z.number().int().nonnegative(),
  displayText: z.string(),
  value: z.string(),
});
export type TemplateOption = z.infer<typeof TemplateOptionSchema>;

export const RendererBindingSchema = z
  .object({
    partName: z.string().min(1).max(240),
    bindingType: z.enum([
      'content_control',
      'table_cell',
      'legacy_form_field',
      'repeating_row',
    ]),
    /** Deterministic structural path; labels are never renderer locators. */
    path: z.string().min(1).max(512),
    ordinal: z.number().int().nonnegative(),
    sdtId: z.string().max(80).nullable(),
    tag: z.string().max(240).nullable(),
    alias: z.string().max(240).nullable(),
    legacyName: z.string().max(240).nullable(),
    tableIndex: z.number().int().nonnegative().nullable(),
    /** Laterality of this binding's table ROW, stamped at compile time from the
     *  document's own leg heading rows. 'unknown' when the document gives no
     *  signal — never inferred from ordering. Addressing uses it fail-closed:
     *  a sided fact may only fill a same-sided row. */
    rowLaterality: z.enum(['right', 'left', 'unknown']).default('unknown'),
    rowIndex: z.number().int().nonnegative().nullable(),
    cellIndex: z.number().int().nonnegative().nullable(),
    repeatAncestorPath: z.string().max(512).nullable(),
    sourceControlSha256: Sha256Schema,
    originalContentSha256: Sha256Schema,
  })
  .strict();
export type RendererBinding = z.infer<typeof RendererBindingSchema>;

export const UnsupportedElementSchema = z
  .object({
    code: z.string().min(1).max(80),
    partName: z.string().min(1).max(240),
    path: z.string().min(1).max(512),
    label: z.string().max(240).nullable(),
    detail: z.string().min(1).max(500),
    clinicallyMaterial: z.boolean(),
    blocksCertification: z.boolean(),
  })
  .strict();
export type UnsupportedElement = z.infer<typeof UnsupportedElementSchema>;

export const TemplateFieldSchema = z
  .object({
    fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/),
    kind: TemplateTwinFieldKindSchema.exclude([
      'static',
      'fixed_table',
      'repeating_table',
      'conditional_block',
      'unsupported',
    ]),
    originalLabel: z.string().min(1).max(240),
    labelSource: z.enum([
      'alias',
      'tag',
      'legacy_name',
      'same_container',
      'left_cell',
      'table_header',
      'preceding_text',
      'generated',
    ]),
    displayOrder: z.number().int().nonnegative(),
    detectionStatus: TemplateTwinDetectionStatusSchema,
    allowedOptions: z.array(TemplateOptionSchema),
    rendererBinding: RendererBindingSchema,
    required: z.boolean(),
    unknownPolicy: z.enum(['blank', 'not_documented', 'requires_input']),
    clinicallyMaterial: z.boolean(),
    criticality: z.enum([
      'routine',
      'medication',
      'allergy',
      'number_unit',
      'laterality',
      'date_duration',
    ]),
    tableId: z.string().max(80).nullable(),
    rowPrototype: z.boolean(),
  })
  .strict();
export type TemplateField = z.infer<typeof TemplateFieldSchema>;

export const TemplateTableCellSchema = z
  .object({
    rowIndex: z.number().int().nonnegative(),
    cellIndex: z.number().int().nonnegative(),
    logicalColumnStart: z.number().int().nonnegative(),
    gridSpan: z.number().int().positive(),
    verticalMerge: z.enum(['none', 'restart', 'continue']),
    nestedTableCount: z.number().int().nonnegative(),
    fieldIds: z.array(z.string().regex(/^ttf_[a-f0-9]{24}$/)),
    staticTextSha256: Sha256Schema,
  })
  .strict();

export const TemplateTableSchema = z
  .object({
    tableId: z.string().regex(/^ttb_[a-f0-9]{20}$/),
    partName: z.string().min(1).max(240),
    path: z.string().min(1).max(512),
    kind: z.enum(['fixed_table', 'repeating_table']),
    displayOrder: z.number().int().nonnegative(),
    gridColumnWidths: z.array(z.number().int().nonnegative()),
    rowCount: z.number().int().nonnegative(),
    repeatPrototypeRow: z.number().int().nonnegative().nullable(),
    maxRows: z.number().int().positive().max(100),
    cells: z.array(TemplateTableCellSchema),
  })
  .strict();
export type TemplateTable = z.infer<typeof TemplateTableSchema>;

export const TemplateDocNodeSchema = z
  .object({
    nodeId: z.string().regex(/^ttn_[a-f0-9]{20}$/),
    partName: z.string().min(1).max(240),
    path: z.string().min(1).max(512),
    displayOrder: z.number().int().nonnegative(),
    kind: TemplateTwinFieldKindSchema,
    fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/).nullable(),
    tableId: z.string().regex(/^ttb_[a-f0-9]{20}$/).nullable(),
    staticTextSha256: Sha256Schema.nullable(),
    bookmarkNames: z.array(z.string().max(240)),
  })
  .strict();

export const TemplateDocPartSchema = z
  .object({
    partName: z.string().min(1).max(240),
    contentType: z.string().min(1).max(240),
    kind: z.enum([
      'document',
      'header',
      'footer',
      'styles',
      'numbering',
      'relationships',
      'media',
      'other',
    ]),
    sha256: Sha256Schema,
    staticSha256: Sha256Schema,
    relationshipCount: z.number().int().nonnegative(),
  })
  .strict();

export const TemplateDocStatsSchema = z
  .object({
    totalFields: z.number().int().nonnegative(),
    dropdowns: z.number().int().nonnegative(),
    comboBoxes: z.number().int().nonnegative(),
    checkboxes: z.number().int().nonnegative(),
    dateControls: z.number().int().nonnegative(),
    tables: z.number().int().nonnegative(),
    repeatingTables: z.number().int().nonnegative(),
    headers: z.number().int().nonnegative(),
    footers: z.number().int().nonnegative(),
    unsupported: z.number().int().nonnegative(),
    blockingUnsupported: z.number().int().nonnegative(),
  })
  .strict();

export const TemplateDocIRSchema = z
  .object({
    irSchemaVersion: z.literal(TEMPLATE_TWIN_IR_SCHEMA_VERSION),
    compilerVersion: z.string().min(1).max(120),
    source: z
      .object({
        sha256: Sha256Schema,
        sizeBytes: z.number().int().positive(),
        mimeType: z.literal(
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        ),
      })
      .strict(),
    parts: z.array(TemplateDocPartSchema).min(3),
    nodes: z.array(TemplateDocNodeSchema),
    fields: z.array(TemplateFieldSchema),
    tables: z.array(TemplateTableSchema),
    unsupported: z.array(UnsupportedElementSchema),
    structureSha256: Sha256Schema,
    staticContentSha256: Sha256Schema,
    stats: TemplateDocStatsSchema,
  })
  .strict()
  .superRefine((ir, ctx) => {
    const ids = new Set<string>();
    for (const field of ir.fields) {
      if (ids.has(field.fieldId)) {
        ctx.addIssue({
          code: 'custom',
          message: `Duplicate fieldId ${field.fieldId}`,
          path: ['fields'],
        });
      }
      ids.add(field.fieldId);
      if (
        (field.kind === 'single_select' || field.kind === 'multi_select') &&
        field.allowedOptions.length === 0
      ) {
        ctx.addIssue({
          code: 'custom',
          message: 'Select fields must preserve at least one native option',
          path: ['fields', field.displayOrder, 'allowedOptions'],
        });
      }
    }
  });
export type TemplateDocIR = z.infer<typeof TemplateDocIRSchema>;

export const SemanticMappingSchema = z
  .object({
    fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/),
    /**
     * WHERE this field's value legitimately comes from.
     *
     *  'extraction'      — dictated; fills from a cited EncounterFact. The only
     *                      class that may ever produce a value today.
     *  'manual'          — a per-visit human field (the technologist on shift).
     *                      Nothing can know it, so it is attested BLANK with a
     *                      named reason rather than blocking certification —
     *                      the needs-input mechanism, applied by class.
     *  'context_default' — RESERVED. Deterministic practice context (referring
     *                      physician, machine, location). NOT implemented: a
     *                      deterministic fill puts content into a signed note
     *                      that the clinician did not dictate, and the flagged
     *                      review-before-sign lane for that does not exist yet.
     *                      Until it does, these classify as 'manual' and render
     *                      honestly blank.
     *  'visit_metadata'  — RESERVED. Deterministic from the visit record.
     */
    sourceType: z
      .enum([
        'extraction',
        'context_default',
        'visit_metadata',
        'manual',
        // An enumerated dropdown filled from the live brain's CHOICE_SLOT pick in
        // the ADOPTED note. Its own provenance class with its own strict checks:
        // verbatim option only, adopted note only, never from a set-aside
        // section, and the marker + note version recorded on the cited fact.
        'verified_note_selection',
      ])
      .default('extraction'),
    clinicalConcept: z.string().min(1).max(160).nullable(),
    expectedDataType: z.enum([
      'text',
      'single_select',
      'multi_select',
      'boolean',
      'date',
      'number',
      'measurement',
      'table',
    ]),
    polarityBehavior: z.enum([
      'affirmative_only',
      'explicit_denial_allowed',
      'value_only',
      'not_applicable',
    ]),
    temporality: z.enum(['current', 'historical', 'planned', 'any']).nullable(),
    laterality: z.enum(['required', 'optional', 'not_applicable']).nullable(),
    unitPolicy: z.enum(['required', 'optional', 'forbidden', 'not_applicable']).nullable(),
    approvedSynonyms: z.array(z.string().min(1).max(120)).max(50),
    required: z.boolean(),
    blankPolicy: z.enum(['blank', 'not_documented', 'requires_input']),
    unknownPolicy: z.enum(['blank', 'not_documented', 'requires_input']),
    practiceDefault: z.string().max(500).nullable(),
    status: TemplateTwinDetectionStatusSchema,
  })
  .strict();
export type SemanticMapping = z.infer<typeof SemanticMappingSchema>;

export const SemanticMappingProposalSchema = z
  .object({
    mappings: z.array(SemanticMappingSchema),
  })
  .strict();

export const EncounterFactSchema = z
  .object({
    factId: z.string().regex(/^ttfact_[a-f0-9]{24}$/),
    sourceType: z
      .enum([
        'encounter_evidence',
        'approved_practice_default',
        // A pick the live brain made from the template's OWN enumerated options
        // and the doctor adopted into the final note. Its provenance is the note
        // selection itself — marker + note version — not a separately extracted
        // fact, so it carries its own identity and anchor.
        'verified_note_selection',
        'clinician_correction',
      ])
      .default('encounter_evidence'),
    concept: z.string().min(1).max(160),
    value: z.union([z.string(), z.number(), z.boolean()]),
    polarity: z.enum(['affirmed', 'denied', 'uncertain', 'conditional']),
    temporality: z.enum(['current', 'historical', 'planned', 'unknown']),
    experiencer: z.enum(['patient', 'family', 'other', 'unknown']),
    laterality: z.enum(['left', 'right', 'bilateral', 'midline', 'not_applicable', 'unknown']),
    number: z.number().nullable(),
    unit: z.string().max(40).nullable(),
    speaker: z.string().max(80).nullable(),
    sourceTranscriptOffsets: z
      .object({ start: z.number().int().nonnegative(), end: z.number().int().nonnegative() })
      .nullable(),
    audioTimestampSeconds: z.number().nonnegative().nullable(),
    evidenceAnchorIds: z.array(z.string().min(1).max(120)).min(1),
    evidenceQuote: z.string().min(1),
    quality: z
      .object({
        asr: z.enum(['high', 'review', 'unknown']),
        evidence: z.enum(['direct', 'conflicting', 'unclear']),
      })
      .strict(),
  })
  .strict();
export type EncounterFact = z.infer<typeof EncounterFactSchema>;

export const FieldResolutionStatusSchema = z.enum([
  'supported',
  'explicitly_denied',
  'not_mentioned',
  'ambiguous',
  'conflict',
  'needs_clinician_input',
  'approved_practice_default',
]);
export type FieldResolutionStatus = z.infer<typeof FieldResolutionStatusSchema>;

export const ResolvedFieldValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.array(z.string()),
  z.array(z.record(z.string(), z.string().nullable())),
]);

export const FieldResolutionSchema = z
  .object({
    fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/),
    status: FieldResolutionStatusSchema,
    value: ResolvedFieldValueSchema.nullable(),
    sourceFactIds: z.array(z.string().regex(/^ttfact_[a-f0-9]{24}$/)),
    evidenceAnchorIds: z.array(z.string().min(1).max(120)),
    selectedOptionOrdinal: z.number().int().nonnegative().nullable(),
    reasonCode: z.string().min(1).max(120),
    clinicianReviewed: z.boolean(),
  })
  .strict()
  .superRefine((resolution, ctx) => {
    const evidenceRequired = resolution.value !== null;
    if (evidenceRequired && resolution.sourceFactIds.length === 0) {
      ctx.addIssue({
        code: 'custom',
        message: 'Every populated clinical value requires sourceFactIds',
        path: ['sourceFactIds'],
      });
    }
    if (evidenceRequired && resolution.evidenceAnchorIds.length === 0) {
      ctx.addIssue({
        code: 'custom',
        message: 'Every populated clinical value requires evidence anchors',
        path: ['evidenceAnchorIds'],
      });
    }
  });
export type FieldResolution = z.infer<typeof FieldResolutionSchema>;

export const FieldValidationIssueSchema = z
  .object({
    fieldId: z.string().regex(/^ttf_[a-f0-9]{24}$/).nullable(),
    code: z.string().min(1).max(120),
    severity: z.enum(['warning', 'blocking']),
    message: z.string().min(1).max(500),
  })
  .strict();

export const TemplateTwinValidationResultSchema = z
  .object({
    valid: z.boolean(),
    issues: z.array(FieldValidationIssueSchema),
    checkedAt: z.string().datetime(),
    validatorVersion: z.string().min(1).max(120),
  })
  .strict();
export type TemplateTwinValidationResult = z.infer<
  typeof TemplateTwinValidationResultSchema
>;

export const TemplateTwinFillManifestSchema = z
  .object({
    manifestVersion: z.literal(1),
    compiledVersionId: z.string().min(1),
    noteTemplateId: z.string().min(1),
    noteTemplateVersion: z.number().int().positive(),
    compilerVersion: z.string().min(1),
    resolverVersion: z.string().min(1),
    resolverModelVersion: z.string().nullable(),
    rendererVersion: z.string().min(1),
    facts: z.array(EncounterFactSchema),
    fields: z.array(FieldResolutionSchema),
    validation: TemplateTwinValidationResultSchema,
    counts: z
      .object({
        filled: z.number().int().nonnegative(),
        needsReview: z.number().int().nonnegative(),
        notMentioned: z.number().int().nonnegative(),
        conflicts: z.number().int().nonnegative(),
        criticalUnresolved: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .strict();
export type TemplateTwinFillManifest = z.infer<typeof TemplateTwinFillManifestSchema>;

export function templateTwinCounts(
  fields: readonly FieldResolution[],
  definitions: readonly TemplateField[],
): TemplateTwinFillManifest['counts'] {
  const critical = new Map(definitions.map((field) => [field.fieldId, field.criticality]));
  const unresolved = new Set<FieldResolutionStatus>([
    'ambiguous',
    'conflict',
    'needs_clinician_input',
  ]);
  return {
    filled: fields.filter((field) => field.value !== null).length,
    needsReview: fields.filter((field) => unresolved.has(field.status)).length,
    notMentioned: fields.filter((field) => field.status === 'not_mentioned').length,
    conflicts: fields.filter((field) => field.status === 'conflict').length,
    criticalUnresolved: fields.filter(
      (field) =>
        unresolved.has(field.status) &&
        critical.get(field.fieldId) !== undefined &&
        critical.get(field.fieldId) !== 'routine',
    ).length,
  };
}
