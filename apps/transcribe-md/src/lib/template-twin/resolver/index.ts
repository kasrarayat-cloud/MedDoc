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
  fieldDemandsInput,
  type RecordDerivedRefusal,
  type SemanticMapping,
  type TemplateField,
} from '../ir';
import { withoutPlaceholderOptions } from '../../note-template-docx/placeholder-option';
import { parseExplicitNumberAndUnit } from '../encounter-facts';
import {
  conceptCandidateFacts,
  normalizeConcept,
  requiredFactTemporality,
  temporalityMatches,
} from '../fact-mapping-match';
import {
  omitDeferralGuard,
  practiceDefaultPreempts,
  resolverLadderExit,
} from '../unmentioned-policy';
import {
  approvedPracticeDefaultAnchorId,
  approvedPracticeDefaultFactId,
} from '../practice-default';
import {
  DIRECT_EVIDENCE_SUPPORTED_REASON,
  isEmptyText,
  isListValuedNarrative,
  joinListValuedNarrative,
  LIST_VALUED_NARRATIVE_JOINED_REASON,
} from '../field-value-derivation';
import { OTHER_EXPERIENCER_CLINICIAN_CONCEPTS } from '../concept-registry';
import { denialOutcome, mixedPolarityNarrative } from '../denial-contract';

export interface ResolveTemplateFieldsInput {
  fields: ReadonlyArray<TemplateField>;
  mappings: ReadonlyArray<SemanticMapping>;
  facts: ReadonlyArray<EncounterFact>;
  /** Persisted physician certification lives outside the immutable compiler
   * IR. Production callers supply the exact certified DB field set. */
  certifiedFieldIds?: ReadonlyArray<string>;
  /** Certification tests may opt in; production resolution stays strict. */
  allowUncertifiedForSyntheticTest?: boolean;
  /**
   * ⚠️ #264 — FIELDS AN INJECTOR DECLINED TO ANSWER, WITH THE REASON.
   *
   * An injector that cannot compute a value today simply mints no fact, and the
   * resolver then reaches its "no fact carries this concept" arm and reports
   * `fact_not_mentioned` — *"nobody said it"*. For a record-derived value that
   * is FALSE and it is the misleading direction: the patient record DID carry a
   * date of birth, and the code declined to turn it into a number because the
   * answer depended on a timezone nobody has recorded.
   *
   * A blank is the right output. A blank labelled "nobody mentioned it" is a
   * blank the doctor cannot act on — they would look for the dictation. So the
   * refusal travels with its reason and lands in `reasonCode`.
   */
  /**
   * ⚠️ SAME TYPE AS THE INJECTOR WRITES, DERIVED FROM `ir.ts` — see the note on
   * `withVisitMetadataFacts`'s own `refusals`. Two ends of one channel, one
   * vocabulary; `string` here would let an unregistered token in through the
   * READING end even with the writing end tightened.
   */
  refusals?: ReadonlyArray<RecordDerivedRefusal>;
}

interface ConvertedValue {
  value: string | number | boolean;
  optionOrdinal: number | null;
}

interface ConversionFailure {
  code: string;
}

type ConversionResult = ConvertedValue | ConversionFailure;

function unique<T>(values: ReadonlyArray<T>): T[] {
  return [...new Set(values)];
}

/**
 * The citation a resolution carries for these facts: their ids and every one of
 * their anchors, each de-duplicated in first-seen order.
 *
 * ⚠️ EXPORTED FOR #313, NOT RE-STATED. The bullet distribution pass
 * (`list-distribution.ts`) rewrites a group's citations per bullet, and the
 * validator refuses any anchor set that is not exactly the cited facts' anchors
 * (EVIDENCE_COVERAGE_INCOMPLETE / EVIDENCE_ANCHOR_UNTRACEABLE, both blocking).
 * Building them with the resolver's own helper is what keeps the two writers
 * producing the same shape.
 */
export function evidenceFor(facts: ReadonlyArray<EncounterFact>): {
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
    status: recordDerivedIfFromTheRecord(status, facts),
    value,
    ...evidenceFor(facts),
    selectedOptionOrdinal,
    reasonCode,
    clinicianReviewed: false,
  });
}

