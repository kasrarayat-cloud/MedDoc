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
// ⚠️ BUMPED FOR #191. The resolver's output changed for IDENTICAL input
// (`not_mentioned` -> `default_kept`), and `certification-lifecycle` compares
// this string exactly to invalidate stale manifests. Left at 1.0.0 it could not
// see the change, so a manifest produced by the old resolver would have been
// accepted as current. Found by the adversarial pass, not by any arm.
// ⚠️ BUMPED AGAIN. The narrowing changed the resolver's output for IDENTICAL
// input in the other direction (`default_kept` -> `not_mentioned` for every
// non-narrative scaffold), and `certification-lifecycle` compares this string
// exactly to invalidate stale manifests. Leaving it meant every template
// certified before the narrowing kept a certification whose stored manifest no
// longer describes what the resolver produces — this file's own recorded
// failure mode, re-armed by the commit that cites it.
export const TEMPLATE_TWIN_RESOLVER_VERSION = 'template-field-resolver/2.0.0';
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
    /**
     * ⚠️ #191 — IS THIS CONTROL A SCAFFOLD? Non-empty default content that is
     * NOT a Word placeholder. The ruling scopes the whole keep/omit policy to
     * scaffolded controls ("an empty underscore run is not scaffolded; there is
     * nothing to keep or omit"), and the adversarial pass found that scope
     * unimplemented — so `keep` applied to checkboxes and dates alike.
     *
     * ⚠️ `.optional()`, AND ABSENT MEANS **NOT SCAFFOLDED**, WHICH IS
     * FAIL-CLOSED. `structureSha256` hashes `fields`, and every compiled IR
     * already in the database was written before this field existed. Making it
     * REQUIRED would make every stored IR unparseable and invalidate every
     * certification; making absence mean "scaffolded" would let a kept default
     * fire on templates nobody measured. Absent therefore means the compiler
     * that produced this IR could not say, and `default_kept` does not fire.
     *
     * ⚠️ THE DISCRIMINATOR IS A SIGNAL THE DOCUMENT DECLARES, never a text
     * heuristic — canon 83, whose reference case is a rule matching Word's
     * "Choose an item." that blocked 28 of 28 dropdowns of the real customer
     * form. Measured on both real documents: `WM IOV Template.docx` 28
     * controls, 28 declaring `w:showingPlcHdr`, SCAFFOLDED **0**; the owner's
     * regenerated consult form 53 controls, 0 placeholders, SCAFFOLDED **53**,
     * reconciling exactly to the total in both.
     */
    scaffolded: z.boolean().optional(),
    /**
     * ⚠️ #192 — THE SENTENCE THE PROPOSER SHOWS AS ITS REASON. A doctor
     * confirming `keep` is agreeing that this exact text prints when the
     * encounter says nothing, so they must SEE it. Without this the proposal
     * would be "keep this control's content" about content nobody displayed.
     *
     * Blank-template prose, never patient data — the same class as the tracked
     * blank fixtures. Capped, and EXCLUDED from `structureSha256` with
     * `scaffolded`, because both are pure functions of bytes that hash already
     * covers.
     */
    scaffoldText: z.string().max(2000).optional(),
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
    /**
     * ⚠️ #179(3) — THE CLOSED SET OF CONCEPTS THIS SCAFFOLDED CLAUSE COVERS.
     *
     * A scaffolded ROS sentence names specific symptoms — "The patient denies
     * heartburn, odynophagia, dysphagia" covers three and NOT the other eleven
     * in its system. `clinicalConcept` alone cannot express that: it is one
     * concept, and matching on it made every clause in a system interchangeable.
     * Measured consequences before this existed: one affirmed symptom ticked
     * EVERY clause in the system, and two affirmed symptoms conflicted the
     * whole export.
     *
     * ⚠️ MATCHING IS SET MEMBERSHIP, NEVER TEXT. The scope is PROPOSED from the
     * sentence's own words by the mapping proposer and CONFIRMED before use —
     * it is never derived at render. That ordering is the whole safety
     * argument: #157(a–d) falsified three successive attempts to decide
     * clinical meaning from prose at render time, and #157(d) deleted the
     * machinery rather than gate it.
     *
     * Empty means "not a scaffolded clause" — ordinary `clinicalConcept`
     * matching applies, unchanged.
     * ⚠️ OPTIONAL, NOT `.default([])`, AND THE FALLBACK IS SAFE NOW. Absent
     * means "not a scaffolded clause" and ordinary `clinicalConcept` matching
     * applies — which is no longer the old defect, because #179(2) made the
     * concepts themselves symptom-granular. A clause mapped to
     * `ros.gastrointestinal.heartburn` already matches only heartburn. The
     * scope exists for a sentence covering SEVERAL symptoms at once.
     */
    conceptScope: z.array(z.string().min(1).max(160)).max(64).optional(),
    required: z.boolean(),
    blankPolicy: z.enum(['blank', 'not_documented', 'requires_input']),
    unknownPolicy: z.enum(['blank', 'not_documented', 'requires_input']),
    /**
     * ⚠️ `.nullish()`, NEVER `.default(...)`. `z.infer` gives the OUTPUT type,
     * where a defaulted field is REQUIRED — which made every hand-built
     * `SemanticMapping` fixture in the suite a type error, for a field none of
     * them care about.
     *
     * ⚠️ AND ABSENCE MEANS THE BOUNDED CLEAR, NOT KEEP — #192. The #191 wording
     * here said the opposite, because `keep` was then the column's default and
     * the two were interchangeable. They are opposites now: the resolver
     * requires `=== 'keep'`, and a column that is NULL is a control nobody
     * ruled on, which must never print.
     */
    /**
     * ⚠️ #194 — THERE IS NO `'keep'`. NULL is the bounded clear COUNTED as
     * still blank (the doctor is told); `'omit'` is the bounded clear NOT
     * counted and with no prompt (the telehealth consent line).
     *
     * The keep half was deleted after its PREMISE was refuted, not merely its
     * mechanism: it fired when NO fact carried the field's concept, and concept
     * equality is the only test performed anywhere, so "nothing contradicted
     * this" was always a claim about the empty set. Measured — a scaffold
     * reading "no varicosities, no oedema and no ulceration" was kept on a
     * visit dictated as a large weeping ulcer with oedema and varicosities.
     * The machine never prints an undictated default.
     */
    unmentionedPolicy: z.literal('omit').nullish(),
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
        /**
         * #247 — A VALUE TAKEN FROM THE PATIENT RECORD, NOT FROM THE DICTATION.
         *
         * Its own class rather than a reuse, and per-visit by construction:
         * `approved_practice_default` is PRACTICE-wide, and a patient's name is
         * not a property of a practice.
         *
         * ⚠️ PROVENANCE IS THE WHOLE POINT. The fill path is built on cited
         * evidence, so a record value that borrowed `encounter_evidence` would
         * make the frozen manifest say the doctor SAID it. That is not
         * hypothetical — `withProcedureDateFact` did exactly that until this
         * value existed, and the manifest recorded the visit date as dictated.
         */
        'visit_record',
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
  /**
   * #247 — THE VALUE CAME OFF THE PATIENT RECORD, AND THE RESOLUTION SAYS SO.
   *
   * ⚠️ IT IS POPULATED, LIKE `supported`, AND IT IS NOT `supported`. Both put a
   * value on the document and both cite facts. What separates them is the only
   * question a reader of a signed note actually asks: *did the clinician say
   * this?* A patient's name printed on a consult letter was read out of the
   * chart, and a manifest reporting it as `supported` beside a dictated
   * assessment makes those two indistinguishable at the one place the
   * distinction is recoverable.
   *
   * Measured against every existing member before it was added:
   *   supported                 asserts DICTATED support. That is the claim
   *                             being corrected, so it cannot be the carrier.
   *   approved_practice_default a PRACTICE-wide policy value the practice
   *                             approved once. This is PER-VISIT and belongs to
   *                             one patient — `approved_practice_default` is
   *                             refused for family 3 in the ruling itself, for
   *                             exactly that reason.
   *   not_mentioned             NOT_MENTIONED_HAS_EVIDENCE is blocking the
   *                             moment a citation exists, and this citation is
   *                             the point.
   *
   * ⚠️ AND THE SOURCE OF TRUTH IS THE FACT, NEVER THIS STATUS. The resolver
   * derives it from `sourceType === 'visit_record'` on the cited facts and the
   * validator re-derives it independently, in both directions — so a
   * `record_derived` resolution citing dictation, and a `supported` resolution
   * citing the record, are both BLOCKING. A label nothing checks is decoration.
   */
  'record_derived',
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
        /**
         * ⚠️ #194 — RULED-BLANK FIELDS, COUNTED SEPARATELY SO THEY ARE NEITHER
         * REPORTED AS UNDICTATED NOR SILENTLY UNCOUNTED. `.optional()` so every
         * manifest already persisted still parses.
         */
        omitted: z.number().int().nonnegative().optional(),
        /**
         * ⚠️ #247 — RECORD-DERIVED FILLS, COUNTED SEPARATELY BECAUSE `filled`
         * CANNOT TELL THE DOCTOR WHICH ONES HE SAID. They are a SUBSET of
         * `filled`, not a sibling bucket, so nothing double-counts and nothing
         * falls into no bucket.
         *
         * ⚠️ `.optional()` AND EMITTED ONLY WHEN NON-ZERO — a deliberate
         * departure from `omitted`, which is always emitted. The sign gate
         * re-verifies a STORED manifest by recomputing these counts and
         * comparing shas (`certification-lifecycle.ts`), so a key that appears
         * unconditionally changes the recomputed sha of every manifest already
         * on disk and fails a document nobody touched. Zero record-derived
         * fills therefore produces byte-identical counts to before this
         * existed.
         */
        recordDerived: z.number().int().nonnegative().optional(),
        conflicts: z.number().int().nonnegative(),
        criticalUnresolved: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .strict();
