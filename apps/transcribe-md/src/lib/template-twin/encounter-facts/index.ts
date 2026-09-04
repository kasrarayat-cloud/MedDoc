// ============================================================================
// Template Twin — canonical encounter-fact projection
// ----------------------------------------------------------------------------
// Converts the existing Layer-3-shaped entity snapshot into provider-neutral,
// evidence-addressable facts. This module is deliberately deterministic: it
// never calls a model, never normalizes a clinical term into another term, and
// never fabricates offsets, timestamps, units, or laterality.
// ============================================================================

import { createHash } from 'node:crypto';

import { rosConcept } from '../ros-lexicon';

import {
  EncounterFactSchema,
  type EncounterFact,
} from '../ir';

export type EncounterInputMode = 'conversation' | 'dictation' | 'text';

export interface EvidenceSnapshot {
  evidence_quote: string;
  speaker?: string;
  timestamp?: number;
}

export interface FactSnapshot extends EvidenceSnapshot {
  [key: string]: unknown;
}

export interface EncounterEntitySnapshot {
  chief_complaint?: (EvidenceSnapshot & { statement: string }) | null;
  /** Structured measurements (L3, additive). Optional so a SOAP snapshot and
   *  every existing caller stay valid. */
  measurements?: Array<{
    segment: string;
    laterality: 'left' | 'right' | 'bilateral' | 'not_applicable' | 'unknown';
    metric: 'diameter' | 'reflux_time' | 'velocity' | 'length' | 'depth';
    value: number;
    unit: string;
    sourceSpan: string;
    speaker?: string;
    timestamp?: number;
  }> | null;
  hpi?: (EvidenceSnapshot & {
    onset?: string;
    duration?: string;
    quality?: string;
    severity?: string;
    location?: string;
    timing?: string;
    context?: string;
    modifying_factors?: string;
    associated_symptoms?: string;
  }) | null;
  past_medical_history?: ReadonlyArray<
    EvidenceSnapshot & { condition: string }
  >;
  medications?: ReadonlyArray<
    EvidenceSnapshot & {
      name: string;
      dose?: string | null;
      route?: string | null;
      frequency?: string | null;
    }
  >;
  allergies?: ReadonlyArray<
    EvidenceSnapshot & {
      substance: string;
      reaction?: string | null;
      superseded?: boolean;
      conflict_note?: string | null;
    }
  >;
  family_history?: ReadonlyArray<
    EvidenceSnapshot & { relation: string; condition: string }
  >;
  social_history?: {
    smoking?: (EvidenceSnapshot & { status: string }) | null;
    alcohol?: (EvidenceSnapshot & { status: string }) | null;
    drugs?: (EvidenceSnapshot & { status: string }) | null;
    occupation?: (EvidenceSnapshot & { value: string }) | null;
  };
  ros?: ReadonlyArray<
    EvidenceSnapshot & {
      system: string;
      finding: string;
      /** Q1 audit §02.9 — stated by L3. Optional HERE (not in the L3 schema,
       *  where it is required) so a snapshot captured before the field existed
       *  still projects, falling back to the inference it always used. */
      polarity?: 'affirmed' | 'denied';
      laterality?: 'left' | 'right' | 'bilateral';
    }
  >;
  exam_findings?: ReadonlyArray<
    EvidenceSnapshot & { system: string; finding: string }
  >;
  tests_mentioned?: ReadonlyArray<
    EvidenceSnapshot & { test: string; result_if_given?: string | null }
  >;
  assessment_discussed?: ReadonlyArray<
    EvidenceSnapshot & { finding: string }
  >;
  plan_discussed?: ReadonlyArray<EvidenceSnapshot & { item: string }>;
}

export interface ProjectEncounterFactsInput {
  mode: EncounterInputMode;
  /** Exact role-labelled transcript, dictation, or typed source passed to L3. */
  contextText: string;
  entities: EncounterEntitySnapshot;
  /** Optional upstream ASR assessment. Typed input should leave this unknown. */
  asrQuality?: 'high' | 'review' | 'unknown';
}

