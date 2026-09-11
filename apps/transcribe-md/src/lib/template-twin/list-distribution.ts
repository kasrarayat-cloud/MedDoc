// ============================================================================
// Template Twin — ONE ITEM PER BULLET, ruling #313.
// ----------------------------------------------------------------------------
// When a form repeats one list-valued control as bullets, each dictated item
// goes on its own bullet. Nothing is dropped, and nothing is printed twice.
//
// Before this pass every member of a bullet run resolved on its own and printed
// the WHOLE joined list — measured on the owner's certified, active form:
// Past Medical History ×3, Impression ×4 and Plan ×5 each printed the full list.
//
// ── WHERE IT RUNS ───────────────────────────────────────────────────────────
// Once, in `prepareTemplateTwinFill`, AFTER the bridge overlay and BEFORE the
// clinician overrides. Every path converges there (certification round trip,
// visit fill, on-demand export, sign-time re-fill, pre-sign preview, the
// insert-default door). Running before the overrides is what keeps a doctor's
// own edit winning, and it means #194's blank-only rule judges the state AFTER
// distribution — the same state the preview offer and the door see.
//
// ── WHAT IT PROMISES ────────────────────────────────────────────────────────
//   · it acts only on a group `bulletGroups` accepts, and only when every
//     member came out of the resolver IDENTICAL (`supported`, same value, same
//     citations, same reason). Anything else is left exactly as it is;
//   · it MINTS NO FACTS, so the fact-set sha is unchanged;
//   · it is ORDER-INDEPENDENT (members are taken in display order) and returns
//     its input in its input order;
//   · every rewritten bullet's value is composed by the functions the validator
//     RE-DERIVES with — imported, never re-stated;
//   · it re-validates its own output and COLLAPSES ("bullet 1 = today's
//     resolution, the rest unused") on any doubt. If even the collapse would
//     add a blocking issue, the group is left untouched. THE PASS CAN NEVER BE
//     THE REASON A DOCUMENT IS WITHHELD.
// ============================================================================

import {
  FieldResolutionSchema,
  LIST_ITEM_SLOT_UNUSED_REASON,
  type EncounterFact,
  type FieldResolution,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateField,
} from './ir';
import { bulletGroups } from './bullet-groups';
import {
  DIRECT_EVIDENCE_SUPPORTED_REASON,
  LIST_VALUED_NARRATIVE_JOINED_REASON,
  deriveFieldValueFromFact,
  joinListValuedNarrative,
} from './field-value-derivation';
import { MIXED_POLARITY_REASON, mixedPolarityNarrative } from './denial-contract';
import { evidenceFor } from './resolver';
import { assertionSupported, validateTemplateTwin } from './validation';

/**
 * The reasons a group may be distributed FROM. These are the three a
 * `supported` narrative can carry from its own evidence; a clinician default,
 * a practice default, a record value or a bridge fill is never redistributed.
 */
const DISTRIBUTABLE_REASONS: ReadonlySet<string> = new Set([
  DIRECT_EVIDENCE_SUPPORTED_REASON,
  LIST_VALUED_NARRATIVE_JOINED_REASON,
  MIXED_POLARITY_REASON,
]);

/** A fixed validation clock for the self-check: only the ISSUES are compared. */
const SELF_CHECK_NOW = '1970-01-01T00:00:00.000Z';

export type ListDistributionOutcome =
  | { readonly kind: 'untouched'; readonly reason: string }
  | { readonly kind: 'distributed'; readonly items: number; readonly bullets: number }
  | { readonly kind: 'collapsed'; readonly reason: string };

/** One group's proposed resolutions, as handed to a self-check. */
export interface ListDistributionCandidate {
  readonly members: readonly TemplateField[];
  readonly mappings: readonly SemanticMapping[];
  readonly facts: readonly EncounterFact[];
  /** Member resolutions, in member (display) order. */
  readonly proposed: readonly FieldResolution[];
  /** The same members as they came in — today's output. */
  readonly baseline: readonly FieldResolution[];
}

