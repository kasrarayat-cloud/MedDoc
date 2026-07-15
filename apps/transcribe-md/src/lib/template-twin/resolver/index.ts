// ============================================================================
// Template Twin — evidence-backed field resolver
// ----------------------------------------------------------------------------
// Resolves each compiler-defined field independently. Matching is exact after
// identifier-only canonicalization; dropdown values are never fuzzy-matched,
// units are never inferred, and every populated value retains source fact and
// evidence-anchor IDs, including approved defaults and physician corrections.
// ============================================================================

import {
  EncounterFactSchema,
  FieldResolutionSchema,
  SemanticMappingSchema,
  TemplateFieldSchema,
  type EncounterFact,
  type FieldResolution,
  type FieldResolutionStatus,
  type SemanticMapping,
  type TemplateField,
} from '../ir';
import { parseExplicitNumberAndUnit } from '../encounter-facts';
import { isMappingTypeCompatible } from '../semantic-mapping';
import {
  approvedPracticeDefaultAnchorId,
  approvedPracticeDefaultFactId,
} from '../practice-default';
import {
  TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE,
  isSupportedTemplateTwinConcept,
} from '../supported-concepts';

export interface ResolveTemplateFieldsInput {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  /** Persisted physician certification lives outside the immutable compiler
   * IR. Production callers supply the exact certified DB field set. */
  certifiedFieldIds?: ReadonlyArray<string>;
  /** Certification tests may opt in; production resolution stays strict. */
  allowUncertifiedForSyntheticTest?: boolean;
}

interface ConvertedValue {
  value: string | number | boolean;
  optionOrdinal: number | null;
}

interface ConversionFailure {
  code: string;
}

type ConversionResult = ConvertedValue | ConversionFailure;

function normalizeConcept(value: string): string {
  return value.normalize('NFKC').trim().toLocaleLowerCase('en-US');
}

function unique<T>(values: ReadonlyArray<T>): T[] {
  return [...new Set(values)];
}

function evidenceFor(facts: ReadonlyArray<EncounterFact>): {
  sourceFactIds: string[];
  evidenceAnchorIds: string[];
} {
  return {
    sourceFactIds: unique(facts.map((fact) => fact.factId)),
    evidenceAnchorIds: unique(
      facts.flatMap((fact) => fact.evidenceAnchorIds),
    ),
  };
}

function makeResolution(
  fieldId: string,
  status: FieldResolutionStatus,
  value: FieldResolution['value'],
  facts: ReadonlyArray<EncounterFact>,
  reasonCode: string,
  selectedOptionOrdinal: number | null = null,
): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId,
    status,
    value,
    ...evidenceFor(facts),
    selectedOptionOrdinal,
    reasonCode,
    clinicianReviewed: false,
  });
}

export function isStrictIsoDate(value: string): boolean {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

function exactOption(
  field: TemplateField,
  raw: string,
): { value: string; ordinal: number } | null {
  const candidate = raw.trim();
  const option = field.allowedOptions.find(
    (item) => item.value === candidate || item.displayText === candidate,
  );
  return option ? { value: option.value, ordinal: option.ordinal } : null;
}

function convertValue(
  field: TemplateField,
  mapping: SemanticMapping,
  rawValue: string | number | boolean,
  polarity: EncounterFact['polarity'],
  explicitNumber: number | null,
  explicitUnit: string | null,
): ConversionResult {
  switch (field.kind) {
    case 'narrative_text':
      return typeof rawValue === 'string'
        ? { value: rawValue, optionOrdinal: null }
        : { code: 'text_value_not_string' };

    case 'single_select': {
      if (typeof rawValue !== 'string') return { code: 'select_value_not_string' };
      const option = exactOption(field, rawValue);
      return option
        ? { value: option.value, optionOrdinal: option.ordinal }
        : { code: 'select_value_not_exact_option' };
    }

    case 'checkbox':
      if (polarity === 'affirmed') return { value: true, optionOrdinal: null };
      if (polarity === 'denied') return { value: false, optionOrdinal: null };
      return { code: 'checkbox_polarity_unresolved' };

    case 'date':
      return typeof rawValue === 'string' && isStrictIsoDate(rawValue.trim())
        ? { value: rawValue.trim(), optionOrdinal: null }
        : { code: 'date_not_unambiguous_iso' };

    case 'number': {
      const parsed = parseExplicitNumberAndUnit(rawValue);
      const number = explicitNumber ?? parsed.number;
      const unit = explicitUnit ?? parsed.unit;
      if (number === null) return { code: 'number_not_explicit' };
      if (unit !== null) return { code: 'number_contains_unapproved_unit' };
      return { value: number, optionOrdinal: null };
    }

    case 'measurement': {
      const parsed = parseExplicitNumberAndUnit(rawValue);
      const number = explicitNumber ?? parsed.number;
      const unit = explicitUnit ?? parsed.unit;
      if (number === null) return { code: 'measurement_number_not_explicit' };
      if (mapping.unitPolicy === 'required' && !unit) {
        return { code: 'measurement_unit_missing' };
      }
      if (mapping.unitPolicy === 'forbidden' && unit) {
        return { code: 'measurement_unit_forbidden' };
      }
      return {
        value: unit ? `${number} ${unit}` : number,
        optionOrdinal: null,
      };
    }

    case 'multi_select':
      return { code: 'multi_select_requires_aggregate_resolution' };
  }
}

function practiceDefaultResolution(
  field: TemplateField,
  mapping: SemanticMapping,
  facts: ReadonlyArray<EncounterFact>,
): FieldResolution | null {
  if (mapping.practiceDefault === null || mapping.status !== 'certified') {
    return null;
  }
  const parsed = parseExplicitNumberAndUnit(mapping.practiceDefault);
  const converted = convertValue(
    field,
    mapping,
    mapping.practiceDefault,
    mapping.practiceDefault.trim().toLocaleLowerCase('en-US') === 'false'
      ? 'denied'
      : 'affirmed',
    parsed.number,
    parsed.unit,
  );
  if ('code' in converted) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      `invalid_practice_default_${converted.code}`,
    );
  }
  const defaultFact = facts.find(
    (fact) =>
      fact.factId === approvedPracticeDefaultFactId(field, mapping) &&
      fact.sourceType === 'approved_practice_default',
  );
  if (!defaultFact) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      'approved_practice_default_evidence_missing',
    );
  }
  return makeResolution(
    field.fieldId,
    'approved_practice_default',
    converted.value,
    [defaultFact],
    'approved_practice_default',
    converted.optionOrdinal,
  );
}