interface AddFactOptions {
  path: string;
  /** Fields extracted from one entity share an evidence group/anchor. */
  evidenceGroup?: string;
  concept: string;
  value: string | number | boolean;
  evidence: EvidenceSnapshot;
  defaultTemporality: EncounterFact['temporality'];
  experiencer?: EncounterFact['experiencer'];
  conflicting?: boolean;
  /** Structured overrides. Prose paths leave these unset and keep the inferred
   *  values, so every existing fact is byte-identical. */
  polarity?: EncounterFact['polarity'];
  laterality?: EncounterFact['laterality'];
  number?: number;
  unit?: string;
  /** Anatomical segment, carried as DATA so downstream addressing never has to
   *  parse it back out of prose. Emitted onto the fact as `segment`, and also
   *  hashed into the factId so two metrics on one vessel stay distinct.
   *
   *  ⚠️ THIS COMMENT USED TO SAY "Folded into the concept for matching", AND
   *  THAT WAS NEVER TRUE — the concept is a bare `measurement.<metric>`, and
   *  until F5-e the segment was consumed by the id hash and dropped. A reader
   *  who trusted it would conclude anatomy already reached the matcher. It did
   *  not, and twenty reflux cells rendered blank on a real signed document. */
  segment?: string;
}

const HPI_FIELDS = [
  'onset',
  'duration',
  'quality',
  'severity',
  'location',
  'timing',
  'context',
  'modifying_factors',
  'associated_symptoms',
] as const;

// ── DENIAL VOCABULARY — ONE LIST, TWO QUESTIONS ─────────────────────────────
// ⚠️ THE VOCABULARY IS UNCHANGED, DELIBERATELY. This is a fix to the SCOPE a
// denial is allowed to reach, not to the tokens. `EXPLICIT_DENIAL` below is
// REBUILT from this list and is byte-identical to the literal it replaced —
// `gate-polarity-scope` asserts its `.source` and `.flags` against that
// literal, so editing a token here reds CI.
//
// The list carries a ROLE, because the same vocabulary answers two different
// questions and asking the wrong one is the whole defect:
//
//   determiner — negates the NOUN PHRASE it heads. "no chest pain",
//                "never smoker", "no known drug allergies".
//   predicate  — negates the CLAUSE it sits in. "patient denies dysphagia",
//                "negative for melena", "not taking warfarin".
//
// ⚠️ WHAT WENT WRONG: `no\s+(?:known|current|evidence\s+of)?` has an OPTIONAL
// qualifier, so it collapses to a bare `no\s+`; tested against the FLAT
// `${value} ${quote}` concatenation — which is what shipped — ANY mid-sentence
// " no " flipped the WHOLE fact to 'denied'. Measured on compiled version
// 070090d3: "Stable chronic conditions with no acute change" resolved
// `explicitly_denied` with `value: null` on a narrative field, and
// `assertResolutionStatus` (note-template-docx/renderer.ts) refuses that pair.
// The doctor lost the WHOLE DOCUMENT — FIELD_RESOLUTION_INVALID — not one
// field, and no validation issue named the field on the way there.
export const DENIAL_VOCABULARY = [
  { token: 'den(?:y|ies|ied)', role: 'predicate' },
  { token: 'without', role: 'predicate' },
  { token: 'negative\\s+for', role: 'predicate' },
  { token: 'no\\s+(?:known|current|evidence\\s+of)?', role: 'determiner' },
  { token: 'not\\s+taking', role: 'predicate' },
  { token: 'never', role: 'determiner' },
] as const;

type DenialRole = (typeof DENIAL_VOCABULARY)[number]['role'];

function denialAlternation(role?: DenialRole): string {
  return DENIAL_VOCABULARY.filter(
    (entry) => role === undefined || entry.role === role,
  )
    .map((entry) => entry.token)
    .join('|');
}

/** Byte-identical to the literal that shipped. It is still the arm-(c)
 *  fallback, and it is the source of every cue the positional scan looks for —
 *  so the scan can never see a denial the old unscoped test could not. */
