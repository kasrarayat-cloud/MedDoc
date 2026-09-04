// ============================================================================
// Template Twin — independent pre-render / pre-sign validator
// ----------------------------------------------------------------------------
// This module does not trust resolver status. It independently checks field
// cardinality, mapping certification, exact enums, checkbox polarity, numeric
// and unit fidelity, laterality, dates, medication/allergy evidence, table
// shape, unsupported elements, and source-anchor coverage.
// ============================================================================

import {
  EncounterFactSchema,
  FieldResolutionSchema,
  FieldValidationIssueSchema,
  SemanticMappingSchema,
  TemplateFieldSchema,
  TemplateTableSchema,
  TemplateTwinValidationResultSchema,
  UnsupportedElementSchema,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateField,
  type TemplateTable,
  type UnsupportedElement,
  type TemplateTwinValidationResult,
} from '../ir';
import { parseExplicitNumberAndUnit } from '../encounter-facts';
import {
  deriveFieldValueFromFact,
  exactOption,
  isStrictIsoDate,
  isListValuedNarrative,
  joinListValuedNarrative,
} from '../field-value-derivation';
import { isMappingTypeCompatible } from '../semantic-mapping';
import {
  denialOutcome,
  mixedPolarityNarrative,
  MIXED_POLARITY_REASON,
} from '../denial-contract';
import {
  approvedPracticeDefaultAnchorId,
  approvedPracticeDefaultFactId,
} from '../practice-default';

export const TEMPLATE_TWIN_VALIDATOR_VERSION =
  'template-field-validator/1.0.0';

interface ValidationIssue {
  fieldId: string | null;
  code: string;
  severity: 'warning' | 'blocking';
  message: string;
}

export interface ValidateTemplateTwinInput {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  resolutions: ReadonlyArray<FieldResolution>;
  tables?: ReadonlyArray<TemplateTable>;
  unsupported?: ReadonlyArray<UnsupportedElement>;
  /** Exact field IDs certified in mutable lifecycle rows for this immutable
   * compiled IR. */
  certifiedFieldIds?: ReadonlyArray<string>;
  /** Allows the certification test renderer to exercise proposed mappings. */
  allowUncertifiedForSyntheticTest?: boolean;
  now?: Date | string;
}

interface RowValue {
  value: string;
  sourceFactId: string;
  evidenceAnchorId: string | null;
  optionOrdinal: string | null;
}

function normalizeConcept(value: string): string {
  return value.normalize('NFKC').trim().toLocaleLowerCase('en-US');
}

function isRowValueArray(value: FieldResolution['value']): value is Array<Record<string, string | null>> {
  return (
    Array.isArray(value) &&
    value.every(
      (entry) =>
        typeof entry === 'object' &&
        entry !== null &&
        !Array.isArray(entry),
    )
  );
}

function parseRowValue(entry: Record<string, string | null>): RowValue | null {
  const allowedKeys = new Set([
    'value',
    'sourceFactId',
    'evidenceAnchorId',
    'optionOrdinal',
  ]);
  if (
    Object.keys(entry).some((key) => !allowedKeys.has(key)) ||
    typeof entry.value !== 'string' ||
    typeof entry.sourceFactId !== 'string' ||
    !('evidenceAnchorId' in entry) ||
    (entry.evidenceAnchorId !== null &&
      typeof entry.evidenceAnchorId !== 'string') ||
    !('optionOrdinal' in entry) ||
    (entry.optionOrdinal !== null && typeof entry.optionOrdinal !== 'string')
  ) {
    return null;
  }
  return {
    value: entry.value,
    sourceFactId: entry.sourceFactId,
    evidenceAnchorId: entry.evidenceAnchorId,
    optionOrdinal: entry.optionOrdinal,
  };
}

// isStrictIsoDate, exactOption and the value derivation now live in
// ../field-value-derivation, because the BRIDGE has to produce exactly what
// this module re-derives and was producing something else. See that file's
// header.
//
// ⚠️ "MOVED VERBATIM" IS TRUE OF TWO OF THE THREE, AND THE THIRD IS STATED
// EXACTLY RATHER THAN ROUNDED. `isStrictIsoDate` and `exactOption` are
// byte-identical (measured by comparing normalised function bodies against
// origin/main). `valueFromFact` -> `deriveFieldValueFromFact` gained exactly
// ONE line, `if (!mapping) return null;` in the `measurement` branch, because
// its `mapping` parameter is now optional for the bridge's sake.
//
// THAT LINE IS UNREACHABLE FROM THIS FILE, and it is structural rather than a
// hope: validateTemplateTwin `continue`s on a missing mapping with
// MAPPING_MISSING well before assertionSupported is ever called, so every call
// site here passes a defined mapping. The validator's behaviour is therefore
// unchanged — but it is unchanged BECAUSE of that, not because nothing moved.