function missingResolution(
  field: TemplateField,
  mapping: SemanticMapping,
  facts: ReadonlyArray<EncounterFact>,
): FieldResolution {
  const practiceDefault = practiceDefaultResolution(field, mapping, facts);
  if (practiceDefault) return practiceDefault;
  const requiresInput =
    field.required ||
    mapping.required ||
    field.unknownPolicy === 'requires_input' ||
    mapping.unknownPolicy === 'requires_input' ||
    mapping.blankPolicy === 'requires_input';
  return makeResolution(
    field.fieldId,
    requiresInput ? 'needs_clinician_input' : 'not_mentioned',
    null,
    [],
    requiresInput ? 'required_fact_not_mentioned' : 'fact_not_mentioned',
  );
}

function defaultLaterality(value: string): EncounterFact['laterality'] {
  if (/\b(?:bilateral|both\s+sides?)\b/i.test(value)) return 'bilateral';
  const left = /\bleft\b/i.test(value);
  const right = /\bright\b/i.test(value);
  if (left && right) return 'bilateral';
  if (left) return 'left';
  if (right) return 'right';
  if (/\bmidline\b/i.test(value)) return 'midline';
  return 'unknown';
}

/**
 * Materialize physician-approved defaults as deterministic provenance facts.
 * They are not encounter transcript assertions, but they carry the same
 * sourceFactId/anchor contract so no populated field receives an evidence
 * exception. The resolver considers them only after encounter evidence is
 * absent and labels the resulting resolution `approved_practice_default`.
 */
export function withApprovedPracticeDefaultFacts(input: {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
}): EncounterFact[] {
  const fields = input.fields.map((field) => TemplateFieldSchema.parse(field));
  const mappings = input.mappings.map((mapping) =>
    SemanticMappingSchema.parse(mapping),
  );
  const facts = input.facts.map((fact) => EncounterFactSchema.parse(fact));
  const existingIds = new Set(facts.map((fact) => fact.factId));
  const mappingById = new Map(mappings.map((mapping) => [mapping.fieldId, mapping]));

  for (const field of fields) {
    const mapping = mappingById.get(field.fieldId);
    if (
      !mapping ||
      mapping.status !== 'certified' ||
      !mapping.clinicalConcept ||
      mapping.practiceDefault === null
    ) {
      continue;
    }
    const factId = approvedPracticeDefaultFactId(field, mapping);
    if (existingIds.has(factId)) continue;
    const raw = mapping.practiceDefault;
    const parsed = parseExplicitNumberAndUnit(raw);
    const denied = raw.trim().toLocaleLowerCase('en-US') === 'false';
    const anchorId = approvedPracticeDefaultAnchorId(field, factId);
    facts.push(
      EncounterFactSchema.parse({
        factId,
        sourceType: 'approved_practice_default',
        concept: mapping.clinicalConcept,
        value: raw,
        polarity: denied ? 'denied' : 'affirmed',
        temporality:
          mapping.temporality === 'historical' ||
          mapping.temporality === 'planned' ||
          mapping.temporality === 'current'
            ? mapping.temporality
            : 'current',
        experiencer: 'patient',
        laterality:
          mapping.laterality === 'not_applicable'
            ? 'not_applicable'
            : defaultLaterality(raw),
        number: parsed.number,
        unit: parsed.unit,
        speaker: 'Approved practice default',
        sourceTranscriptOffsets: null,
        audioTimestampSeconds: null,
        evidenceAnchorIds: [anchorId],
        evidenceQuote:
          'Physician-approved practice default for this certified template version.',
        quality: { asr: 'unknown', evidence: 'direct' },
      }),
    );
    existingIds.add(factId);
  }
  return facts;
}