export const EXPLICIT_DENIAL = new RegExp(
  `(?:^|[\\s,;:])(?:${denialAlternation()})(?:\\b|$)`,
  'i',
);
/** The same pattern, global: arm (b) needs every cue AND its offsets. */
const DENIAL_CUES = new RegExp(EXPLICIT_DENIAL.source, 'gi');
/** Arm (a) — a denial that HEADS the value and negates it. */
const HEAD_DETERMINER = new RegExp(
  `^(?:${denialAlternation('determiner')})(?:\\b|$)`,
  'i',
);
/** Arm (d) — a denial that negates the CLAUSE it sits in.
 *  ⚠️ DELIBERATELY THE PREDICATE SUBSET, AGAINST THE ADVERSARIAL PASS'S
 *  RECOMMENDATION, AND THE REASON IS MEASURED. Widening this to the full
 *  vocabulary closes a checkbox-only false affirmation (D2) — but production
 *  has ZERO checkbox fields (112 narrative_text / 28 single_select / 10
 *  number), while the widening turns 18 LIVE facts (11 `assessment`, 2 `plan`,
 *  5 exam) from correctly affirmed back into `denied`. On a narrative field a
 *  denial is not a blank box, it is `explicitly_denied` + null and the renderer
 *  REFUSES THE WHOLE DOCUMENT. Measured: "Lungs clear to auscultation, no
 *  wheezes or rales." reads denied under the wide form.
 *  RETIRED WHEN: any uploaded .docx introduces a Word checkbox
 *  (note-template-docx/compiler.ts:492 modern SDT, :661 legacy), at which point
 *  the wide form becomes correct and this comment becomes wrong. */
const CLAUSE_PREDICATE = new RegExp(
  `(?:^|[\\s,;:])(?:${denialAlternation('predicate')})(?:\\b|$)`,
  'i',
);
/** "Allergies: no known drug allergies" — L3 keeps the section label on some
 *  values, and the determiner sits behind it. */
const VALUE_LABEL_PREFIX = /^\s*[A-Za-z][^:\n]{0,39}:\s*/;
const CLAUSE_BREAK = /[.;\n]/;
const REGEXP_METACHARACTERS = /[.*+?^${}()|[\]\\]/g;
const UNCERTAINTY =
  /\b(?:possible|possibly|maybe|may|might|uncertain|unclear|suspected|question\s+of)\b/i;
const CONDITIONAL = /\b(?:if|unless|in\s+case)\b/i;
const HISTORICAL =
  /\b(?:history\s+of|historical|previous(?:ly)?|prior|in\s+the\s+past|resolved)\b/i;
const PLANNED =
  /\b(?:plan(?:ned)?|will|schedule(?:d)?|refer(?:red|ral)?|start(?:ing)?|follow[- ]?up)\b/i;
const UNCLEAR_EVIDENCE = /\[unclear in recording\]|\binaudible\b/i;

function digest(value: string): string {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}

/**
 * Stable concept segment used for source-exposed system/test names. This is
 * identifier normalization only; it does not change the clinical meaning.
 */
export function conceptSegment(value: string): string {
  const segment = value
    .normalize('NFKC')
    .trim()
    .toLocaleLowerCase('en-US')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 80);
  return segment || 'unspecified';
}

/**
 * Case-INSENSITIVE offset of the value inside its own evidence quote, or -1.
 *
 * ⚠️ CASE-INSENSITIVITY IS LOAD-BEARING, NOT POLITENESS. L3 CAPITALISES the
 * finding while the quote keeps the sentence's own casing, so a case-sensitive
 * `indexOf` returns -1 for EVERY pinned entity on compiled version 070090d3
 * ("Stable chronic conditions…" vs "…stable chronic conditions…"), and every
 * positional arm below would fall through to the unscoped answer this entry
 * exists to stop using. A regex match rather than
 * `quote.toLowerCase().indexOf(value.toLowerCase())`, because lowercasing can
 * change a string's LENGTH and therefore every offset after it — and offsets
 * are precisely what arm (b) reasons about.
 */
function locateValueInQuote(value: string, quote: string): number {
  const match = new RegExp(
    value.replace(REGEXP_METACHARACTERS, '\\$&'),
    'i',
  ).exec(quote);
  return match ? match.index : -1;
}

/** End of the clause containing `from`, or the end of the text. */
function firstClauseEnd(text: string, from: number): number {
  const offset = text.slice(from).search(CLAUSE_BREAK);
  return offset === -1 ? text.length : from + offset;
}