/**
 * #247 — A SUPPORTED RESOLUTION WHOSE EVIDENCE IS THE PATIENT RECORD IS
 * `record_derived`, NOT `supported`.
 *
 * ⚠️ ONE PROMOTION POINT, INSIDE `makeResolution`, AND NOT FIVE BRANCHES AT THE
 * FIVE `'supported'` CALL SITES. This file mints `supported` in five places
 * (direct evidence, exact options, multi-select, repeating rows, mixed-polarity
 * narrative) and a sixth will be added by somebody who has never read this
 * comment. A rule applied at every producer is a rule that will one day be
 * applied at all but one of them — canon's partial-application family — and the
 * failure mode here is silent: the document is identical and the manifest
 * claims a record value was dictated.
 *
 * ⚠️ EVERY cited fact, not SOME. A field supported jointly by a dictated
 * sentence and a record value is genuinely dictated in part, and calling the
 * whole resolution record-derived would understate what the clinician said. The
 * `visit_metadata` injector cannot produce that shape today — it refuses to
 * inject when any fact already speaks to the concept — so this arm is
 * conservative about a case that does not currently arise, which is the right
 * direction for a claim about provenance.
 *
 * Only `supported` is promoted. A conflict is still a conflict, and a blank is
 * still blank, whoever the evidence came from.
 */