function practiceDefaultMatches(
  field: TemplateField,
  mapping: SemanticMapping,
  value: FieldResolution['value'],
): boolean {
  if (mapping.practiceDefault === null || value === null || Array.isArray(value)) {
    return false;
  }
  const raw = mapping.practiceDefault;
  switch (field.kind) {
    case 'narrative_text':
      return typeof value === 'string' && value === raw;
    case 'single_select':
      return (
        typeof value === 'string' &&
        exactOption(field, raw)?.value === value
      );
    case 'multi_select':
      return false;
    case 'checkbox':
      return (
        typeof value === 'boolean' &&
        (raw === 'true' || raw === 'false') &&
        value === (raw === 'true')
      );
    case 'date':
      return typeof value === 'string' && isStrictIsoDate(raw) && value === raw;
    case 'number': {
      const parsed = parseExplicitNumberAndUnit(raw);
      return (
        typeof value === 'number' &&
        parsed.unit === null &&
        parsed.number === value
      );
    }
    case 'measurement': {
      const parsed = parseExplicitNumberAndUnit(raw);
      if (parsed.number === null) return false;
      if (mapping.unitPolicy === 'required' && parsed.unit === null) return false;
      if (mapping.unitPolicy === 'forbidden' && parsed.unit !== null) return false;
      return value === (parsed.unit ? `${parsed.number} ${parsed.unit}` : parsed.number);
    }
  }
}

/**
 * ⚠️ EXPORTED SO AN ARM CAN DRIVE IT RATHER THAN RE-IMPLEMENT IT. It is a pure
 * predicate over a fact and a mapping; exporting changes no behaviour. The
 * alternative was an arm that reproduced this rule inline, which is a control
 * that reimplements its subject — it passes whatever the shipped matcher does.
 */
export function factMatchesMapping(
  fact: EncounterFact,
  mapping: SemanticMapping,
): boolean {
  // ⚠️ #179(3) — A DECLARED SCOPE MATCHES BY SET MEMBERSHIP, AND IT IS CHECKED
  // FIRST. A scaffolded clause covers a named set of symptom concepts; a fact
  // satisfies it only by being IN that set. No text is compared, at render or
  // anywhere else.
  //
  // ⚠️ THE SCOPE DOES NOT WIDEN `clinicalConcept` — IT REPLACES IT for these
  // fields. Falling through to the concept check as well would let a
  // system-level concept satisfy a clause that scopes three of its fourteen
  // symptoms, which is the defect this exists to end.
  if (mapping.conceptScope && mapping.conceptScope.length > 0) {
    const scope = new Set(mapping.conceptScope.map(normalizeConcept));
    if (!scope.has(normalizeConcept(fact.concept))) return false;
    return temporalityMatches(fact, mapping);
  }
  if (!mapping.clinicalConcept) return false;
  const concepts = new Set(
    [mapping.clinicalConcept, ...mapping.approvedSynonyms].map(normalizeConcept),
  );
  if (!concepts.has(normalizeConcept(fact.concept))) return false;
  return temporalityMatches(fact, mapping);
}

/**
 * ⚠️ ONE IMPLEMENTATION, SHARED BY BOTH MATCH PATHS. A second copy would drift
 * the day either is fixed, and a scoped clause silently accepting a different
 * tense from an unscoped one is the kind of divergence nothing would report.
 *
 * ⚠️ AND A NULL MAPPING TEMPORALITY MEANS `current`, NOT `any` — #179(6). The
 * shipped compiler emits null for scaffolded clauses, and the refutation pass
 * demonstrated that a HISTORICAL, resolved symptom then matched a
 * present-tense sentence. "The patient denies chest pain" must not be
 * contradicted by chest pain the patient had in 2019.
 */
function temporalityMatches(
  fact: EncounterFact,
  mapping: SemanticMapping,
): boolean {
  if (mapping.temporality === 'any') return true;
  const want = mapping.temporality ?? 'current';
  return fact.temporality === want;
}

