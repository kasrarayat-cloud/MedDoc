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
      // ⚠️ THE DEFAULT STAYS, AND ITS REASON IS WRITTEN HERE RATHER THAN
      // ASSUMED. Removal was evaluated on 2026-08-15 (owner ruling, item 3)
      // because a default must never be the assumed classification. The
      // evidence, in full:
      //
      //   · both CONSTRUCTING sites now classify explicitly
      //     (`fallbackSemanticMappings` and the model proposer, one shared
      //     `classifyFieldSource`), so the default is no longer load-bearing
      //     for anything this codebase writes;
      //   · with it removed, `tsc` was CLEAN and only tests failed — 8
      //     `procedure-date` fixtures that omit the field, plus one arm in
      //     `source-type-roundtrip.test.ts` that asserts the default by name;
      //   · so removal is runtime-PLAUSIBLE.
      //
      // It is kept anyway, for one reason: SIX re-parse sites feed the FILL
      // path (`fill-engine`, `resolver`, `validation` — the last via
      // `safeParse` on raw input). Removing the default converts "a mapping
      // arrived without a classification" from a silent mislabel into a THROW
      // WHILE FILLING A DOCTOR'S DOCUMENT. The schema's input is loosely typed,
      // so `tsc` cannot prove no such value exists — and a red test is a
      // strictly better place to learn this than a doctor's export.
      //
      // The ruling's goal — "a future path that forgets fails loudly" — is
      // therefore met by `gate-source-type-explicit.test.ts`, which fails when
      // a CONSTRUCTING site omits `sourceType`. Loud at author time, silent at
      // fill time. Revisit only with the fill path's own adversarial pass.
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
    /**
     * ⚠️ `.optional()`, NOT `.default('keep')`. `z.infer` gives the OUTPUT type,
     * where a defaulted field is REQUIRED — which made every hand-built
     * `SemanticMapping` fixture in the suite a type error, for a field none of
     * them care about. Optional says the same thing where it matters: ABSENCE
     * MEANS KEEP, and the column's own `DEFAULT 'keep'` carries it in the
     * database.
     */
    unmentionedPolicy: z.enum(['keep', 'omit']).optional(),
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
    /**
     * ANATOMICAL SEGMENT AS SPOKEN — "GSV at the SFJ". Structured, because the
     * evidence quote is not a reliable carrier of it.
     *
     * ⚠️ F5-e. L3 extracts this per measurement (`03-extract-entities.ts:254`,
     * REQUIRED `min(1)`) and emits ONE ENTRY PER NUMBER, so a line dictating a
     * diameter and a reflux time yields two entries that both name the vessel.
     * The projection then dropped it: `segment` reached `add()` and was spent
     * only on the fact-ID hash. Downstream, `segmentCongruent` had to recover
     * anatomy from the QUOTE — which works for the diameter half ("Right GSV at
     * the SFJ: diameter 3.10 millimeters") and never for the reflux half
     * ("reflux time 0.110 seconds"). Measured on production's own manifest:
     * anatomy present in 20 of 20 diameter quotes and 0 of 20 reflux quotes, so
     * every reflux cell refused `no_supporting_fact` and rendered BLANK.
     *
     * Nullable, defaulted, and NOT `min(1)`: most facts are not measurements and
     * have no segment, and a default keeps every previously-constructed fact
     * parseable under `.strict()`.
     *
     * ⚠️ Adding this changes NO factId — `sourceIdentity` already hashed the
     * segment before it was ever emitted.
     */
    segment: z.string().max(120).nullable().default(null),
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
  /**
   * OWNER RULING #157(b) — THE FIELD IS BLANK **BECAUSE** THE ENCOUNTER DENIED
   * IT, AND THE MANIFEST SAYS SO BY NAME.
   *
   * ⚠️ A NEW STATUS WAS REQUIRED; NOTHING IN THE ENUM ABOVE COULD CARRY THIS.
   * Rule (3) needs one that is simultaneously (i) legal at the renderer,
   * (ii) NON-BLOCKING at validation, and (iii) reason-carrying. Measured
   * against every existing member:
   *
   *   not_mentioned          NOT_MENTIONED_HAS_EVIDENCE is BLOCKING the moment
   *                          `sourceFactIds` is non-empty, so reusing it means
   *                          DISCARDING the citation — destroying the audit
   *                          trail and making the manifest silent, which is the
   *                          one thing rule (3) forbids outright.
   *   ambiguous              FIELD_AMBIGUOUS is blocking when the field is
   *                          critical/required. That IS today's harm.
   *   conflict               always blocking.
   *   needs_clinician_input  DOWNGRADED TO A WARNING at certification
   *                          (`allowUncertifiedForSyntheticTest`), so a
   *                          template would certify GREEN with a clinically
   *                          material section silently blank.
   *
   * `denial_withheld` carries its evidence, never blocks a document, is counted
   * as `needsReview` (and `criticalUnresolved` where the field is not routine),
   * and BLOCKS CERTIFICATION on a clinically material field. Blank at the
   * document; loud everywhere a human or a gate can read it.
   */
  'denial_withheld',
  /**
   * THE SCAFFOLD'S OWN SENTENCE WAS EVALUATED AND KEPT, RATHER THAN NEVER
   * LOOKED AT.
   *
   * ⚠️ A NEW STATUS WAS REQUIRED, AND THE ENUM ABOVE ALREADY SAYS WHY. The
   * distinguishing fact is that this field CARRIES EVIDENCE and is still blank:
   * the encounter was searched, nothing contradicted the template's pre-printed
   * clause, so the doctor's own default stands. Measured against every existing
   * member:
   *   not_mentioned            `NOT_MENTIONED_HAS_EVIDENCE` is BLOCKING the
   *                            moment `sourceFactIds` is non-empty — which is
   *                            exactly the state this status describes. Reusing
   *                            it means discarding the citation, and the
   *                            citation IS the claim.
   *   approved_practice_default a PRACTICE-wide policy default, chosen by the
   *                            practice. This is the TEMPLATE's own printed
   *                            text, chosen by the doctor who authored the
   *                            form. Different author, different audit trail.
   *   denial_withheld          the encounter DENIED the thing. Here nothing
   *                            denied and nothing affirmed; the default was
   *                            simply not contradicted.
   *   supported                would demand a value and a patch. There is no
   *                            value — the point is that nothing was written.
   *
   * ⚠️ AND THE DISTINCTION IS THE WHOLE CLINICAL CLAIM. "The patient denies
   * chest pain" and "nobody asked about chest pain" must not produce the same
   * proof. Today both render as an untouched scaffold and both earn `blank`,
   * which asserts only that the field was not patched. This status, and the
   * `kept_default` proof kind it drives, separate them — evaluated-and-kept
   * from never-looked-at.
   */
  'default_kept',
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
    // ⚠️ THE INVERSE CONSTRAINT, AND IT IS WHAT GIVES THE STATUS ITS MEANING.
    // Everywhere else evidence is required BECAUSE there is a value. Here it is
    // required because there is NOT one: a kept default with no cited facts is
    // indistinguishable from a field nobody examined, which is the exact
    // conflation this status exists to end. And a value would be a
    // contradiction — nothing was written.
    if (resolution.status === 'default_kept') {
      if (resolution.sourceFactIds.length === 0) {
        ctx.addIssue({
          code: 'custom',
          message:
            'A kept default must cite the facts that were evaluated — without them it is ' +
            'indistinguishable from a field nobody examined',
          path: ['sourceFactIds'],
        });
      }
      if (resolution.value !== null || resolution.selectedOptionOrdinal !== null) {
        ctx.addIssue({
          code: 'custom',
          message: 'A kept default writes nothing: it must carry no value and select no option',
          path: ['value'],
        });
      }
    }
    if (evidenceRequired && resolution.evidenceAnchorIds.length === 0) {
      ctx.addIssue({
        code: 'custom',
        message: 'Every populated clinical value requires evidence anchors',
        path: ['evidenceAnchorIds'],
      });
    }
    // #157(b) — A WITHHELD DENIAL IS BLANK BY CONSTRUCTION, NOT BY CONVENTION.
    // The renderer's `assertResolutionStatus` already refuses a null value that
    // carries an ordinal, but nothing stopped a caller minting this status WITH
    // a value — which would be a denial printing something, through the one
    // status invented to mean the opposite. The schema is the cheapest place to
    // make that unrepresentable, and every producer parses through it.
    if (
      resolution.status === 'denial_withheld' &&
      (resolution.value !== null || resolution.selectedOptionOrdinal !== null)
    ) {
      ctx.addIssue({
        code: 'custom',
        message: 'A withheld denial must carry no value and select no option',
        path: ['value'],
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
  // ⚠️ #157(b) — `denial_withheld` IS COUNTED, IN THE SAME COMMIT THAT
  // INTRODUCES IT. A new status is silently uncounted by default: `filled`
  // counts `value !== null`, so a blank-with-a-reason would land in NO bucket
  // and the manifest's own summary would report a document that is quietly
  // missing a section as though nothing had happened. Rule (3) permits a blank;
  // it forbids a SILENT one, and the counts are where silence would live.
  const unresolved = new Set<FieldResolutionStatus>([
    'ambiguous',
    'conflict',
    'needs_clinician_input',
    'denial_withheld',
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