/**
 * Does a denial GOVERN this value, or does it merely share a sentence with it?
 *
 * ⚠️ EVERY ARM IS A NARROWING OF THE OLD UNSCOPED TEST. Arms (a), (b) and (d)
 * all match with the SAME vocabulary and the same surrounding context as
 * `EXPLICIT_DENIAL`, over a SUBSET of the text it used to see, and (c) IS that
 * test. So this function's denied-set is a subset of the shipped one: it can
 * turn a denial into an affirmation, and it can never invent a denial that the
 * shipped code did not already make. `gate-polarity-scope` asserts that
 * relation over every fixture it carries.
 */
function denialGovernsValue(value: string, quote: string): boolean {
  const unscoped = (): boolean => EXPLICIT_DENIAL.test(`${value} ${quote}`);
  const stated = value.trim();
  if (!stated) return unscoped();

  // (a) DETERMINER AT THE HEAD OF THE VALUE, past an optional "Label:" prefix.
  if (HEAD_DETERMINER.test(stated)) return true;
  const unlabelled = stated.replace(VALUE_LABEL_PREFIX, '');
  if (unlabelled !== stated && HEAD_DETERMINER.test(unlabelled)) return true;

  // (c) THE VALUE IS NOT LOCATABLE IN ITS OWN QUOTE. Nothing positional can be
  // said, so keep the answer that shipped. Deliberately conservative: this is
  // where a paraphrased or joined value lands, and guessing there would be a
  // second defect rather than a fix for the first.
  const start = locateValueInQuote(stated, quote);
  if (start < 0) return unscoped();

  const clauseEnd = firstClauseEnd(quote, start);

  // (d) THE VALUE IS THE WHOLE STATEMENT, so (b) has nothing in front of it to
  // scan and would be vacuous. A denial PREDICATE in that statement's first
  // clause governs it. Without this arm "Patient denies dysphagia." reads
  // affirmed and a checkbox is TICKED for a denial.
  if (start === 0 && stated.length >= clauseEnd) {
    // ⚠️ PREDICATE ONLY — see CLAUSE_PREDICATE's own note. A determiner-carried
    // whole-statement denial ("There is no evidence of DVT.") reads AFFIRMED
    // here and that is a RECORDED RESIDUAL, pinned as gate rows h1-h4, not an
    // oversight. Widening it costs 18 live narrative facts a whole document.
    return CLAUSE_PREDICATE.test(quote.slice(0, clauseEnd));
  }

  // (b) POSITIONAL IN-CLAUSE SCAN. The nearest cue ENDING at or before the
  // value governs it, unless a clause break stands between the two. A cue
  // AFTER the value does not reach back — that is the entire bug.
  DENIAL_CUES.lastIndex = 0;
  let governingEnd = -1;
  let cue: RegExpExecArray | null;
  while ((cue = DENIAL_CUES.exec(quote)) !== null) {
    if (cue[0].length === 0) {
      DENIAL_CUES.lastIndex += 1;
      continue;
    }
    const end = cue.index + cue[0].length;
    // ⚠️ BREAK ON WHERE THE CUE *STARTS*, NOT WHERE IT ENDS. A cue that begins
    // BEFORE the value and ends INSIDE it aborted the whole scan, leaving
    // `governingEnd` unset and the fact AFFIRMED — "Denies chest pain" sits at
    // offset 5 in "ROS: denies chest pain." while its cue spans 4..11. That is
    // the SILENT direction: `convertValue` keys a checkbox on polarity alone,
    // so the box is TICKED for a finding the record explicitly denies. Five
    // shapes hit it (`Denies…`, `Negative for…`, `Not taking…`,
    // `known drug allergies`, `evidence of…`) and six live production facts.
    if (cue.index >= start) break;
    governingEnd = end;
  }
  if (governingEnd < 0) return false;
  return !CLAUSE_BREAK.test(quote.slice(governingEnd, start));
}

function inferPolarity(value: string | number | boolean, quote: string): EncounterFact['polarity'] {
  const text = `${String(value)} ${quote}`;
  // UNCERTAINTY and CONDITIONAL are UNCHANGED and still evaluated first, still
  // on the flat concatenation. This entry is about the denial arm alone.
  if (UNCERTAINTY.test(text)) return 'uncertain';
  if (CONDITIONAL.test(text)) return 'conditional';
  if (value === false) return 'denied';
  return denialGovernsValue(String(value), quote) ? 'denied' : 'affirmed';
}