function rowPrototypeValue(
  pairs: ReadonlyArray<{ fact: EncounterFact; converted: ConvertedValue }>,
): Array<Record<string, string | null>> {
  return pairs.map(({ fact, converted }) => ({
    value: String(converted.value),
    sourceFactId: fact.factId,
    evidenceAnchorId: fact.evidenceAnchorIds[0] ?? null,
    optionOrdinal:
      converted.optionOrdinal === null ? null : String(converted.optionOrdinal),
  }));
}

function resolveOne(
  field: TemplateField,
  mapping: SemanticMapping | undefined,
  allFacts: ReadonlyArray<EncounterFact>,
  allowUncertified: boolean,
  certifiedFieldIds: ReadonlySet<string>,
): FieldResolution {
  if (!mapping) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      'semantic_mapping_missing',
    );
  }
  if (!isMappingTypeCompatible(field, mapping)) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      'semantic_mapping_type_mismatch',
    );
  }
  if (
    !allowUncertified &&
    (mapping.status !== 'certified' ||
      (field.detectionStatus !== 'certified' &&
        !certifiedFieldIds.has(field.fieldId)))
  ) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      'field_or_mapping_not_certified',
    );
  }
  if (mapping.status === 'unsupported' || field.detectionStatus === 'unsupported') {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      'field_or_mapping_unsupported',
    );
  }
  if (!mapping.clinicalConcept) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      'clinical_concept_unmapped',
    );
  }
  if (!isSupportedTemplateTwinConcept(mapping.clinicalConcept)) {
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      [],
      TEMPLATE_TWIN_UNSUPPORTED_CONCEPT_CODE.toLocaleLowerCase('en-US'),
    );
  }

  const approvedConcepts = new Set(
    [mapping.clinicalConcept, ...mapping.approvedSynonyms].map(normalizeConcept),
  );
  const conceptCandidates = allFacts.filter(
    (fact) =>
      fact.sourceType !== 'approved_practice_default' &&
      approvedConcepts.has(normalizeConcept(fact.concept)),
  );
  if (conceptCandidates.length === 0) {
    return missingResolution(field, mapping, allFacts);
  }

  const expectedTemporality = mapping.temporality;
  const temporalCandidates =
    expectedTemporality === null || expectedTemporality === 'any'
      ? conceptCandidates
      : conceptCandidates.filter((fact) => fact.temporality === expectedTemporality);
  if (temporalCandidates.length === 0) {
    return makeResolution(
      field.fieldId,
      'ambiguous',
      null,
      conceptCandidates,
      'temporality_not_approved',
    );
  }

  const permitsFamily = normalizeConcept(mapping.clinicalConcept).startsWith(
    'family_history.',
  );
  if (
    temporalCandidates.some(
      (fact) =>
        fact.experiencer !== 'patient' &&
        !(permitsFamily && fact.experiencer === 'family'),
    )
  ) {
    return makeResolution(
      field.fieldId,
      'ambiguous',
      null,
      temporalCandidates,
      'experiencer_not_approved',
    );
  }

  if (temporalCandidates.some((fact) => fact.quality.evidence === 'conflicting')) {
    return makeResolution(
      field.fieldId,
      'conflict',
      null,
      temporalCandidates,
      'source_evidence_conflict',
    );
  }
  if (
    temporalCandidates.some(
      (fact) =>
        fact.quality.evidence === 'unclear' || fact.quality.asr === 'review',
    )
  ) {
    return makeResolution(
      field.fieldId,
      'ambiguous',
      null,
      temporalCandidates,
      'source_evidence_needs_review',
    );
  }

  if (mapping.laterality === 'required') {
    const lateralities = unique(
      temporalCandidates.map((fact) => fact.laterality),
    );
    if (lateralities.includes('unknown') || lateralities.includes('not_applicable')) {
      return makeResolution(
        field.fieldId,
        'needs_clinician_input',
        null,
        temporalCandidates,
        'required_laterality_missing',
      );
    }
    if (lateralities.length > 1) {
      return makeResolution(
        field.fieldId,
        'conflict',
        null,
        temporalCandidates,
        'laterality_conflict',
      );
    }
  }

  const polarities = unique(temporalCandidates.map((fact) => fact.polarity));
  if (polarities.includes('uncertain') || polarities.includes('conditional')) {
    return makeResolution(
      field.fieldId,
      'ambiguous',
      null,
      temporalCandidates,
      'polarity_ambiguous',
    );
  }
  if (polarities.includes('affirmed') && polarities.includes('denied')) {
    return makeResolution(
      field.fieldId,
      'conflict',
      null,
      temporalCandidates,
      'polarity_conflict',
    );
  }
  const allDenied = polarities.length === 1 && polarities[0] === 'denied';
  if (allDenied && field.kind === 'checkbox') {
    if (mapping.polarityBehavior !== 'explicit_denial_allowed') {
      return makeResolution(
        field.fieldId,
        'needs_clinician_input',
        null,
        temporalCandidates,
        'checkbox_false_semantics_not_certified',
      );
    }
  } else if (allDenied) {
    // Safe-alpha mappings do not yet carry an exact, physician-certified
    // negative rendering value for non-checkbox fields. Preserve the denial
    // evidence for review, but never coerce it into narrative/select/date or
    // repeating output that the renderer cannot safely represent.
    return makeResolution(
      field.fieldId,
      'needs_clinician_input',
      null,
      temporalCandidates,
      'negative_rendering_policy_missing',
    );
  }

  if (field.kind === 'multi_select') {
    if (field.rowPrototype) {
      return makeResolution(
        field.fieldId,
        'needs_clinician_input',
        null,
        temporalCandidates,
        'repeating_multi_select_requires_clinician_input',
      );
    }
    const selected = new Map<number, string>();
    for (const fact of temporalCandidates) {
      if (typeof fact.value !== 'string') {
        return makeResolution(
          field.fieldId,
          'needs_clinician_input',
          null,
          temporalCandidates,
          'multi_select_value_not_string',
        );
      }
      const option = exactOption(field, fact.value);
      if (!option) {
        return makeResolution(
          field.fieldId,
          'needs_clinician_input',
          null,
          temporalCandidates,
          'multi_select_value_not_exact_option',
        );
      }
      selected.set(option.ordinal, option.value);
    }
    const values = [...selected.entries()]
      .sort(([left], [right]) => left - right)
      .map(([, value]) => value);
    return makeResolution(
      field.fieldId,
      'supported',
      values,
      temporalCandidates,
      'exact_options_supported',
    );
  }

  const convertedPairs: Array<{
    fact: EncounterFact;
    converted: ConvertedValue;
  }> = [];
  for (const fact of temporalCandidates) {
    const converted = convertValue(
      field,
      mapping,
      fact.value,
      fact.polarity,
      fact.number,
      fact.unit,
    );
    if ('code' in converted) {
      return makeResolution(
        field.fieldId,
        'needs_clinician_input',
        null,
        temporalCandidates,
        converted.code,
      );
    }
    convertedPairs.push({ fact, converted });
  }

  if (field.rowPrototype) {
    return makeResolution(
      field.fieldId,
      'supported',
      rowPrototypeValue(convertedPairs),
      temporalCandidates,
      'repeating_rows_supported',
    );
  }

  const distinctValues = unique(
    convertedPairs.map(({ converted }) => JSON.stringify(converted.value)),
  );
  if (distinctValues.length > 1) {
    return makeResolution(
      field.fieldId,
      'conflict',
      null,
      temporalCandidates,
      'multiple_distinct_supported_values',
    );
  }

  const selected = convertedPairs[0]?.converted;
  if (!selected) return missingResolution(field, mapping, allFacts);
  return makeResolution(
    field.fieldId,
    allDenied ? 'explicitly_denied' : 'supported',
    selected.value,
    temporalCandidates,
    allDenied ? 'explicit_denial_supported' : 'direct_evidence_supported',
    selected.optionOrdinal,
  );
}

/** Resolve every compiler field exactly once and in compiler display order. */
export function resolveTemplateFields(
  input: ResolveTemplateFieldsInput,
): FieldResolution[] {
  const fields = input.fields.map((field) => TemplateFieldSchema.parse(field));
  const mappings = input.mappings.map((mapping) =>
    SemanticMappingSchema.parse(mapping),
  );
  const facts = input.facts.map((fact) => EncounterFactSchema.parse(fact));
  const mappingById = new Map(mappings.map((mapping) => [mapping.fieldId, mapping]));
  const certifiedFieldIds = new Set(input.certifiedFieldIds ?? []);

  return [...fields]
    .sort((a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId))
    .map((field) =>
      resolveOne(
        field,
        mappingById.get(field.fieldId),
        facts,
        input.allowUncertifiedForSyntheticTest === true,
        certifiedFieldIds,
      ),
    );
}