/** Returns true only when the output can be re-derived from cited facts. */
function assertionSupported(
  field: TemplateField,
  mapping: SemanticMapping,
  resolution: FieldResolution,
  citedFacts: ReadonlyArray<EncounterFact>,
): boolean {
  const value = resolution.value;
  if (value === null) return true;

  // ══ OWNER RULING #157(b) — A DENIAL IS RE-DERIVED, NOT RE-DESCRIBED. ══════
  //
  // ⚠️ THE EXISTING RAIL CANNOT VERIFY A DENIAL, AND THAT IS MEASURED, NOT
  // ASSUMED. `deriveFieldValueFromFact` returns `fact.value` for a
  // narrative_text — the AFFIRMED ENTITY. So the rail below refuses the
  // doctor's own sentence with ASSERTION_NOT_SUPPORTED (blocking) and ACCEPTS
  // the entity. Driven end to end through the real compiler -> resolver ->
  // validator -> awaited renderer:
  //
  //   value "The patient has no history of diabetes."  -> valid=false, blocked
  //   value "Diabetes"                                 -> valid=true, RENDERED
  //
  // The second row is the harm: a signed past-medical-history section reading
  // "Diabetes" for a patient who was said not to have it, with nothing
  // blocking. So a denial is verified against `denialOutcome` — the SAME
  // function the resolver wrote it with, given the same field and mapping —
  // and the two cannot disagree without one of them being edited.
  //
  // ⚠️ #157(d) TOOK THE CITED FACTS AWAY FROM THAT FUNCTION ENTIRELY, WHICH IS
  // RULE (1) AS A STRUCTURAL PROPERTY RATHER THAN A DESCRIBED ONE. A function
  // that cannot see the dictation cannot decide anything from its text, so
  // there is no heuristic left here to be defeated by the next sentence
  // somebody dictates. This is a TIGHTENING: it is byte-identity against a shared
  // derivation, exactly like the list-valued narrative case below, and it does
  // not widen what the affirmed path accepts by a single character.
  if (resolution.status === 'explicitly_denied') {
    const expected = denialOutcome(field, mapping);
    return expected.status === 'explicitly_denied' && expected.value === value;
  }

  // ══ #157(c) Q3 — A MIXED-POLARITY NARRATIVE IS RE-DERIVED, NOT RE-DESCRIBED.
  //
  // Same shape as the denial branch above and for the same reason: the resolver
  // COMPOSES this value from several facts, and the only honest verification is
  // byte-identity against the SAME function that composed it. `citedFacts` is in
  // `sourceFactIds` order — which is the resolver's `judged` order, which is
  // DICTATION order — so the re-derivation reproduces the segments in the same
  // sequence or it does not reproduce them at all.
  //
  // ⚠️ A REFUSAL FALLS THROUGH RATHER THAN RETURNING FALSE. If no legal mixed
  // path could have produced this value, the existing rails judge it exactly as
  // they always have. Inventing a new way to REFUSE inside a slice about not
  // refusing is how a fix becomes the next incident.
  const citedPolarities = new Set(citedFacts.map((fact) => fact.polarity));
  if (
    field.kind === 'narrative_text' &&
    !field.rowPrototype &&
    citedPolarities.has('affirmed') &&
    citedPolarities.has('denied')
  ) {
    const expected = mixedPolarityNarrative(field, mapping, citedFacts);
    if (expected.kind === 'text') return expected.text === value;
  }

  if (field.rowPrototype) {
    if (!isRowValueArray(value)) return false;
    return value.every((rawEntry) => {
      const entry = parseRowValue(rawEntry);
      if (!entry) return false;
      const fact = citedFacts.find((candidate) => candidate.factId === entry.sourceFactId);
      if (!fact || !factMatchesMapping(fact, mapping)) return false;
      if (
        entry.evidenceAnchorId === null ||
        !fact.evidenceAnchorIds.includes(entry.evidenceAnchorId)
      ) {
        return false;
      }
      const derived = deriveFieldValueFromFact(field, mapping, fact);
      if (derived === null || entry.value !== String(derived)) return false;
      if (field.kind === 'single_select') {
        const option = exactOption(field, entry.value);
        if (!option || entry.optionOrdinal !== String(option.ordinal)) return false;
      }
      return true;
    });
  }

  if (field.kind === 'multi_select') {
    if (!Array.isArray(value) || value.some((entry) => typeof entry !== 'string')) {
      return false;
    }
    return value.every((selected) =>
      citedFacts.some(
        (fact) =>
          factMatchesMapping(fact, mapping) &&
          deriveFieldValueFromFact(field, mapping, fact) === selected,
      ),
    );
  }

  // A list-valued narrative section is re-derived AS A WHOLE: the joined value
  // must be exactly what the shared composer produces from these same cited
  // facts, in this same order. Built from one function so the build side and
  // this verify side cannot drift -- the defect this module was created for.
  // ⚠️ GATED ON MORE THAN ONE CITED FACT, DELIBERATELY. `joinListValuedNarrative`
  // TRIMS, so applying it to a single-fact narrative would accept a resolution
  // whose value merely trims to the cited fact -- relaxing the byte-identity this
  // module exists to enforce ("the document carries the CITED FACT'S value...
  // this is a TIGHTENING, not a loosening"). A one-fact section takes the
  // unchanged strict path below.
  if (citedFacts.length > 1 && isListValuedNarrative(field, mapping)) {
    const joined = joinListValuedNarrative(field, mapping, citedFacts);
    if (
      joined !== null &&
      joined === value &&
      citedFacts.every((fact) => factMatchesMapping(fact, mapping))
    ) {
      return true;
    }
  }

  return citedFacts.some(
    (fact) =>
      factMatchesMapping(fact, mapping) &&
      deriveFieldValueFromFact(field, mapping, fact) === value,
  );
}

