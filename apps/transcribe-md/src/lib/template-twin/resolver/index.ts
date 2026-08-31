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
import { withoutPlaceholderOptions } from '../../note-template-docx/placeholder-option';
import { parseExplicitNumberAndUnit } from '../encounter-facts';
import { isMappingTypeCompatible } from '../semantic-mapping';
import {
  approvedPracticeDefaultAnchorId,
  approvedPracticeDefaultFactId,
} from '../practice-default';
import {
  isListValuedNarrative,
  joinListValuedNarrative,
} from '../field-value-derivation';
import { denialOutcome } from '../denial-contract';

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
  // ⚠️ WORD'S "Choose an item." IS NOT AN OPTION A RESOLVER MAY SELECT. The
  // compiled IR carries it at ordinal 0 by necessity — the renderer re-compiles
  // the source and hashes `fields`, so removing it orphans every
  // already-compiled twin (F24-S5 ITEM A) — so the exclusion lives on each
  // READER, and this reader selects a CLINICAL VALUE. Returning null here puts
  // a placeholder match on the same path as any other off-list value.
  const option = withoutPlaceholderOptions(field.allowedOptions).find(
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
  /** Overrides the reason when the field is unfilled for a NAMED reason more
   *  specific than "nothing was said" — the reason must survive, the false
   *  evidence trail must not. */
  reason?: { unfilled: string; required: string },
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
    requiresInput
      ? (reason?.required ?? 'required_fact_not_mentioned')
      : (reason?.unfilled ?? 'fact_not_mentioned'),
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
  // A MANUAL field carries no concept BY CONSTRUCTION — nothing in any encounter
  // can say who the technologist on shift was — and the certificate attests that
  // it renders blank. Reporting it as an unmapped field turned a designed state
  // into a configuration error, and at visit time that error is BLOCKING: four
  // such fields refused the native document on every visit, forever, and the
  // export fell back to the styled path. Nothing was made safer by that — the
  // fields are blank in both documents — so the only effect was that the doctor
  // never got their own form back.
  if (mapping.sourceType === 'manual') {
    return makeResolution(field.fieldId, 'not_mentioned', null, [], 'manual_source_not_filled');
  }
  // A VERIFIED NOTE SELECTION is answered by the adopted note's own pick, which
  // only the picks bridge can read. Resolving it here from raw facts produced
  // `select_value_not_exact_option` — needs-clinician-input, and BLOCKING at
  // visit time — for fourteen dropdowns the note had already answered. Same
  // shape as the fixed-grid rule: the component that can address it, addresses
  // it; the baseline is honestly blank.
  if (mapping.sourceType === 'verified_note_selection') {
    return makeResolution(field.fieldId, 'not_mentioned', null, [], 'awaiting_note_selection');
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

  // A FIXED-GRID TABLE CELL IS ADDRESSED BY ITS ROW, AND THE RESOLVER CANNOT
  // SEE ROWS.
  // Its only inputs are the field's concept and the fact set. In a 26-row vein
  // grid every reflux cell shares one concept, so "the reflux facts" are
  // candidates for all 26 of them and nothing here can say which row a given
  // 2.4 seconds belongs to. It was guessing: sometimes filling the wrong leg,
  // more often failing on type and returning needs_clinician_input for 33 cells
  // that the encounter had said nothing about — noise that reads like missing
  // evidence and blocks certification.
  //
  // Row addressing lives in the bridge, which matches a note row to an IR row by
  // vein label and then requires the fact to satisfy laterality and segment. So
  // the baseline for a table cell is the honest "not said here", and the bridge
  // overlays the values it can actually address. Required cells still surface as
  // needs-input through missingResolution, exactly as before.
  // A repeating-row PROTOTYPE is the opposite case and keeps resolving here: it
  // expands one row per fact, so there is no row to address and no ambiguity to
  // resolve. Only the fixed grid — many rows, one shared concept — defers.
  if (field.rendererBinding.bindingType === 'table_cell' && !field.rowPrototype) {
    return missingResolution(field, mapping, allFacts);
  }

  // A SELECT CAN ONLY CONFLICT OVER ITS OWN OPTIONS.
  // These dropdowns sit inside sentences ("Right deep venous system <choose>")
  // and map to a coarse concept like `exam.vascular`, which every vascular
  // statement in the encounter shares. Judging polarity and laterality across
  // all of them made a "conflict" out of four unrelated sentences — one
  // affirmed, one denied — and blocked certification on a field about which the
  // encounter had said nothing selectable. Seven fields, every run.
  //
  // A fact whose value is not one of THIS field's enumerated options cannot
  // fill it, so it is not evidence about it and cannot contradict anything
  // here. When none qualify there is nothing to conflict about, and the field
  // continues to the existing derivation path — which surfaces it as
  // needs-input with select_value_not_exact_option, not as a silent blank and
  // not as a conflict. Two facts that both name real options and disagree are
  // still a genuine conflict, judged exactly as before.
  const conflictCandidates =
    field.kind === 'single_select' || field.kind === 'multi_select'
      ? conceptCandidates.filter(
          (fact) => typeof fact.value === 'string' && exactOption(field, fact.value) !== null,
        )
      : conceptCandidates;

  const expectedTemporality = mapping.temporality;
  const temporalCandidates =
    expectedTemporality === null || expectedTemporality === 'any'
      ? conceptCandidates
      : conceptCandidates.filter((fact) => fact.temporality === expectedTemporality);
  if (temporalCandidates.length === 0) {
    // NOT ambiguous, and NOT cited. The mapping approves one temporality and no
    // fact carries it, so nothing was said about this field in the sense the
    // mapping requires — that is absence, not conflicting evidence. Citing the
    // rejected facts made the resolution contradict itself: it declared their
    // temporality unapproved and then attached them as the field's evidence,
    // and the validator (unchanged, and right) flagged both the mismatch and
    // the ambiguity. The reason code still names exactly why.
    return missingResolution(field, mapping, allFacts, {
      unfilled: 'temporality_not_approved',
      required: 'required_temporality_not_approved',
    });
  }

  // The facts eligible to fill THIS field (see conflictCandidates above), which
  // are the only ones whose disagreement is a disagreement about it. For a
  // non-select this is every temporal candidate, exactly as before.
  const judged = temporalCandidates.filter((fact) => conflictCandidates.includes(fact));

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
    const lateralities = unique(judged.map((fact) => fact.laterality));
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

  const polarities = unique(judged.map((fact) => fact.polarity));
  if (polarities.includes('uncertain') || polarities.includes('conditional')) {
    return makeResolution(
      field.fieldId,
      'ambiguous',
      null,
      judged,
      'polarity_ambiguous',
    );
  }
  if (polarities.includes('affirmed') && polarities.includes('denied')) {
    return makeResolution(
      field.fieldId,
      'conflict',
      null,
      judged,
      'polarity_conflict',
    );
  }
  const allDenied = polarities.length === 1 && polarities[0] === 'denied';
  // ══ OWNER RULING #157(b) — EVERY DENIAL RETURNS HERE, AND NOTHING BELOW EVER
  // SEES ONE. ════════════════════════════════════════════════════════════════
  //
  // Denial used to be decided in FOUR places — this arm, the multi_select
  // producer, the rowPrototype producer, and the scalar `mayPopulateDenial`
  // ternary — and each of the four reached a different wrong answer:
  //
  //   value_only        -> `ambiguous` -> FIELD_AMBIGUOUS is BLOCKING on any
  //                        critical/required field -> the doctor's WHOLE
  //                        DOCUMENT is refused, because one sentence was
  //                        dictated in the negative.
  //   affirmative_only  -> `explicitly_denied` + null -> the renderer's arm A
  //                        refuses a populated status carrying no value.
  //   explicit_denial   -> value KEPT -> the renderer's arm C refuses any
  //                        non-checkbox -> refused again, by a third route.
  //   multi-fact         -> did not reach any of them: `!allDenied` at the
  //                        list-join below diverted an accumulating denied
  //                        narrative into `multiple_distinct_supported_values`
  //                        -> FIELD_CONFLICT -> blocking. That is the measured
  //                        28-of-31 killed-documents harm.
  //
  // ⚠️ THE EARLY RETURN IS THE FIX FOR THE FOURTH ONE. Every path below this
  // line now runs on affirmed evidence only, so `allDenied` is false
  // everywhere downstream and the ternaries that used to test it are gone
  // rather than left as dead code that reads like live policy.
  //
  // The outcome itself lives in `denial-contract.ts`, which the VALIDATOR
  // re-derives from — one implementation for the write side and the verify
  // side, because that is the defect `field-value-derivation.ts` was extracted
  // to remove and this is the same shape one polarity over.
  if (allDenied) {
    // ⚠️ `judged`, NOT `temporalCandidates`. `allDenied` is computed from
    // `judged` — the exact-option subset — and the VALIDATOR re-asks the
    // question of the set this resolution CITES. Citing the wider set made a
    // resolution whose own evidence contained an affirmed bystander fact, so
    // `DENIAL_WITHHELD_WITHOUT_DENIAL` fired blocking and the whole export was
    // lost on every one of the 28 production single_selects. The two arms
    // directly above already cite `judged`; this one did not.
    const denial = denialOutcome(field, mapping, judged);
    return makeResolution(
      field.fieldId,
      denial.status,
      denial.value,
      judged,
      denial.reasonCode,
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
    // #157(b) rule (2): a denied multi_select never reaches here — selecting an
    // option ASSERTS ITS PRESENCE, so a denial is withheld above.
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
    // #157(b) rule (2): a denied repeating section never reaches here — every
    // row it would expand asserts the presence of what was denied.
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
    // A narrative SECTION accumulates; it does not contradict itself. Two past
    // medical conditions are not two answers to one question. See
    // field-value-derivation.ts for why measurements deliberately keep
    // conflicting here rather than joining.
    // ⚠️ `!allDenied` IS GONE, NOT RELAXED. It was the guard that sent a
    // multi-fact DENIED narrative into `multiple_distinct_supported_values`,
    // and a denial can no longer arrive here at all — it returned at the
    // #157(b) block above. Re-adding a polarity test here would be dead code
    // that looks like a safety property.
    if (isListValuedNarrative(field, mapping)) {
      const joined = joinListValuedNarrative(field, mapping, temporalCandidates);
      if (joined !== null) {
        return makeResolution(
          field.fieldId,
          'supported',
          joined,
          temporalCandidates,
          'list_valued_narrative_joined',
        );
      }
    }
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
  // #157(b): affirmed evidence only. `mayPopulateDenial` is gone — the two
  // shapes it permitted (a checkbox's `false`, a narrative's denial text) are
  // decided by `denialOutcome`, and the shapes it permitted BY ACCIDENT (a
  // denied date, number or measurement keeping its value under
  // `explicit_denial_allowed`) were refused by the renderer and are now
  // withheld with a named reason instead.
  return makeResolution(
    field.fieldId,
    'supported',
    selected.value,
    temporalCandidates,
    'direct_evidence_supported',
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