export interface DistributeListItemsInput {
  readonly ir: Pick<TemplateDocIR, 'fields'>;
  readonly mappings: readonly SemanticMapping[];
  /** Lookup only — every fact the fill can cite. The pass mints none. */
  readonly facts: readonly EncounterFact[];
  readonly resolutions: readonly FieldResolution[];
  /**
   * ⚠️ TEST SEAM ONLY. Replaces the self-check applied to a DISTRIBUTED
   * proposal (never to the collapse, which is always checked by the built-in
   * validator comparison). Production callers never pass it.
   */
  readonly acceptDistribution?: (candidate: ListDistributionCandidate) => boolean;
}

export interface ListDistributionPlan {
  readonly resolutions: FieldResolution[];
  readonly outcomes: ReadonlyArray<{
    readonly memberFieldIds: readonly string[];
    readonly outcome: ListDistributionOutcome;
  }>;
}

function sameOrdered(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function unusedSlot(fieldId: string): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId,
    status: 'not_mentioned',
    value: null,
    sourceFactIds: [],
    evidenceAnchorIds: [],
    selectedOptionOrdinal: null,
    reasonCode: LIST_ITEM_SLOT_UNUSED_REASON,
    clinicianReviewed: false,
  });
}

/**
 * One bullet's resolution for exactly these facts (already in the shared
 * resolution's citation order), or `null` when no shared composer will produce
 * a value for them — a doubt, which collapses the group.
 */
function composeBullet(
  field: TemplateField,
  mapping: SemanticMapping,
  facts: readonly EncounterFact[],
): FieldResolution | null {
  let value: string;
  let reasonCode: string;
  if (facts.some((fact) => fact.polarity === 'denied')) {
    // The denied facts ride on bullet 1 so FIELD_MIXED_POLARITY_DENIAL_WITHHELD
    // fires once rather than N times. The value is the affirmed facts' own text,
    // byte-identical to what the validator's mixed branch re-derives.
    const mixed = mixedPolarityNarrative(field, mapping, facts);
    if (mixed.kind !== 'text') return null;
    value = mixed.text;
    reasonCode = MIXED_POLARITY_REASON;
  } else if (facts.length > 1) {
    // Duplicate-text items and the overflow bullet: the join path.
    const joined = joinListValuedNarrative(field, mapping, facts);
    if (joined === null) return null;
    value = joined;
    reasonCode = LIST_VALUED_NARRATIVE_JOINED_REASON;
  } else {
    // ⚠️ ONE FACT: THE STRICT, UNTRIMMED PATH. The validator re-derives a
    // one-fact narrative with `deriveFieldValueFromFact` and compares with `===`
    // — never the join, which trims. Splitting the joined string instead would
    // lose a trailing space and break an item that itself contains "; ".
    const derived = deriveFieldValueFromFact(field, mapping, facts[0]!);
    if (typeof derived !== 'string') return null;
    value = derived;
    reasonCode = DIRECT_EVIDENCE_SUPPORTED_REASON;
  }
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'supported',
    value,
    ...evidenceFor(facts),
    selectedOptionOrdinal: null,
    reasonCode,
    clinicianReviewed: false,
  });
}

/**
 * The built-in self-check: the group's resolutions, validated on their own by
 * THE validator, must raise no BLOCKING issue the untouched group did not
 * already raise. That covers the per-field re-derivation, the anchor rules,
 * the required-blank exemption and the three #313 group checks at once, and it
 * is the validator's own verdict rather than a model of it.
 */
function introducesNoBlocking(candidate: ListDistributionCandidate): boolean {
  const blocking = (resolutions: readonly FieldResolution[]): string[] =>
    validateTemplateTwin({
      fields: candidate.members,
      mappings: candidate.mappings,
      facts: candidate.facts,
      resolutions,
      allowUncertifiedForSyntheticTest: true,
      now: SELF_CHECK_NOW,
    })
      .issues.filter((issue) => issue.severity === 'blocking')
      .map((issue) => `${issue.fieldId ?? ''}\0${issue.code}`);
  const before = new Set(blocking(candidate.baseline));
  return blocking(candidate.proposed).every((key) => before.has(key));
}

/**
 * Place one dictated item per bullet across every accepted bullet group, and
 * report what happened to each group.
 */