export function validateTemplateTwin(
  input: ValidateTemplateTwinInput,
): TemplateTwinValidationResult {
  const issues: ValidationIssue[] = [];
  const add = (
    code: string,
    severity: 'warning' | 'blocking',
    message: string,
    fieldId: string | null = null,
  ): void => {
    issues.push(
      FieldValidationIssueSchema.parse({ fieldId, code, severity, message }),
    );
  };

  const fields: TemplateField[] = [];
  for (const raw of input.fields) {
    const parsed = TemplateFieldSchema.safeParse(raw);
    if (parsed.success) fields.push(parsed.data);
    else add('FIELD_SCHEMA_INVALID', 'blocking', 'A compiled field definition is invalid.');
  }
  const mappings: SemanticMapping[] = [];
  for (const raw of input.mappings) {
    const parsed = SemanticMappingSchema.safeParse(raw);
    if (parsed.success) mappings.push(parsed.data);
    else add('MAPPING_SCHEMA_INVALID', 'blocking', 'A semantic mapping is invalid.');
  }
  const facts: EncounterFact[] = [];
  for (const raw of input.facts) {
    const parsed = EncounterFactSchema.safeParse(raw);
    if (parsed.success) facts.push(parsed.data);
    else add('FACT_SCHEMA_INVALID', 'blocking', 'An encounter fact is invalid.');
  }
  const resolutions: FieldResolution[] = [];
  for (const raw of input.resolutions) {
    const parsed = FieldResolutionSchema.safeParse(raw);
    if (parsed.success) resolutions.push(parsed.data);
    else add('RESOLUTION_SCHEMA_INVALID', 'blocking', 'A field resolution is invalid.');
  }
  const tables: TemplateTable[] = [];
  for (const raw of input.tables ?? []) {
    const parsed = TemplateTableSchema.safeParse(raw);
    if (parsed.success) tables.push(parsed.data);
    else add('TABLE_SCHEMA_INVALID', 'blocking', 'A compiled table definition is invalid.');
  }
  const unsupported: UnsupportedElement[] = [];
  for (const raw of input.unsupported ?? []) {
    const parsed = UnsupportedElementSchema.safeParse(raw);
    if (parsed.success) unsupported.push(parsed.data);
    else add('UNSUPPORTED_REGISTER_INVALID', 'blocking', 'The unsupported-element register is invalid.');
  }

  for (const element of unsupported) {
    add(
      element.code,
      element.blocksCertification || element.clinicallyMaterial
        ? 'blocking'
        : 'warning',
      element.blocksCertification || element.clinicallyMaterial
        ? 'A clinically material or certification-blocking document element is unsupported.'
        : 'A non-clinical document element is unsupported.',
    );
  }

  const fieldIds = new Set(fields.map((field) => field.fieldId));
  if (fieldIds.size !== fields.length) {
    add('DUPLICATE_FIELD_DEFINITION', 'blocking', 'The compiled field set contains duplicate field IDs.');
  }
  const mappingById = new Map<string, SemanticMapping>();
  for (const mapping of mappings) {
    if (mappingById.has(mapping.fieldId)) {
      add('DUPLICATE_MAPPING', 'blocking', 'A field has more than one semantic mapping.', mapping.fieldId);
    } else {
      mappingById.set(mapping.fieldId, mapping);
    }
    if (!fieldIds.has(mapping.fieldId)) {
      add('UNKNOWN_MAPPING_FIELD', 'blocking', 'A semantic mapping references an unknown field.', mapping.fieldId);
    }
  }
  const resolutionById = new Map<string, FieldResolution>();
  for (const resolution of resolutions) {
    if (resolutionById.has(resolution.fieldId)) {
      add('DUPLICATE_RESOLUTION', 'blocking', 'A field has more than one resolution.', resolution.fieldId);
    } else {
      resolutionById.set(resolution.fieldId, resolution);
    }
    if (!fieldIds.has(resolution.fieldId)) {
      add('UNKNOWN_RESOLUTION_FIELD', 'blocking', 'A resolution references an unknown field.', resolution.fieldId);
    }
  }

  const factById = new Map<string, EncounterFact>();
  for (const fact of facts) {
    if (factById.has(fact.factId)) {
      add('DUPLICATE_FACT', 'blocking', 'The encounter fact set contains duplicate fact IDs.');
    } else {
      factById.set(fact.factId, fact);
    }
  }
  const tableById = new Map(tables.map((table) => [table.tableId, table]));
  const certifiedFieldIds = new Set(input.certifiedFieldIds ?? []);
  const repeatedCountsByTable = new Map<string, number>();
  const repeatedAnchorsByTable = new Map<string, string[]>();

  for (const field of fields) {
    const mapping = mappingById.get(field.fieldId);
    const resolution = resolutionById.get(field.fieldId);
    if (!mapping) {
      add('MAPPING_MISSING', 'blocking', 'The field has no semantic mapping.', field.fieldId);
      continue;
    }
    if (!resolution) {
      add('RESOLUTION_MISSING', 'blocking', 'The field has no field resolution.', field.fieldId);
      continue;
    }
    if (!isMappingTypeCompatible(field, mapping)) {
      add('MAPPING_TYPE_MISMATCH', 'blocking', 'The mapping data type does not match the compiled control.', field.fieldId);
    }
    if (
      !input.allowUncertifiedForSyntheticTest &&
      (mapping.status !== 'certified' ||
        (field.detectionStatus !== 'certified' &&
          !certifiedFieldIds.has(field.fieldId)))
    ) {
      add('FIELD_NOT_CERTIFIED', 'blocking', 'The field structure and semantic mapping are not certified.', field.fieldId);
    }
    if (mapping.status === 'unsupported' || field.detectionStatus === 'unsupported') {
      add('FIELD_UNSUPPORTED', field.clinicallyMaterial ? 'blocking' : 'warning', 'The field is unsupported.', field.fieldId);
    }

    const citedFacts: EncounterFact[] = [];
    for (const factId of resolution.sourceFactIds) {
      const fact = factById.get(factId);
      if (!fact) {
        add('SOURCE_FACT_MISSING', 'blocking', 'A resolution cites a missing encounter fact.', field.fieldId);
      } else {
        citedFacts.push(fact);
      }
    }
    const citedAnchorSet = new Set(resolution.evidenceAnchorIds);
    const factAnchorSet = new Set(citedFacts.flatMap((fact) => fact.evidenceAnchorIds));
    if (citedFacts.some((fact) => fact.evidenceAnchorIds.some((id) => !citedAnchorSet.has(id)))) {
      add('EVIDENCE_COVERAGE_INCOMPLETE', 'blocking', 'Not every cited fact anchor is retained by the resolution.', field.fieldId);
    }
    if (resolution.evidenceAnchorIds.some((id) => !factAnchorSet.has(id))) {
      add('EVIDENCE_ANCHOR_UNTRACEABLE', 'blocking', 'A resolution anchor is not traceable to a cited fact.', field.fieldId);
    }

    const populated = resolution.value !== null;
    // #157(b) — `denial_withheld` joins this set so UNRESOLVED_VALUE_PRESENT
    // covers it: the one status that MEANS "blank" must never be found holding
    // a value. `ir.ts`'s schema already refuses that shape, so this is the
    // second wall rather than the first.
    const unresolved = new Set([
      'ambiguous',
      'conflict',
      'needs_clinician_input',
      'denial_withheld',
    ]);
    if (populated && unresolved.has(resolution.status)) {
      add('UNRESOLVED_VALUE_PRESENT', 'blocking', 'An unresolved field contains a renderable value.', field.fieldId);
    }
    if (
      populated &&
      (resolution.sourceFactIds.length === 0 || resolution.evidenceAnchorIds.length === 0)
    ) {
      add('POPULATED_WITHOUT_EVIDENCE', 'blocking', 'A populated clinical value lacks evidence.', field.fieldId);
    }
    if (
      resolution.status === 'not_mentioned' &&
      (resolution.sourceFactIds.length > 0 || resolution.evidenceAnchorIds.length > 0)
    ) {
      add('NOT_MENTIONED_HAS_EVIDENCE', 'blocking', 'A not-mentioned field unexpectedly retains clinical evidence.', field.fieldId);
    }
    if (citedFacts.some((fact) => !factMatchesMapping(fact, mapping))) {
      add('SOURCE_FACT_CONCEPT_MISMATCH', 'blocking', 'A cited fact does not match the approved semantic mapping.', field.fieldId);
    }

    if (resolution.status === 'approved_practice_default') {
      const defaultFact = citedFacts[0];
      const expectedDefaultFactId = approvedPracticeDefaultFactId(field, mapping);
      const expectedDefaultAnchorId = approvedPracticeDefaultAnchorId(
        field,
        expectedDefaultFactId,
      );
      if (
        citedFacts.length !== 1 ||
        defaultFact?.sourceType !== 'approved_practice_default' ||
        defaultFact?.factId !== expectedDefaultFactId ||
        defaultFact?.value !== mapping.practiceDefault ||
        defaultFact?.sourceTranscriptOffsets !== null ||
        defaultFact?.audioTimestampSeconds !== null ||
        defaultFact?.evidenceAnchorIds.length !== 1 ||
        defaultFact?.evidenceAnchorIds[0] !== expectedDefaultAnchorId ||
        resolution.sourceFactIds.length !== 1 ||
        resolution.sourceFactIds[0] !== expectedDefaultFactId ||
        resolution.evidenceAnchorIds.length !== 1 ||
        resolution.evidenceAnchorIds[0] !== expectedDefaultAnchorId ||
        mapping.status !== 'certified' ||
        !practiceDefaultMatches(field, mapping, resolution.value)
      ) {
        add('PRACTICE_DEFAULT_INVALID', 'blocking', 'The practice default is missing approval, provenance evidence, or an exact resolved value.', field.fieldId);
      }
    } else if (populated && !assertionSupported(field, mapping, resolution, citedFacts)) {
      add('ASSERTION_NOT_SUPPORTED', 'blocking', 'The populated value cannot be re-derived from its cited facts.', field.fieldId);
    }

    if (
      resolution.status === 'supported' &&
      citedFacts.some((fact) => fact.quality.evidence !== 'direct')
    ) {
      add('SUPPORTED_STATUS_CONFLICTS_WITH_QUALITY', 'blocking', 'A supported field cites unclear or conflicting evidence.', field.fieldId);
    }

    const critical = field.criticality !== 'routine' || field.clinicallyMaterial;
    if (resolution.status === 'conflict') {
      add('FIELD_CONFLICT', 'blocking', 'The field contains conflicting encounter evidence.', field.fieldId);
    } else if (resolution.status === 'ambiguous') {
      add('FIELD_AMBIGUOUS', critical || field.required || mapping.required ? 'blocking' : 'warning', 'The field evidence is ambiguous.', field.fieldId);
    } else if (resolution.status === 'needs_clinician_input') {
      // AT CERTIFICATION ONLY, this is a warning rather than a blocker.
      //
      // Certification asks "does this template fill correctly from evidence?",
      // not "did a clinician sit down and answer every prompt?". A field the
      // resolver deliberately refuses to infer — an enumerated DIAGNOSIS, say —
      // is CORRECT behaviour, and the field stays BLANK either way. It is
      // attested as a blank-proof carrying this reason, so the certificate says
      // exactly what happened rather than hiding it.
      //
      // AT VISIT TIME the severity is unchanged: a clinically material field
      // needing input still blocks, because there the question really is
      // whether the clinician answered. Both directions are test-pinned.
      const needsInputBlocks =
        !input.allowUncertifiedForSyntheticTest &&
        (critical || field.required || mapping.required);
      add('FIELD_NEEDS_CLINICIAN_INPUT', needsInputBlocks ? 'blocking' : 'warning', 'The field needs clinician input.', field.fieldId);
    } else if (resolution.status === 'denial_withheld') {
      // ══ #157(b) RULE (3) — NO DENIAL MAY REFUSE AN EXPORT. ════════════════
      //
      // ⚠️ A WARNING **UNCONDITIONALLY** — not "unless critical", not "unless
      // required". Every conditional severity in this function is a route back
      // to the harm this ruling ends: FIELD_AMBIGUOUS blocks when
      // `critical || field.required || mapping.required`, and that clause alone
      // is why a `value_only` denial on a clinically material narrative took
      // the doctor's whole document down. A field left blank is a field left
      // blank; refusing the OTHER hundred and forty-nine fields does not fill
      // it.
      //
      // ⚠️ AND THE SILENCE RULE IS SATISFIED ELSEWHERE, DELIBERATELY, BECAUSE A
      // WARNING IS EASY TO SKIM. The blank is named in THREE durable places, so
      // no single reader has to notice this line:
      //   · `resolution.reasonCode` — the manifest's own field-level token,
      //     persisted to `template_twin_fill_manifests`;
      //   · `counts.needsReview` / `counts.criticalUnresolved` — `ir.ts`'s
      //     `templateTwinCounts`, widened in the same commit;
      //   · ⚠️ NOT a certification blocker for a NARRATIVE denial — #157(d) Q2
      //     exempts `denial_withheld_narrative_always_blank` by name, so the two
      //     DURABLE places are the reason token and the counts. This comment
      //     used to say the opposite, and it was falsified in the same commit
      //     that made the narrative blank unconditional. It still holds for the
      //     NON-exempt tokens —
      //     `denialWithheldMaterialFieldIds`, which is what stops a template
      //     certifying green with a material section quietly empty.
      //
      // That last one is the reason this is not `needs_clinician_input`: that
      // status is DOWNGRADED to a warning at certification by
      // `allowUncertifiedForSyntheticTest`, so reusing it would have bought the
      // non-blocking export at the price of a certificate that lies.
      add('FIELD_DENIAL_WITHHELD', 'warning', 'The field is blank because the encounter denied it.', field.fieldId);
      if (
        citedFacts.length === 0 ||
        citedFacts.some((fact) => fact.polarity !== 'denied')
      ) {
        // The status asserts "this blank is a DENIAL". An uncited or
        // non-denied citation makes that assertion false, and a false reason
        // in the manifest is worse than no reason — it is the audit trail
        // saying something the evidence does not.
        add('DENIAL_WITHHELD_WITHOUT_DENIAL', 'blocking', 'A withheld denial does not cite denied evidence.', field.fieldId);
      }
    } else if (
      resolution.status === 'not_mentioned' &&
      (field.required || mapping.required || mapping.unknownPolicy === 'requires_input')
    ) {
      add('REQUIRED_FIELD_NOT_MENTIONED', 'blocking', 'A required field was not mentioned.', field.fieldId);
    }

    // ══ #157(c) Q3 — THE MANIFEST MUST NOT BE SILENT ABOUT A DENIAL THAT
    // CONTRIBUTED NOTHING. ═════════════════════════════════════════════════
    //
    // A mixed field renders, and rule (3) says it must. But a denial that was
    // withheld inside it left the document with NO trace of itself — the
    // affirmed half prints and the denied half is simply absent. The reason
    // token rides on `resolution.reasonCode` (persisted per field to
    // `template_twin_fill_manifests`), and this issue names the field so a
    // reader who is scanning issues rather than reason codes sees it too.
    //
    // ⚠️ A WARNING, NEVER BLOCKING — the same unconditional severity as
    // FIELD_DENIAL_WITHHELD, and for the same reason. Blocking here would
    // reintroduce, through a new code, exactly the document-killer this ruling
    // removes.
    //
    // ⚠️ #157(d) C3 — RE-KEYED FROM `startsWith(`${MIXED_POLARITY_REASON}:`)` TO
    // EXACT EQUALITY, IN THE SAME COMMIT THAT STOPPED COMPOSING THE TOKEN. The
    // prefix test was the composed token's only consumer; leaving it would have
    // made this warning SILENTLY DEAD while the code still read as though the
    // silence rule held. And the context it used to carry in the identifier now
    // comes from the CITED FACTS, which is where it always belonged: the count
    // is re-derived here, not persisted in a reason string.
    if (
      resolution.status === 'supported' &&
      resolution.reasonCode === MIXED_POLARITY_REASON
    ) {
      const withheldDenials = citedFacts.filter((fact) => fact.polarity === 'denied').length;
      add('FIELD_MIXED_POLARITY_DENIAL_WITHHELD', 'warning', `A denial in this mixed-polarity field contributed no text (${withheldDenials} denied fact${withheldDenials === 1 ? '' : 's'} withheld under ${MIXED_POLARITY_REASON}).`, field.fieldId);
    }

    if (field.kind === 'single_select' && populated && !field.rowPrototype) {
      if (typeof resolution.value !== 'string') {
        add('SINGLE_SELECT_TYPE_INVALID', 'blocking', 'A single-select value is not a string.', field.fieldId);
      } else {
        const option = field.allowedOptions.find((item) => item.value === resolution.value);
        if (!option) {
          add('DROPDOWN_NOT_EXACT_OPTION', 'blocking', 'A dropdown value is not an exact native option.', field.fieldId);
        } else if (resolution.selectedOptionOrdinal !== option.ordinal) {
          add('DROPDOWN_ORDINAL_MISMATCH', 'blocking', 'The dropdown ordinal does not match its exact option.', field.fieldId);
        }
      }
    }
    if (field.kind === 'multi_select' && populated) {
      if (
        !Array.isArray(resolution.value) ||
        resolution.value.some((value) => typeof value !== 'string')
      ) {
        add('MULTI_SELECT_TYPE_INVALID', 'blocking', 'A multi-select value has an invalid shape.', field.fieldId);
      } else {
        const values = resolution.value as string[];
        const allowed = new Set(field.allowedOptions.map((option) => option.value));
        if (values.some((value) => !allowed.has(value))) {
          add('MULTI_SELECT_NOT_EXACT_OPTIONS', 'blocking', 'A multi-select contains a value outside the native option set.', field.fieldId);
        }
        if (new Set(values).size !== values.length) {
          add('MULTI_SELECT_DUPLICATE', 'blocking', 'A multi-select repeats an option.', field.fieldId);
        }
      }
    }
    if (field.kind === 'checkbox' && populated && !field.rowPrototype) {
      if (typeof resolution.value !== 'boolean') {
        add('CHECKBOX_TYPE_INVALID', 'blocking', 'A checkbox value is not boolean.', field.fieldId);
      } else if (
        resolution.value === true &&
        !citedFacts.some((fact) => fact.polarity === 'affirmed')
      ) {
        add('CHECKBOX_AFFIRMATION_MISSING', 'blocking', 'A selected checkbox lacks affirmative evidence.', field.fieldId);
      } else if (
        resolution.value === false &&
        resolution.status === 'explicitly_denied' &&
        !citedFacts.some((fact) => fact.polarity === 'denied')
      ) {
        add('CHECKBOX_DENIAL_MISSING', 'blocking', 'A denied checkbox lacks explicit denial evidence.', field.fieldId);
      }
    }
    if (field.kind === 'date' && populated && !field.rowPrototype) {
      if (typeof resolution.value !== 'string' || !isStrictIsoDate(resolution.value)) {
        add('DATE_INVALID', 'blocking', 'A date is not an unambiguous valid ISO calendar date.', field.fieldId);
      }
    }
    if (field.kind === 'number' && populated && !field.rowPrototype) {
      if (typeof resolution.value !== 'number' || !Number.isFinite(resolution.value)) {
        add('NUMBER_INVALID', 'blocking', 'A numeric field is not a finite explicit number.', field.fieldId);
      }
      if (citedFacts.some((fact) => fact.unit !== null)) {
        add('NUMBER_HAS_UNIT', 'blocking', 'A number-only field cites an unapproved unit.', field.fieldId);
      }
    }
    if (field.kind === 'measurement' && populated && !field.rowPrototype) {
      const parsed = parseExplicitNumberAndUnit(resolution.value as string | number | boolean);
      if (parsed.number === null) {
        add('MEASUREMENT_NUMBER_INVALID', 'blocking', 'A measurement lacks an explicit finite number.', field.fieldId);
      }
      if (mapping.unitPolicy === 'required' && parsed.unit === null) {
        add('MEASUREMENT_UNIT_MISSING', 'blocking', 'A required measurement unit is missing.', field.fieldId);
      }
      if (mapping.unitPolicy === 'forbidden' && parsed.unit !== null) {
        add('MEASUREMENT_UNIT_FORBIDDEN', 'blocking', 'A forbidden measurement unit is present.', field.fieldId);
      }
    }

    if (mapping.laterality === 'required' && populated) {
      const lateralities = new Set(citedFacts.map((fact) => fact.laterality));
      if (lateralities.has('unknown') || lateralities.has('not_applicable') || lateralities.size !== 1) {
        add('LATERALITY_UNRESOLVED', 'blocking', 'Required laterality is missing or conflicting.', field.fieldId);
      }
    }

    const concept = mapping.clinicalConcept
      ? normalizeConcept(mapping.clinicalConcept)
      : '';
    if (field.criticality === 'medication' || concept.startsWith('medication.')) {
      if (concept === 'medication.dose' && populated) {
        if (citedFacts.some((fact) => fact.number === null || fact.unit === null)) {
          add('MEDICATION_DOSE_INCOMPLETE', 'blocking', 'A medication dose lacks an explicit number or unit.', field.fieldId);
        }
      }
      if (
        populated &&
        citedFacts.some((fact) =>
          ['medication.name', 'medication.route', 'medication.frequency'].includes(concept) &&
          typeof fact.value !== 'string',
        )
      ) {
        add('MEDICATION_COMPONENT_INVALID', 'blocking', 'A medication component is not directly supported text.', field.fieldId);
      }
    }
    if (field.criticality === 'allergy' || concept.startsWith('allergy.')) {
      if (
        citedFacts.some(
          (fact) =>
            fact.experiencer !== 'patient' ||
            fact.quality.evidence === 'conflicting',
        )
      ) {
        add('ALLERGY_EVIDENCE_UNRESOLVED', 'blocking', 'Allergy evidence is conflicting or not patient-specific.', field.fieldId);
      }
    }

    if (field.tableId) {
      const table = tableById.get(field.tableId);
      if (!table) {
        add('TABLE_DEFINITION_MISSING', 'blocking', 'A table field references a missing table definition.', field.fieldId);
      } else if (field.rowPrototype && populated) {
        if (!isRowValueArray(resolution.value)) {
          add('REPEATING_ROW_SHAPE_INVALID', 'blocking', 'A repeating-row field does not contain row records.', field.fieldId);
        } else {
          const rowCount = resolution.value.length;
          if (rowCount > table.maxRows) {
            add('TABLE_ROW_OVERFLOW', 'blocking', 'Resolved repeating rows exceed the certified table limit.', field.fieldId);
          }
          const priorCount = repeatedCountsByTable.get(field.tableId);
          if (priorCount !== undefined && priorCount !== rowCount) {
            add('TABLE_ROW_ALIGNMENT_CONFLICT', 'blocking', 'Repeating table columns do not have aligned row counts.', field.fieldId);
          } else {
            repeatedCountsByTable.set(field.tableId, rowCount);
          }
          const rowAnchors = resolution.value.map((entry) => {
            const parsed = parseRowValue(entry);
            return parsed?.evidenceAnchorId ?? '';
          });
          const priorAnchors = repeatedAnchorsByTable.get(field.tableId);
          if (
            priorAnchors !== undefined &&
            (priorAnchors.length !== rowAnchors.length ||
              priorAnchors.some((anchor, index) => anchor !== rowAnchors[index]))
          ) {
            add('TABLE_ROW_EVIDENCE_MISALIGNED', 'blocking', 'Repeating table columns do not share aligned row evidence.', field.fieldId);
          } else {
            repeatedAnchorsByTable.set(field.tableId, rowAnchors);
          }
        }
      }
    }
  }

  let checkedAt: string;
  try {
    checkedAt = new Date(input.now ?? Date.now()).toISOString();
  } catch {
    checkedAt = new Date(0).toISOString();
    add('VALIDATION_TIMESTAMP_INVALID', 'blocking', 'The validation timestamp is invalid.');
  }
  return TemplateTwinValidationResultSchema.parse({
    valid: !issues.some((issue) => issue.severity === 'blocking'),
    issues,
    checkedAt,
    validatorVersion: TEMPLATE_TWIN_VALIDATOR_VERSION,
  });
}