export type TemplateTwinFillManifest = z.infer<typeof TemplateTwinFillManifestSchema>;

// ══ #272 — THE RECORD-DERIVED REFUSAL VOCABULARY, IN ONE PLACE ═════════════
//
// A record-derived value is one the PATIENT RECORD supplies — a name, an age.
// When the record cannot supply it, the field is blank for a NAMED reason, and
// ruling #272 says that blank must never withhold the document:
//
//   A WITHHELD CONSULT OVER ONE AMBIGUOUS AGE IS THE WRONG TRADE.
//   A DOCTOR TYPING "61" IS THE RIGHT ONE.
//
// ⚠️ IT LIVES HERE, AND NOT BESIDE THE INJECTOR, BECAUSE IT HAS THREE READERS
// AND A RULE WITH THREE READERS DRIFTS. The resolver knows a refusal by the
// CHANNEL it arrived on; `validation/index.ts` sees only a status and a
// reasonCode and must reach the same verdict; and the injector is where the
// tokens are minted. `ir.ts` is the module all three already import, so the
// list is shared rather than copied.
//
// ⚠️ AND THE DRIFT IS ARMED, NOT TRUSTED: `gate-272` asserts that every reason
// the injector can emit is a member of this set. Adding a refusal reason
// without adding it here would otherwise produce a blank that silently blocks
// the document again — the exact regression #272 exists to end, arriving
// through the one door nobody watches.
export const RECORD_DERIVED_REFUSAL_REASONS = [
  'age_input_absent',
  'age_unparseable',
  'age_implausible',
  'age_timezone_ambiguous',
] as const;