function recordDerivedIfFromTheRecord(
  status: FieldResolutionStatus,
  facts: ReadonlyArray<EncounterFact>,
): FieldResolutionStatus {
  if (status !== 'supported' || facts.length === 0) return status;
  return facts.every((fact) => fact.sourceType === 'visit_record')
    ? 'record_derived'
    : status;
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
      // ⚠️ #218 — AN EMPTY STRING IS NOT A VALUE. Without this the blanked
      // escape hatch resolves `supported` over an emptied control and the whole
      // chain reports success: validator VALID with zero issues, renderer a
      // `filled` proof, `counts.filled > 0` satisfied. Refusing here makes it a
      // bounded clear that is COUNTED as blank, which is the honest outcome.
      // The predicate is IMPORTED, not re-derived — this arm and
      // `deriveFieldValueFromFact` are two implementations of one decision, and
      // they have disagreed before.
      if (typeof rawValue !== 'string') return { code: 'text_value_not_string' };
      return isEmptyText(rawValue)
        ? { code: 'text_value_empty' }
        : { value: rawValue, optionOrdinal: null };

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
  // ⚠️ ONE PROPERTY, ONE READER — RULING #258. The confirm surface asks the same
  // question ("does a default answer this before the policy is read?") and used
  // to answer it with its own `!== null`. The `status` half stays HERE: in
  // production it is unreachable (an uncertified mapping exits at the
  // certification guard far above) and it matters only on the synthetic-test
  // path, whereas at confirm time the mapping is being certified — so sharing it
  // would offer a control that stops working the moment the doctor certifies.
  if (!practiceDefaultPreempts(mapping) || mapping.status !== 'certified') {
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
  /**
   * ⚠️ DELIBERATELY WIDER THAN `RecordDerivedRefusal`, AND #275's RE-PASS PROVED
   * WHY. Tightening this to the record-derived vocabulary looked right and
   * failed the typecheck at :685, where the TEMPORALITY path passes
   * `temporality_not_approved` through the same parameter. This parameter is
   * "a named reason a field is blank" in general; the record-derived CHANNEL —
   * `ResolveTemplateFieldsInput.refusals` — is the narrow one, and it is the
   * only one that carries `neverBlocks`.
   */
  reason?: { unfilled: string; required: string; neverBlocks?: boolean },
  /** TRUE at exactly one call site: the one reached because NO fact carries
   *  this field's approved concept. That is the only site where "the encounter
   *  said nothing about this" is a true statement rather than a deferral. */
  conceptUnmatched = false,
): FieldResolution {
  const practiceDefault = practiceDefaultResolution(field, mapping, facts);
  if (practiceDefault) return practiceDefault;
  // ══ #272 — A RECORD-DERIVED REFUSAL NEVER WITHHOLDS A DOCUMENT ═══════════
  //
  // `requiresInput` turns a blank into `needs_clinician_input`;
  // `validation/index.ts:583-586` makes that BLOCKING; `fill-engine.ts:198`
  // turns any blocking issue into `render: null`. So this path did not blank a
  // field — it withheld the doctor's whole form.
  //
  //   A WITHHELD CONSULT OVER ONE AMBIGUOUS AGE IS THE WRONG TRADE.
  //   A DOCTOR TYPING "61" IS THE RIGHT ONE.
  //
  // ⚠️ AND IT IS NOT SCOPED TO REQUIRED CONTROLS THE WAY THE READING SUGGESTS.
  // `needsInputBlocks` is `critical || field.required || mapping.required`, and
  // `critical` is `field.criticality !== 'routine' || field.clinicallyMaterial`
  // — with `clinicallyMaterial` hard-coded TRUE at all twelve compiler sites.
  // Measured in production: **238 of 238 rows carry `clinicallyMaterial = t`
  // and `required = f`.** So `critical` is a CONSTANT TRUE, the `required`
  // disjuncts are dead weight, and EVERY field reaching this status takes the
  // document down. (Ruling #157(d) already filed that separately — *"a
  // qualifier that is always true is a comment"*.)
  //
  // ⚠️ THE CODEBASE ALREADY ARGUES THE FIX, IN ITS OWN WORDS:
  //   · `manual_source_not_filled` (:486) returns `not_mentioned`, and records
  //     what the alternative cost — "four such fields refused the native
  //     document on every visit, forever … the only effect was that the doctor
  //     never got their own form back."
  //   · `denial_withheld` is a warning UNCONDITIONALLY under #157(b) —
  //     "refusing the OTHER hundred and forty-nine fields does not fill it."
  //
  // This does NOT weaken `needs_clinician_input` in general: the escalation
  // stands for every other route in, and `neverBlocks` is set ONLY by the
  // injector-refusal channel, whose members are record-derived by construction.
  // ⚠️ THE DISJUNCTION MOVED TO `ir.ts` AND IS NOT RESTATED HERE — #275's
  // re-pass found the validator asking a NARROWER version of this same
  // question. One predicate, two readers.
  const requiresInput = !reason?.neverBlocks && fieldDemandsInput(field, mapping);
  const unmentionedScaffold =
    conceptUnmatched && reason === undefined && facts.length > 0;

  // ⚠️ #194 — THE KEEP BRANCH IS DELETED. It used to return `default_kept`
  // here. Its premise was refuted, not merely its mechanism: it fired when
  // `conceptCandidates.length === 0` -- when NO fact carried the field's
  // concept -- and concept equality is the only test performed anywhere, so
  // "nothing dictated contradicted this clause" was always a claim about the
  // EMPTY SET. A scaffold reading "no varicosities, no oedema and no
  // ulceration" was kept on a visit dictated as a large weeping ulcer with
  // oedema and varicosities, because that fact carried `chief_complaint`.
  //
  // The machine never prints an undictated default. A doctor's own default is
  // now a HUMAN act at review (REVIEW-DEFAULTS), where the click is their
  // assertion and it fills through the normal human-typed path.

  return makeResolution(
    field.fieldId,
    requiresInput ? 'needs_clinician_input' : 'not_mentioned',
    null,
    [],
    requiresInput
      ? (reason?.required ?? 'required_fact_not_mentioned')
      : unmentionedScaffold && mapping.unmentionedPolicy === 'omit'
        // #191 — the scaffold was cleared ON PURPOSE and the reason says so.
        // `fact_not_mentioned` would read as "nobody looked".
        // ⚠️ GATED ON THE SHARED PREDICATE, not on the policy alone: a named
        // reason must survive, and a clearing nothing evaluated is not
        // deliberate.
        ? 'omitted_unsupported_default'
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
        temporality: requiredFactTemporality(mapping),
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
  refusal?: { unfilled: string; required: string },
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
  // ⚠️ THE LADDER IS WALKED, NOT WRITTEN HERE — RULING #258, NO MIRROR.
  //
  // These five guards used to be five inline `if`s, and the confirm surface
  // carried a hand-maintained copy of them so it could decide what to OFFER.
  // That copy shipped EIGHT divergences in seven rounds; every repair widened a
  // matrix so the copy's CURRENT divergences became visible, and none made the
  // next one impossible. There is one copy now, it lives in `unmentioned-policy`
  // (the leaf, because that module is value-imported by a `'use client'`
  // component and this one value-imports zod), and both sides walk it.
  //
  // ⚠️ EACH ROW CARRIES ITS OWN `status` AND `reasonCode`, so nothing about the
  // resolutions below changed — the same tokens, in the same order, from a table
  // instead of from a sequence of statements.
  // ⚠️ AND THE WALK ITSELF IS THE SHARED FUNCTION NOW — RULING #280. The loop
  // that used to live here (the table walk plus the interleaved certification
  // check, whose POSITION is behaviour) is `resolverLadderExit`, beside the
  // table it walks. Two reasons, and the second is the one that forced it:
  //
  //   · #258's invariant is ONE implementation, and a loop here plus a loop in
  //     `omitBranchUnreachable` was two walks of one table;
  //   · the read set on this path could not be TRACED while it lived here.
  //     `resolveTemplateFields` zod-parses its inputs and `parse` returns a NEW
  //     object, so a Proxy on what the caller passes records zod touching every
  //     key rather than this function's own reads. The arm therefore derived the
  //     read set with a member-expression REGEX over two anchored byte ranges of
  //     this file — and #251 retires text scanning as a proof of behaviour.
  //     Measured: 4 reads inside the regions, 8 more outside them in this same
  //     file, so a guard one function call away was invisible.
  //
  // Lifting it gives the tracer something it can wrap directly, on the far side
  // of the parse.
  const ladder = resolverLadderExit(field, mapping, {
    allowUncertified,
    certifiedFieldIds,
  });
  if (ladder) {
    return makeResolution(field.fieldId, ladder.status, null, [], ladder.reasonCode);
  }

  // ⚠️ THE SHARED CONCEPT HALF, NOT A FOURTH OPEN-CODED COPY. This filter used
  // to build its own approved-concept set, which meant #179(3)'s declared
  // scope — checked by the validator — was invisible here. The resolver filled
  // a field the validator then refused, and `fill-engine` turned that into a
  // WITHHELD DOCUMENT rather than a wrong value.
  // ⚠️ #313 — THE FILTER LIVES IN `fact-mapping-match.ts` NOW, verbatim, so
  // `listItemCandidates` (the validator's group check) composes the SAME stage
  // rather than a copy of it. Behaviour is unchanged; the tense stage below
  // stays a separate call, as it must.
  const conceptCandidates = conceptCandidateFacts(mapping, allFacts);
  // ⚠️ #264 — A NAMED REFUSAL OUTRANKS "NOBODY SAID IT", AND IT IS CHECKED
  // BEFORE the concept search rather than after. An injector that declined to
  // compute a value mints no fact, so the concept search finds nothing and the
  // arm below would report `fact_not_mentioned` — a true statement about the
  // FACTS and a false one about the ENCOUNTER. The refusal is the more specific
  // reason and the more specific reason wins.
  //
  // The value is still null and the field is still blank: this changes the
  // LABEL on the blank, not the blank.
  if (refusal) {
    // ⚠️ `neverBlocks` — #272. The blank is NAMED and the document still
    // renders. The opt-out is a property of the CHANNEL, not a token list
    // somebody has to keep in step: only `withVisitMetadataFacts` writes here.
    return missingResolution(field, mapping, allFacts, { ...refusal, neverBlocks: true });
  }

  if (conceptCandidates.length === 0) {
    // The ONLY site that earns #191's kept default: no fact in the encounter
    // carries this field's approved concept, so the template's own sentence
    // stands uncontradicted. The three other `missingResolution` sites are
    // DEFERRALS with facts in hand — a grid row the resolver cannot address, a
    // temporality the mapping did not approve — and a kept default there would
    // answer a question that was actually asked.
    return missingResolution(field, mapping, allFacts, undefined, true);
  }

  // ⚠️ #179(5) — A CHECKBOX ANSWERS FOR EXACTLY ONE SYMPTOM, AND THE REFUSAL
  // HAS TO LIVE HERE BECAUSE THE FILL PATH NEVER REACHED THE OTHER ONE.
  //
  // `deriveFieldValueFromFact` already refuses a multi-scope tick, and the
  // validator and the bridge both call it. The RESOLVER does not — it carries
  // its own inline `case 'checkbox'` which reads ONLY `fact.polarity` and
  // discards the finding. So the ruled refusal existed, was commented, was
  // tested against the derivation helper, and had no effect whatever on the
  // value actually written to the document.
  //
  // A box whose declared scope covers several symptoms cannot be answered by
  // one fact: "affirmed" is ambiguous between them. Refused rather than
  // guessed — an unticked box a clinician can tick is recoverable, a wrongly
  // ticked one is not.
  //
  // ⚠️ A DEFERRAL, NOT A KEPT DEFAULT. Facts ARE in hand here, so #191's
  // `conceptUnmatched` flag is deliberately not passed — the same reasoning as
  // the fixed-grid cell below. The encounter DID speak to this field; the
  // resolver simply cannot say which symptom it spoke about.
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
  // ⚠️ BOTH DEFERRALS ARE ONE SHARED CALL NOW — RULING #258, NO MIRROR.
  //
  // These two were separate `if`s, and the confirm surface's copy of the ladder
  // knew about NEITHER of them for most of its life: the fixed grid was the
  // seventh divergence, found by a peer session's independent pass, and the
  // multi-scope checkbox was the EIGHTH, found by round seven after the matrix
  // had already been widened three times.
  //
  // ⚠️ THEY WERE INVISIBLE FOR A STRUCTURAL REASON, NOT A CARELESS ONE. The copy
  // was built by walking the GUARD LADDER above, and these are not guards in that
  // ladder — they are different CALL SITES of `missingResolution`, reached only
  // once facts carry the field's concept. `:490`'s own comment says it: "The
  // three other `missingResolution` sites are DEFERRALS with facts in hand."
  // Three of the four cannot honour an omit, and the copy walked past all of
  // them.
  //
  // A ninth deferral is added to `omitDeferralGuard` and both sides get it.
  if (omitDeferralGuard(field, mapping) !== null) {
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

  // ⚠️ SEPARATE FROM THE CONCEPT STAGE ON PURPOSE, AND THE TWO MUST NOT MERGE.
  // `conceptCandidates.length === 0` is the ONE site that earns #191's kept
  // practice default; this stage is a DEFERRAL that must not. A single combined
  // predicate cannot tell them apart and would silently re-route kept defaults.
  // ⚠️ temporalityMatches is TEMPORALITY-AGNOSTIC for the operative family (see
  // fact-mapping-match.ts) — the operative body mixes tenses. The agnostic check
  // lives in that ONE shared reader so this filter and the validator's
  // factMatchesMapping stay in agreement; a resolver-only fix cited off-tense
  // facts the validator then refused, withholding the whole native note.
  const temporalCandidates = conceptCandidates.filter((fact) =>
    temporalityMatches(fact, mapping),
  );
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

  // ⚠️ NON-NULL BY THE PRE-CONCEPT TABLE'S `clinical_concept_unmapped` ROW,
  // which returned above. TypeScript cannot see through the table walk, and a
  // second `if` here would be exactly the duplicate decision ruling #258 just
  // removed — so the guarantee is named and asserted, not re-tested.
  const normalizedConcept = normalizeConcept(mapping.clinicalConcept!);
  const permitsFamily = normalizedConcept.startsWith('family_history.');
  /**
   * ⚠️ #247 — THE REFERRING CLINICIAN IS THE ONE CONCEPT WHOSE SUBJECT IS NOT
   * THE PATIENT, AND WITHOUT THIS LINE IT COULD NEVER RESOLVE AT ALL.
   *
   * `experiencer` answers "who is this fact ABOUT", and the projector emits
   * `other` for the referrer because that is true — the fact is about a second
   * physician. Every other concept in the registry describes the patient, so
   * this gate is a correct default and a total refusal here: the field would
   * come back `ambiguous / experiencer_not_approved` on every visit that
   * dictated a referrer, which is precisely the visits it exists for.
   *
   * ⚠️ AND THE ALTERNATIVE WAS TO LIE IN THE PROJECTOR. Stamping the referrer
   * `experiencer: 'patient'` would have made this arm pass with no change
   * here — and written into the frozen manifest that a named outside physician
   * is the patient. Same shape as the `encounter_evidence` misattribution that
   * created the `visit_record` class: the cheap fix corrupts the audit trail
   * rather than the render, so nothing fails and the record is wrong.
   *
   * Named by CONCEPT, via the single shared set — NOT a hard-coded `||` string.
   *
   * ⚠️ WAS `=== 'visit_metadata.referring_physician'` — A SINGLE-CONCEPT WHITELIST,
   * AND A BLOCKING OWNER FINDING CAUGHT WHAT IT LEFT OUT. `procedure.surgeon` is
   * the signing clinician (record-derived, `experiencer: 'other'`, exactly like
   * the referrer), but it was not on the whitelist, so a certified operative note
   * came back `ambiguous / experiencer_not_approved` on Surgeon → FIELD_AMBIGUOUS
   * (blocking) → native render withheld → export surface hidden. The set
   * `OTHER_EXPERIENCER_CLINICIAN_CONCEPTS` is now the ONE source of truth for
   * "whose subject is a clinician", so adding the next such concept is a one-line
   * edit in the registry, not a second string here that drifts from it.
   */
  const permitsOtherClinician =
    OTHER_EXPERIENCER_CLINICIAN_CONCEPTS.has(normalizedConcept);
  if (
    temporalCandidates.some(
      (fact) =>
        fact.experiencer !== 'patient' &&
        !(permitsFamily && fact.experiencer === 'family') &&
        !(permitsOtherClinician && fact.experiencer === 'other'),
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
    // ══ OWNER RULING #157(c) Q3 — MIXED POLARITY RESOLVES PER FACT, AND
    // `polarity_conflict` DIES WITH ITS SIBLING. ══════════════════════════
    //
    // ⚠️ THIS RETURN IS THE DOCUMENT-KILLER #157(b) DID NOT REACH, AND IT IS
    // STRICTLY MORE COMMON THAN THE ONE IT DID. It fires BEFORE `allDenied` is
    // computed, so a field carrying ONE affirmed and ONE denied fact never saw
    // the denial contract at all: `conflict` -> FIELD_CONFLICT (always
    // blocking) -> `renderTemplateDocx` REJECTED, and the doctor loses the
    // WHOLE DOCUMENT. Measured, before this change:
    //
    //   [assessment "Pneumonia" affirmed, assessment "Pulmonary embolism" denied]
    //     -> conflict / polarity_conflict, valid=false, [FIELD_CONFLICT],
    //        render REJECTED
    //
    // A slice whose promise is that denials stop killing documents cannot ship
    // with this alive. `past_medical_history`, `family_history`, `allergy` and
    // `medication` are accumulating narratives in production and
    // "history of diabetes, no history of hypertension" is exactly this shape —
    // and the OWNER'S OWN ROS is mixed-polarity by construction.
    //
    // ⚠️ THE VERDICT IS PER FACT, NEVER PER FIELD, AND IT LIVES IN
    // `denial-contract.ts` BECAUSE THE VALIDATOR RE-DERIVES IT FROM THERE. A
    // second copy of this composition on the verify side would drift from this
    // one the day either is fixed, and what drifts is what reaches a signature.
    //
    // ⚠️ A REFUSAL LEAVES THE FIELD EXACTLY WHERE IT WAS. Everything the mixed
    // contract cannot resolve — a selection kind, a repeating section, two
    // distinct affirmed values on a narrative that is not an accumulating
    // SECTION, mixed laterality — falls through to the same `polarity_conflict`
    // it produced before. This widens what resolves; it narrows nothing.
    const mixed = mixedPolarityNarrative(field, mapping, judged);
    if (mixed.kind === 'text') {
      return makeResolution(
        field.fieldId,
        'supported',
        mixed.text,
        judged,
        mixed.reasonCode,
      );
    }
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
    const denial = denialOutcome(field, mapping);
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
          LIST_VALUED_NARRATIVE_JOINED_REASON,
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
    DIRECT_EVIDENCE_SUPPORTED_REASON,
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
  const refusalByFieldId = new Map(
    (input.refusals ?? []).map((r) => [r.fieldId, { unfilled: r.unfilled, required: r.required }]),
  );

  return [...fields]
    .sort((a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId))
    .map((field) =>
      resolveOne(
        field,
        mappingById.get(field.fieldId),
        facts,
        input.allowUncertifiedForSyntheticTest === true,
        certifiedFieldIds,
        refusalByFieldId.get(field.fieldId),
      ),
    );
}