export function planListDistribution(input: DistributeListItemsInput): ListDistributionPlan {
  const fields = input.ir.fields;
  const fieldById = new Map(fields.map((field) => [field.fieldId, field]));
  const mappingById = new Map(input.mappings.map((mapping) => [mapping.fieldId, mapping]));
  const resolutionById = new Map<string, FieldResolution>();
  const duplicated = new Set<string>();
  for (const resolution of input.resolutions) {
    if (resolutionById.has(resolution.fieldId)) duplicated.add(resolution.fieldId);
    else resolutionById.set(resolution.fieldId, resolution);
  }
  // A duplicated resolution is a doubt the validator reports (DUPLICATE_RESOLUTION);
  // it is removed so no group containing it can be rewritten.
  for (const fieldId of duplicated) resolutionById.delete(fieldId);
  const factById = new Map<string, EncounterFact>();
  for (const fact of input.facts) {
    if (!factById.has(fact.factId)) factById.set(fact.factId, fact);
  }

  const replacements = new Map<string, FieldResolution>();
  const outcomes: Array<ListDistributionPlan['outcomes'][number]> = [];

  for (const group of bulletGroups(fields, input.mappings)) {
    const members = group.memberFieldIds.map((id) => fieldById.get(id)!);
    const memberMappings = members.map((field) => mappingById.get(field.fieldId)!);
    const record = (outcome: ListDistributionOutcome) =>
      outcomes.push({ memberFieldIds: group.memberFieldIds, outcome });
    const untouched = (reason: string) => record({ kind: 'untouched', reason });

    // ── ELIGIBILITY: every member came out of the resolver identical ───────
    const current = members.map((field) => resolutionById.get(field.fieldId));
    if (current.some((resolution) => resolution === undefined)) {
      untouched('resolution_missing');
      continue;
    }
    const baseline = current as FieldResolution[];
    const shared = baseline[0]!;
    const eligible = baseline.every(
      (resolution) =>
        resolution.status === 'supported' &&
        typeof resolution.value === 'string' &&
        resolution.clinicianReviewed === false &&
        resolution.selectedOptionOrdinal === null &&
        DISTRIBUTABLE_REASONS.has(resolution.reasonCode),
    );
    if (!eligible) {
      untouched('member_not_distributable');
      continue;
    }
    if (
      !baseline.every(
        (resolution) =>
          resolution.value === shared.value &&
          resolution.reasonCode === shared.reasonCode &&
          sameOrdered(resolution.sourceFactIds, shared.sourceFactIds) &&
          sameOrdered(resolution.evidenceAnchorIds, shared.evidenceAnchorIds),
      )
    ) {
      untouched('members_differ');
      continue;
    }
    if (new Set(shared.sourceFactIds).size !== shared.sourceFactIds.length) {
      untouched('citation_repeats');
      continue;
    }
    const cited = shared.sourceFactIds.map((id) => factById.get(id));
    if (cited.some((fact) => fact === undefined)) {
      untouched('cited_fact_missing');
      continue;
    }
    const citedFacts = cited as EncounterFact[];
    // Items are DICTATED facts. A resolution citing anything else is not one
    // this pass was built for, and a doubt leaves it alone.
    if (citedFacts.some((fact) => fact.sourceType !== 'encounter_evidence')) {
      untouched('cited_fact_not_dictated');
      continue;
    }
    const denied = citedFacts.filter((fact) => fact.polarity === 'denied');
    const affirmed = citedFacts.filter((fact) => fact.polarity === 'affirmed');
    if (denied.length + affirmed.length !== citedFacts.length) {
      untouched('polarity_not_binary');
      continue;
    }

    // ── ITEMS: grouped by the join's OWN de-duplication key ───────────────
    // `String(derived).trim()` is exactly what `joinListValuedNarrative`
    // collapses on, so "HTN" and "HTN " are ONE item citing both facts — never
    // two bullets reading the same thing.
    const items: EncounterFact[][] = [];
    const itemIndexByText = new Map<string, number>();
    let itemDoubt: string | null = null;
    for (const fact of affirmed) {
      const derived = deriveFieldValueFromFact(members[0]!, memberMappings[0]!, fact);
      if (derived === null) {
        itemDoubt = 'item_does_not_derive';
        break;
      }
      const text = String(derived).trim();
      if (!text) {
        itemDoubt = 'item_empty';
        break;
      }
      const at = itemIndexByText.get(text);
      if (at === undefined) {
        itemIndexByText.set(text, items.length);
        items.push([fact]);
      } else {
        items[at]!.push(fact);
      }
    }
    if (itemDoubt !== null) {
      untouched(itemDoubt);
      continue;
    }
    if (items.length === 0) {
      untouched('no_affirmed_item');
      continue;
    }

    const bullets = members.length;
    const collapsed = members.map((field, index) =>
      index === 0 ? shared : unusedSlot(field.fieldId),
    );
    const candidateFor = (proposed: readonly FieldResolution[]): ListDistributionCandidate => ({
      members,
      mappings: memberMappings,
      facts: input.facts,
      proposed,
      baseline,
    });

    // ── PLACEMENT ──────────────────────────────────────────────────────────
    let proposed: FieldResolution[] | null;
    let collapseReason: string | null = null;
    if (items.length === 1) {
      // K = 1: bullet 1 keeps today's resolution BYTE-IDENTICALLY — nothing is
      // re-derived — and the rest are unused.
      proposed = collapsed;
    } else {
      // 2 <= K <= N: one item per bullet. K > N: bullets 1..N-1 one item each,
      // bullet N the REMAINDER joined (ruling #313 O2 — never drop, never
      // withhold).
      const assigned: EncounterFact[][] = members.map((_, index) =>
        index < bullets - 1 ? (items[index] ?? []) : items.slice(bullets - 1).flat(),
      );
      assigned[0] = [...assigned[0]!, ...denied];
      proposed = [];
      for (let index = 0; index < bullets; index += 1) {
        const mine = new Set(assigned[index]!.map((fact) => fact.factId));
        if (mine.size === 0) {
          proposed.push(unusedSlot(members[index]!.fieldId));
          continue;
        }
        // Each bullet cites only its own facts, in the SHARED resolution's
        // order — which is dictation order, and the order the validator's
        // re-derivation reads.
        const ordered = citedFacts.filter((fact) => mine.has(fact.factId));
        const bullet = composeBullet(members[index]!, memberMappings[index]!, ordered);
        if (bullet === null) {
          collapseReason = 'composer_refused';
          proposed = null;
          break;
        }
        proposed.push(bullet);
      }
    }

    // ── SELF-CHECK, THEN COLLAPSE RATHER THAN WITHHOLD ─────────────────────
    if (proposed !== null && proposed !== collapsed) {
      const perFieldOk = proposed.every((resolution, index) => {
        if (resolution.value === null) return true;
        const facts = resolution.sourceFactIds.map((id) => factById.get(id)!);
        return assertionSupported(members[index]!, memberMappings[index]!, resolution, facts);
      });
      if (!perFieldOk) {
        collapseReason = 'assertion_not_supported';
        proposed = null;
      } else if (!(input.acceptDistribution ?? introducesNoBlocking)(candidateFor(proposed))) {
        collapseReason = 'self_check_failed';
        proposed = null;
      }
    }
    const final = proposed ?? collapsed;
    // ⚠️ THE COLLAPSE IS CHECKED TOO, WITH THE BUILT-IN CHECK ONLY. It cites the
    // whole candidate set on bullet 1, so it is expected to validate — and if
    // it ever did not, the group is left exactly as it came in.
    if (!introducesNoBlocking(candidateFor(final))) {
      untouched('collapse_failed_self_check');
      continue;
    }
    if (collapseReason !== null) {
      // Reason code only — never a value, a label or a fact.
      console.info(
        `[template-twin:distribute] collapsed reason=${collapseReason} bullets=${bullets}`,
      );
      record({ kind: 'collapsed', reason: collapseReason });
    } else {
      record({ kind: 'distributed', items: items.length, bullets });
    }
    members.forEach((field, index) => replacements.set(field.fieldId, final[index]!));
  }

  return {
    resolutions: input.resolutions.map(
      (resolution) => replacements.get(resolution.fieldId) ?? resolution,
    ),
    outcomes,
  };
}

/** THE pass, as the fill engine calls it: resolutions in, resolutions out. */
export function distributeListItems(input: DistributeListItemsInput): FieldResolution[] {
  return planListDistribution(input).resolutions;
}