export type RecordDerivedRefusalReason = (typeof RECORD_DERIVED_REFUSAL_REASONS)[number];

/** Is this reasonCode a record-derived refusal? The ONE reader of the list. */
export function isRecordDerivedRefusal(reasonCode: string | null | undefined): boolean {
  if (!reasonCode) return false;
  return (RECORD_DERIVED_REFUSAL_REASONS as readonly string[]).includes(reasonCode);
}

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
  // #247 — see the schema comment: PRESENT ONLY WHEN NON-ZERO, so a manifest
  // stored before this status existed recomputes to the same sha.
  const recordDerived = fields.filter(
    (field) => field.status === 'record_derived',
  ).length;
  return {
    filled: fields.filter((field) => field.value !== null).length,
    ...(recordDerived > 0 ? { recordDerived } : {}),
    needsReview: fields.filter((field) => unresolved.has(field.status)).length,
    // ⚠️ #194 — AN `omit` IS NOT COUNTED, AND A NULL POLICY IS. Both take the
    // bounded clear, so the PAGE is identical; the difference is what the doctor
    // is told. A NULL policy is a field nobody ruled on, and it must appear in
    // "N still blank — nothing dictated for those yet" so the blank is visible.
    // An `omit` was RULED blank — the telehealth consent line on an in-person
    // visit — so prompting about it every time is noise about a decision
    // already made.
    //
    // ⚠️ THE COUNT MUST NOT SILENTLY SWALLOW EITHER. `default_kept` fell into no
    // bucket once and one unrelated dictated sentence collapsed a form's blank
    // count 11 -> 0; the reconciliation arm exists because of that.
    // ⚠️ #194 — A RULED `omit` IS NOT COUNTED; EVERY OTHER BLANK IS. Both take
    // the bounded clear, so the PAGE is identical and the difference is only
    // what the doctor is told. A NULL policy is a field nobody ruled on and
    // must appear in "N still blank — nothing dictated for those yet", so the
    // blank stays visible. An `omit` was RULED blank — the telehealth consent
    // line on an in-person visit — and prompting about it every visit is noise
    // about a decision already made.
    //
    // ⚠️ NOTHING MAY FALL INTO NO BUCKET. `default_kept` did exactly that once,
    // and one unrelated dictated sentence collapsed a form's blank count from
    // 11 to 0 with the document byte-identical. The reconciliation arm exists
    // because of that, and it counts the omitted set explicitly rather than
    // letting it vanish.
    notMentioned: fields.filter(
      (field) =>
        field.status === 'not_mentioned' &&
        field.reasonCode !== 'omitted_unsupported_default',
    ).length,
    omitted: fields.filter(
      (field) => field.reasonCode === 'omitted_unsupported_default',
    ).length,
    conflicts: fields.filter((field) => field.status === 'conflict').length,
    criticalUnresolved: fields.filter(
      (field) =>
        unresolved.has(field.status) &&
        critical.get(field.fieldId) !== undefined &&
        critical.get(field.fieldId) !== 'routine',
    ).length,
  };
}
