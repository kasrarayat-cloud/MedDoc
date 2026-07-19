// ============================================================================
// Template Twin — canonical encounter-fact projection
// ----------------------------------------------------------------------------
// Converts the existing Layer-3-shaped entity snapshot into provider-neutral,
// evidence-addressable facts. This module is deliberately deterministic: it
// never calls a model, never normalizes a clinical term into another term, and
// never fabricates offsets, timestamps, units, or laterality.
// ============================================================================

import { createHash } from 'node:crypto';

import {
  EncounterFactSchema,
  type EncounterFact,
} from '../ir';
import {
  isSupportedTemplateTwinConcept,
  supportedProjectedSystemConcept,
} from '../supported-concepts';

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
    EvidenceSnapshot & { system: string; finding: string }
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

const EXPLICIT_DENIAL =
  /(?:^|[\s,;:])(?:den(?:y|ies|ied)|without|negative\s+for|no\s+(?:known|current|evidence\s+of)?|not\s+taking|never)(?:\b|$)/i;
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

function inferPolarity(value: string | number | boolean, quote: string): EncounterFact['polarity'] {
  const text = `${String(value)} ${quote}`;
  if (UNCERTAINTY.test(text)) return 'uncertain';
  if (CONDITIONAL.test(text)) return 'conditional';
  if (value === false || EXPLICIT_DENIAL.test(text)) return 'denied';
  return 'affirmed';
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

function uniqueExactOffset(
  contextText: string,
  quote: string,
): { start: number; end: number } | null {
  let cursor = 0;
  let onlyMatch = -1;
  let matchCount = 0;
  while (cursor <= contextText.length - quote.length) {
    const found = contextText.indexOf(quote, cursor);
    if (found < 0) break;
    matchCount += 1;
    if (matchCount > 1) return null;
    onlyMatch = found;
    // Advance one UTF-16 code unit so overlapping duplicate quotes are also
    // treated as ambiguous. Layer 3 does not provide a source span that could
    // safely distinguish either occurrence.
    cursor = found + 1;
  }
  return matchCount === 1
    ? { start: onlyMatch, end: onlyMatch + quote.length }
    : null;
}

/**
 * Structural proof available after projection has discarded the source text.
 * Exact quote equality is established by `uniqueExactOffset`; downstream
 * consumers can still reject null, empty, or quote-length-inconsistent spans
 * without trusting resolver status.
 */
export function hasExactEncounterEvidenceSpan(fact: EncounterFact): boolean {
  const offsets = fact.sourceTranscriptOffsets;
  return Boolean(
    offsets &&
      offsets.start < offsets.end &&
      offsets.end - offsets.start === fact.evidenceQuote.length,
  );
}

/**
 * Project all supported Layer-3 entity categories. Facts remain ordered by the
 * source schema so manifests and tests are deterministic.
 */
export function projectEncounterFacts(input: ProjectEncounterFactsInput): EncounterFact[] {
  const facts: EncounterFact[] = [];
  const evidenceLocations = new Map<
    string,
    { offsets: { start: number; end: number } | null }
  >();
  const sourceEvidenceSha256 = digest(input.contextText);

  const add = (options: AddFactOptions): void => {
    // Layer 3 may contain specialty detail outside the bounded safe-alpha
    // Template Twin registry. Generic SOAP keeps that source data, while Twin
    // fact projection refuses to create an apparently supported concept that
    // certification/runtime cannot independently validate.
    if (!isSupportedTemplateTwinConcept(options.concept)) return;
    const quote = options.evidence.evidence_quote;
    if (!quote || !quote.trim()) return;

    const evidenceGroup = options.evidenceGroup ?? options.path;
    let evidenceLocation = evidenceLocations.get(evidenceGroup);
    if (!evidenceLocation) {
      evidenceLocation = {
        // Core L3 output does not carry source offsets. A quote therefore has
        // an exact usable anchor only when it occurs verbatim exactly once in
        // the canonical source. Compound facts may share that one real span.
        // Missing, non-exact, and duplicate quotes remain unanchored so the
        // resolver and independent validator can fail closed.
        offsets: uniqueExactOffset(input.contextText, quote),
      };
      evidenceLocations.set(evidenceGroup, evidenceLocation);
    }
    const { offsets } = evidenceLocation;
    const numberAndUnit = parseExplicitNumberAndUnit(options.value);
    const polarity = inferPolarity(options.value, quote);
    const evidenceQuality: EncounterFact['quality']['evidence'] =
      options.conflicting
        ? 'conflicting'
        : offsets === null ||
            polarity === 'uncertain' ||
            polarity === 'conditional' ||
            UNCLEAR_EVIDENCE.test(quote)
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
      quote,
      offsets,
    });
    const anchorIdentity = JSON.stringify({
      mode: input.mode,
      sourceEvidenceSha256,
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
        laterality: inferLaterality(options.value, quote),
        number: numberAndUnit.number,
        unit: numberAndUnit.unit,
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
        quality: { asr, evidence: evidenceQuality },
      }),
    );
  };

  const entities = input.entities;
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
    const concept = supportedProjectedSystemConcept('ros', item.system);
    if (!concept) continue;
    add({
      path: `ros.${index}.finding`,
      concept,
      value: item.finding,
      evidence: item,
      defaultTemporality: 'current',
    });
  }

  for (const [index, item] of (entities.exam_findings ?? []).entries()) {
    const concept = supportedProjectedSystemConcept('exam', item.system);
    if (!concept) continue;
    add({
      path: `exam_findings.${index}.finding`,
      concept,
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

  return facts;
}