function inferTemporality(
  value: string | number | boolean,
  quote: string,
  fallback: EncounterFact['temporality'],
): EncounterFact['temporality'] {
  const text = `${String(value)} ${quote}`;
  if (PLANNED.test(text)) return 'planned';
  if (HISTORICAL.test(text)) return 'historical';
  return fallback;
}

function inferLaterality(value: string | number | boolean, quote: string): EncounterFact['laterality'] {
  const text = `${String(value)} ${quote}`;
  if (/\b(?:bilateral|both\s+sides?)\b/i.test(text)) return 'bilateral';
  const left = /\bleft\b/i.test(text);
  const right = /\bright\b/i.test(text);
  if (left && right) return 'bilateral';
  if (left) return 'left';
  if (right) return 'right';
  if (/\bmidline\b/i.test(text)) return 'midline';
  return 'unknown';
}

/** Strict parsing only. Embedded or textual quantities remain unparsed. */
export function parseExplicitNumberAndUnit(
  value: string | number | boolean,
): { number: number | null; unit: string | null } {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return { number: value, unit: null };
  }
  if (typeof value !== 'string') return { number: null, unit: null };
  const match = value.trim().match(
    /^([+-]?(?:\d+(?:\.\d+)?|\.\d+))(?:\s*([A-Za-zµμ%][A-Za-z0-9µμ%/.\-]*(?:\s+[A-Za-z][A-Za-z0-9µμ%/.\-]*)*))?$/,
  );
  if (!match) return { number: null, unit: null };
  const parsed = Number(match[1]);
  if (!Number.isFinite(parsed)) return { number: null, unit: null };
  return { number: parsed, unit: match[2]?.trim() || null };
}

function nthExactOffset(
  contextText: string,
  quote: string,
  occurrence: number,
): { start: number; end: number } | null {
  let cursor = 0;
  let found = -1;
  for (let index = 0; index <= occurrence; index += 1) {
    found = contextText.indexOf(quote, cursor);
    if (found < 0) return null;
    cursor = found + quote.length;
  }
  return { start: found, end: found + quote.length };
}

/**
 * Project all supported Layer-3 entity categories. Facts remain ordered by the
 * source schema so manifests and tests are deterministic.
 */

/**
 * UNIT NORMALIZATION — lives here, not in the extractor.
 *
 * L3 records the value and unit EXACTLY as spoken ("0.62 centimeters",
 * "1800 milliseconds") and does no arithmetic: asking a language model to
 * convert is asking it to be a calculator, and a number that changes on the way
 * into a chart is the one defect this pipeline may never ship.
 *
 * Conversion is therefore deterministic code, in one place, with the canonical
 * unit chosen to match what the templates actually ask for:
 *   * lengths  -> mm      (0.62 cm  -> 6.2 mm)
 *   * durations-> seconds (1800 ms  -> 1.8 seconds)
 * The ORIGINAL value and unit stay in the fact's evidence quote, so the
 * conversion is always auditable against what was said.
 */
const LENGTH_TO_MM: Record<string, number> = {
  mm: 1, millimeter: 1, millimeters: 1, millimetre: 1, millimetres: 1,
  cm: 10, centimeter: 10, centimeters: 10, centimetre: 10, centimetres: 10,
};
const DURATION_TO_SECONDS: Record<string, number> = {
  s: 1, sec: 1, secs: 1, second: 1, seconds: 1,
  ms: 0.001, millisecond: 0.001, milliseconds: 0.001,
};

export function normalizeMeasurement(
  value: number,
  unit: string,
): { value: number; unit: string } {
  const u = unit.trim().toLowerCase().replace(/\./g, '');
  const lengthFactor = LENGTH_TO_MM[u];
  if (lengthFactor !== undefined) {
    // Round to 6dp to kill float noise (0.62 * 10 = 6.199999999999999).
    return { value: Number((value * lengthFactor).toFixed(6)), unit: 'mm' };
  }
  const durationFactor = DURATION_TO_SECONDS[u];
  if (durationFactor !== undefined) {
    return { value: Number((value * durationFactor).toFixed(6)), unit: 'seconds' };
  }
  // Unknown unit: pass through untouched rather than guess. The fact still
  // carries the spoken unit and the matcher compares numbers, so an
  // unrecognised unit degrades to "no match", never to a wrong number.
  return { value, unit: unit.trim() };
}

export function projectEncounterFacts(input: ProjectEncounterFactsInput): EncounterFact[] {
  const facts: EncounterFact[] = [];
  const quoteOccurrences = new Map<string, number>();
  const evidenceLocations = new Map<
    string,
    { occurrence: number; offsets: { start: number; end: number } | null }
  >();

  const add = (options: AddFactOptions): void => {
    const quote = options.evidence.evidence_quote;
    if (!quote || !quote.trim()) return;

    const evidenceGroup = options.evidenceGroup ?? options.path;
    let evidenceLocation = evidenceLocations.get(evidenceGroup);
    if (!evidenceLocation) {
      const occurrence = quoteOccurrences.get(quote) ?? 0;
      quoteOccurrences.set(quote, occurrence + 1);
      const preferredOffsets = nthExactOffset(
        input.contextText,
        quote,
        occurrence,
      );
      evidenceLocation = {
        occurrence,
        // A single exact source span can legitimately support multiple L3
        // entities (for example, two medications in one sentence). Reuse that
        // real span when there is no nth occurrence; never synthesize offsets.
        offsets:
          preferredOffsets ?? nthExactOffset(input.contextText, quote, 0),
      };
      evidenceLocations.set(evidenceGroup, evidenceLocation);
    }
    const { occurrence, offsets } = evidenceLocation;
    const numberAndUnit = parseExplicitNumberAndUnit(options.value);
    // A stated polarity beats an inferred one, always. The inference is a
    // fallback for the paths L3 does not state it on, not a second opinion.
    const polarity = options.polarity ?? inferPolarity(options.value, quote);
    const evidenceQuality: EncounterFact['quality']['evidence'] =
      options.conflicting
        ? 'conflicting'
        : polarity === 'uncertain' || polarity === 'conditional' || UNCLEAR_EVIDENCE.test(quote)
          ? 'unclear'
          : 'direct';
    const asr: EncounterFact['quality']['asr'] = UNCLEAR_EVIDENCE.test(quote)
      ? 'review'
      : input.mode === 'text'
        ? 'unknown'
        : input.asrQuality ?? 'unknown';
    const sourceIdentity = JSON.stringify({
      mode: input.mode,
      path: options.path,
      concept: options.concept,
      value: options.value,
      segment: options.segment ?? null,
      // Laterality is IDENTITY-BEARING for a measurement: the same 7 mm on the
      // right and the left are two different clinical facts, and collapsing
      // them to one id would let a right-leg value satisfy a left-leg row.
      laterality: options.laterality ?? null,
      quote,
      occurrence,
    });
    const anchorIdentity = JSON.stringify({
      mode: input.mode,
      quote,
      offsets,
      timestamp: options.evidence.timestamp ?? null,
      unresolvedGroup: offsets === null ? evidenceGroup : null,
    });

    facts.push(
      EncounterFactSchema.parse({
        factId: `ttfact_${digest(sourceIdentity).slice(0, 24)}`,
        sourceType: 'encounter_evidence',
        concept: options.concept,
        value: options.value,
        polarity,
        temporality: inferTemporality(
          options.value,
          quote,
          options.defaultTemporality,
        ),
        experiencer: options.experiencer ?? 'patient',
        laterality: options.laterality ?? inferLaterality(options.value, quote),
        number: options.number ?? numberAndUnit.number,
        unit: options.unit ?? numberAndUnit.unit,
        speaker: options.evidence.speaker?.slice(0, 80) ?? null,
        sourceTranscriptOffsets: offsets,
        audioTimestampSeconds:
          typeof options.evidence.timestamp === 'number' &&
          Number.isFinite(options.evidence.timestamp) &&
          options.evidence.timestamp >= 0
            ? options.evidence.timestamp
            : null,
        evidenceAnchorIds: [`ttev_${digest(anchorIdentity).slice(0, 24)}`],
        evidenceQuote: quote,
        // F5-e: the segment is EMITTED, not merely hashed into the factId above.
        // It reached this function and died here, which is the whole of F5-e.
        segment: options.segment ?? null,
        quality: { asr, evidence: evidenceQuality },
      }),
    );
  };

  // TranscribeVisit.entities is NULLABLE. The on-demand native-export path
  // feeds it straight through, so a visit whose L3 output was never persisted
  // (a legacy row, a failed pipeline, a re-export after cleanup) reached here
  // as null and threw "Cannot read properties of null (reading
  // 'chief_complaint')" — surfacing to the doctor as a silent styled fallback.
  // No entities means no evidence, which means no facts: an empty projection,
  // not an exception.
  const entities = input.entities ?? ({} as typeof input.entities);
  if (entities.chief_complaint) {
    add({
      path: 'chief_complaint.statement',
      concept: 'chief_complaint',
      value: entities.chief_complaint.statement,
      evidence: entities.chief_complaint,
      defaultTemporality: 'current',
    });
  }

  if (entities.hpi) {
    for (const field of HPI_FIELDS) {
      const value = entities.hpi[field];
      if (typeof value !== 'string' || !value) continue;
      add({
        path: `hpi.${field}`,
        evidenceGroup: 'hpi',
        concept: `hpi.${field}`,
        value,
        evidence: entities.hpi,
        defaultTemporality: 'current',
      });
    }
  }

  for (const [index, item] of (entities.past_medical_history ?? []).entries()) {
    add({
      path: `past_medical_history.${index}.condition`,
      concept: 'past_medical_history',
      value: item.condition,
      evidence: item,
      defaultTemporality: 'historical',
    });
  }

  for (const [index, item] of (entities.medications ?? []).entries()) {
    const fields: ReadonlyArray<[string, string | null | undefined]> = [
      ['name', item.name],
      ['dose', item.dose],
      ['route', item.route],
      ['frequency', item.frequency],
    ];
    for (const [field, value] of fields) {
      if (!value) continue;
      add({
        path: `medications.${index}.${field}`,
        evidenceGroup: `medications.${index}`,
        concept: `medication.${field}`,
        value,
        evidence: item,
        defaultTemporality: 'current',
      });
    }
  }

  for (const [index, item] of (entities.allergies ?? []).entries()) {
    add({
      path: `allergies.${index}.substance`,
      evidenceGroup: `allergies.${index}`,
      concept: 'allergy.substance',
      value: item.substance,
      evidence: item,
      defaultTemporality: 'current',
      conflicting: item.superseded === true || Boolean(item.conflict_note),
    });
    if (item.reaction) {
      add({
        path: `allergies.${index}.reaction`,
        evidenceGroup: `allergies.${index}`,
        concept: 'allergy.reaction',
        value: item.reaction,
        evidence: item,
        defaultTemporality: 'current',
        conflicting: item.superseded === true || Boolean(item.conflict_note),
      });
    }
  }

  for (const [index, item] of (entities.family_history ?? []).entries()) {
    add({
      path: `family_history.${index}.relation`,
      evidenceGroup: `family_history.${index}`,
      concept: 'family_history.relation',
      value: item.relation,
      evidence: item,
      defaultTemporality: 'historical',
      experiencer: 'family',
    });
    add({
      path: `family_history.${index}.condition`,
      evidenceGroup: `family_history.${index}`,
      concept: 'family_history.condition',
      value: item.condition,
      evidence: item,
      defaultTemporality: 'historical',
      experiencer: 'family',
    });
  }

  const social = entities.social_history;
  if (social?.smoking) {
    add({ path: 'social_history.smoking', concept: 'social_history.smoking', value: social.smoking.status, evidence: social.smoking, defaultTemporality: 'current' });
  }
  if (social?.alcohol) {
    add({ path: 'social_history.alcohol', concept: 'social_history.alcohol', value: social.alcohol.status, evidence: social.alcohol, defaultTemporality: 'current' });
  }
  if (social?.drugs) {
    add({ path: 'social_history.drugs', concept: 'social_history.drugs', value: social.drugs.status, evidence: social.drugs, defaultTemporality: 'current' });
  }
  if (social?.occupation) {
    add({ path: 'social_history.occupation', concept: 'social_history.occupation', value: social.occupation.value, evidence: social.occupation, defaultTemporality: 'current' });
  }

  for (const [index, item] of (entities.ros ?? []).entries()) {
    add({
      path: `ros.${index}.finding`,
      // ⚠️ #179(2) — SYMPTOM GRANULARITY. This emitted `ros.<system>` and every
      // clause in a system shared one concept, so the checkbox arm (which reads
      // polarity and discards the finding) ticked all of them from one fact,
      // and a second affirmed symptom conflicted the export. The symptom now
      // travels IN the concept, so a clause can address exactly what it covers.
      // Both halves come from the CLOSED lexicon the L3 schema enforces, so
      // this cannot produce a concept the registry will refuse.
      concept: rosConcept(conceptSegment(item.system), conceptSegment(item.finding)),
      value: item.finding,
      evidence: item,
      defaultTemporality: 'current',
      // Q1 audit §02.9 — L3 states these now, so stop guessing them back out of
      // the prose. Passed through only when present, so a snapshot taken before
      // the field existed keeps the inferred value and stays byte-identical.
      polarity: item.polarity,
      laterality: item.laterality,
    });
  }

  for (const [index, item] of (entities.exam_findings ?? []).entries()) {
    add({
      path: `exam_findings.${index}.finding`,
      concept: `exam.${conceptSegment(item.system)}`,
      value: item.finding,
      evidence: item,
      defaultTemporality: 'current',
    });
  }

  for (const [index, item] of (entities.tests_mentioned ?? []).entries()) {
    add({
      path: `tests_mentioned.${index}.test`,
      evidenceGroup: `tests_mentioned.${index}`,
      concept: 'test.name',
      value: item.test,
      evidence: item,
      defaultTemporality: 'current',
    });
    if (item.result_if_given) {
      add({
        path: `tests_mentioned.${index}.result`,
        evidenceGroup: `tests_mentioned.${index}`,
        concept: `test.${conceptSegment(item.test)}.result`,
        value: item.result_if_given,
        evidence: item,
        defaultTemporality: 'current',
      });
    }
  }

  for (const [index, item] of (entities.assessment_discussed ?? []).entries()) {
    add({
      path: `assessment_discussed.${index}.finding`,
      concept: 'assessment',
      value: item.finding,
      evidence: item,
      defaultTemporality: 'current',
    });
  }

  for (const [index, item] of (entities.plan_discussed ?? []).entries()) {
    add({
      path: `plan_discussed.${index}.item`,
      concept: 'plan',
      value: item.item,
      evidence: item,
      defaultTemporality: 'planned',
    });
  }

  // ── STRUCTURED MEASUREMENTS -> numeric EncounterFacts ────────────────────
  // These are what matchMeasurementFact needs and could never previously get:
  // a real number, a real laterality, and a traceable anchor. The matcher and
  // its requirements are untouched — they are simply satisfiable now.
  for (const m of entities.measurements ?? []) {
    if (!m || typeof m.value !== 'number' || !Number.isFinite(m.value)) continue;
    const norm = normalizeMeasurement(m.value, m.unit);
    add({
      // Concept is the measurement KIND ALONE — `measurement.diameter`. Anatomy
      // is NOT folded in here; it stays structured data on the fact
      // (`segment`, `laterality`), never invented into a per-field concept
      // string, so the concept keeps matching the registry's own vocabulary.
      //
      // ⚠️ This comment used to claim the concept carried "the segment as an
      // attribute-style suffix". It never did, and the segment was not on the
      // fact either — see the `segment` doc above and F5-e.
      path: `measurements.${m.metric}`,
      concept: `measurement.${m.metric}`,
      // A fact's `value` is its STATED FORM; `number` and `unit` are the
      // structured attributes beside it. Emitting a raw number here made the
      // fact contradict its own schema, and the validator noticed: it
      // re-derives a text cell's value as `typeof fact.value === 'string' ?
      // fact.value : null`, so every measurement the bridge placed — correct
      // number, correct leg, correct segment, real citation — came back
      // ASSERTION_NOT_SUPPORTED. The document's cells are text; the stated form
      // is what fills them.
      value: String(norm.value),
      evidence: {
        evidence_quote: m.sourceSpan,
        speaker: m.speaker,
        timestamp: m.timestamp,
      },
      defaultTemporality: 'current',
      laterality: m.laterality,
      number: norm.value,
      unit: norm.unit,
      // The segment travels with the fact so downstream addressing can align
      // it to a template row without parsing it back out of prose.
      segment: m.segment,
    });
  }

  return facts;
}
