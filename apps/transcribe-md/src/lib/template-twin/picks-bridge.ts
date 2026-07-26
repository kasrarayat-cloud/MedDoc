// ============================================================================
// Template Twin — CHOICE_SLOT picks -> IR field resolutions bridge (Phase 2c).
// ----------------------------------------------------------------------------
// The LIVE brain (build-soap-prompt CHOICE_SLOT fill) fills each {{one of: …}}
// marker in the generated note with EXACTLY ONE of its listed options (or drops
// it when undictated). This bridge maps those picks onto the twin IR's
// single-select FieldResolutions that renderTemplateDocx consumes:
//   - marker N (document order) -> the Nth single_select IR field (displayOrder)
//     — order is stable because both derive from the same docx in document order,
//     which also disambiguates the Right/Left duplicated dropdowns.
//   - a pick is accepted ONLY on an EXACT match to one of that field's enumerated
//     options (case/space-normalised); never an off-list value.
//   - blank stays blank: a dropped marker / omitted carrier line / unmatched pick
//     resolves to `not_mentioned` (null), never invented.
// Non-select fields (narrative/table/measurement) are out of this bridge's scope
// and resolve to not_mentioned here; the fill engine's resolver owns those.
//
// Pure + deterministic. No I/O, no AI.
// ============================================================================

import { createHash } from 'node:crypto';

import { EMPTY_SECTION_PLACEHOLDER } from '@/lib/soap-format';

import type { EncounterFact, SemanticMapping } from './ir';
import { buildVerifiedNoteSelectionFact } from './verified-note-selection';
import {
  FieldResolutionSchema,
  type FieldResolution,
  type TemplateDocIR,
  type TemplateField,
} from './ir';

const MARKER_RE = /\{\{one of:\s*([^}]*)\}\}/g;

function norm(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, ' ');
}

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Split a marker-text line into its fixed segments and per-marker option lists,
 *  in order. A line with no markers yields optionLists=[]. */
function splitLine(line: string): { fixed: string[]; optionLists: string[][] } {
  const fixed: string[] = [];
  const optionLists: string[][] = [];
  let last = 0;
  for (const m of line.matchAll(MARKER_RE)) {
    fixed.push(line.slice(last, m.index));
    optionLists.push(m[1].split('|').map((o) => o.trim()).filter(Boolean));
    last = m.index + m[0].length;
  }
  fixed.push(line.slice(last));
  return { fixed, optionLists };
}

/** Recover the picks for one marker-text line by locating the matching filled
 *  line. Each capture is CONSTRAINED to that marker's own options (longest-first
 *  alternation), so multi-marker chains ("The <vein> from <seg> to <seg>") never
 *  mis-boundary and an off-list value simply fails to match (-> blank). Returns
 *  one entry per marker: the picked option text, or null when the line/marker is
 *  absent (undictated carrier omitted). */
function alignLineFrom(
  markerLine: string,
  filledLines: string[],
  startIdx: number,
): { picks: (string | null)[]; matchedAt: number } {
  const { fixed, optionLists } = splitLine(markerLine);
  if (optionLists.length === 0) return { picks: [], matchedAt: -1 };
  const alt = (opts: string[]): string =>
    '(' +
    [...opts]
      .sort((a, b) => b.length - a.length) // longest first: "distal thigh" before "thigh"
      .map((o) => escapeRe(o.trim()))
      .join('|') +
    ')';
  const pattern =
    '^\\s*' +
    fixed.map((f, i) => escapeRe(f.trim()) + (i < optionLists.length ? '\\s*' + alt(optionLists[i]) + '\\s*' : '')).join('') +
    '\\s*$';
  let re: RegExp;
  try {
    re = new RegExp(pattern, 'i');
  } catch {
    return { picks: optionLists.map(() => null), matchedAt: -1 };
  }
  // Consume forward from startIdx so duplicated carriers (Right then Left leg)
  // map to their own filled line in document order, never the same first hit.
  for (let i = startIdx; i < filledLines.length; i++) {
    const mm = re.exec(filledLines[i].trim());
    if (mm) return { picks: optionLists.map((_, k) => mm[k + 1] ?? null), matchedAt: i };
  }
  return { picks: optionLists.map(() => null), matchedAt: -1 }; // line omitted -> blank
}

/** A pick is written ONLY under the verified-note-selection rules, and it cites
 *  the selection itself. Every check is enforced here; none is waived.
 *
 *  The earlier rule — a pick must be entailed by an extracted fact — could not
 *  hold: the options are protocol language ("Bilateral Detailed", "Swelling,
 *  Heaviness") and no extractor emits facts that read like that. It left every
 *  dropdown blank on every real visit while the note had selected them
 *  correctly, and the native export refused the document as incomplete. */
function supported(
  field: TemplateField,
  value: string,
  ordinal: number,
  markerOrdinal: number,
  noteSha256: string,
  mapping?: SemanticMapping,
): { resolution: FieldResolution; fact: EncounterFact } | null {
  // A citation needs a concept to satisfy. Without one there is nothing for the
  // validator to check the fact against, so the field stays blank.
  if (!mapping?.clinicalConcept) {
    console.info(
      `[template-twin:bridge] pick left blank field=${field.fieldId} reason=no_approved_concept`,
    );
    return null;
  }
  const fact = buildVerifiedNoteSelectionFact({
    field,
    mapping,
    optionValue: value,
    markerOrdinal,
    noteSha256,
  });
  return {
    fact,
    resolution: FieldResolutionSchema.parse({
      fieldId: field.fieldId,
      status: 'supported',
      value,
      sourceFactIds: [fact.factId],
      evidenceAnchorIds: [...fact.evidenceAnchorIds],
      selectedOptionOrdinal: ordinal,
      reasonCode: 'choice_slot_pick',
      clinicianReviewed: false,
    }),
  };
}
function notMentioned(field: TemplateField): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'not_mentioned',
    value: null,
    sourceFactIds: [],
    evidenceAnchorIds: [],
    selectedOptionOrdinal: null,
    reasonCode: 'blank_when_unsaid',
    clinicianReviewed: false,
  });
}

export interface BridgeChoiceSlotPicksInput {
  ir: TemplateDocIR;
  /** L3 EncounterFacts. Picks no longer draw their evidence from here — see
   *  verified-note-selection.ts — but the set is kept so a future class can. */
  facts: readonly EncounterFact[];
  /** Approved mappings — a citation must satisfy the validator's rule. */
  mappings?: readonly SemanticMapping[];
  /** The {{one of}} marker text the template was compiled/parsed from. */
  markerText: string;
  /** The ADOPTED note (markers filled with picks). Single-source rule: this is
   *  the note that will be signed and exported, never a draft or a suggestion
   *  lane — a pick the doctor has not adopted is not a selection. */
  filledNote: string;
}

export interface BridgeChoiceSlotPicksResult {
  resolutions: FieldResolution[];
  /** The provenance facts the accepted picks cite. They MUST reach the manifest's
   *  fact set, or the validator will (rightly) call the citations untraceable. */
  facts: EncounterFact[];
}

/** Section labels whose body still carries the anchored verifier's set-aside
 *  placeholder. Content there was DEMOTED for the clinician to review; a pick
 *  inside it has not been adopted, so it cannot be a verified selection. The
 *  verifier's grounding is cited, never rebuilt or second-guessed here. */
function setAsideLineIndexes(filledLines: readonly string[]): Set<number> {
  const out = new Set<number>();
  let inSetAside = false;
  filledLines.forEach((line, i) => {
    const t = line.trim();
    if (/^#{1,6}\s/.test(t)) inSetAside = false;
    if (t === EMPTY_SECTION_PLACEHOLDER) inSetAside = true;
    if (inSetAside) out.add(i);
  });
  return out;
}

/**
 * Map the note's CHOICE_SLOT picks onto exact-option single-select resolutions.
 * Every field in `ir` gets a resolution (selects filled from picks; everything
 * else not_mentioned). Constrained-fill invariants hold: only listed options,
 * blank when unsaid, never off-list.
 */
export function bridgeChoiceSlotPicks(
  input: BridgeChoiceSlotPicksInput,
): BridgeChoiceSlotPicksResult {
  const { ir, markerText, filledNote } = input;
  const selectFields = ir.fields
    .filter((f) => f.kind === 'single_select' && f.detectionStatus !== 'unsupported' && !f.rowPrototype)
    .sort((a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId));

  const filledLines = filledNote.split('\n');
  const setAside = setAsideLineIndexes(filledLines);
  // The note's identity travels into every citation, so a re-generated or edited
  // note can never reuse a prior manifest's provenance.
  const noteSha256 = createHash('sha256').update(filledNote).digest('hex');

  const picks: Array<{ value: string | null; lineIndex: number }> = [];
  let cursor = 0;
  for (const line of markerText.split('\n')) {
    MARKER_RE.lastIndex = 0;
    if (!MARKER_RE.test(line)) continue;
    MARKER_RE.lastIndex = 0;
    const { picks: linePicks, matchedAt } = alignLineFrom(line, filledLines, cursor);
    picks.push(...linePicks.map((value) => ({ value, lineIndex: matchedAt })));
    if (matchedAt >= 0) cursor = matchedAt + 1;
  }

  // Nth pick -> Nth single_select field (document order).
  const pickByFieldId = new Map<string, { value: string | null; lineIndex: number; ordinal: number }>();
  selectFields.forEach((field, i) => {
    const p = picks[i];
    pickByFieldId.set(field.fieldId, {
      value: p?.value ?? null,
      lineIndex: p?.lineIndex ?? -1,
      ordinal: i,
    });
  });

  const facts: EncounterFact[] = [];
  const resolutions = ir.fields.map((field) => {
    const pick = pickByFieldId.get(field.fieldId);
    if (!pick) return notMentioned(field);
    if (pick.value == null || pick.value === '') return notMentioned(field);

    // (c) NOT FROM THE SET-ASIDE LANE. Content the anchored verifier demoted is
    // awaiting the clinician; a pick sitting in it has not been adopted.
    if (pick.lineIndex >= 0 && setAside.has(pick.lineIndex)) {
      console.info(
        `[template-twin:bridge] pick left blank field=${field.fieldId} reason=set_aside_not_adopted`,
      );
      return notMentioned(field);
    }

    // (a) VERBATIM, never fuzzy: the value must BE one of this field's own
    // enumerated options. An off-list value is not a selection.
    const opt = field.allowedOptions.find(
      (o) => norm(o.displayText) === norm(pick.value!) || norm(o.value) === norm(pick.value!),
    );
    if (!opt) {
      console.info(
        `[template-twin:bridge] pick left blank field=${field.fieldId} reason=not_an_enumerated_option`,
      );
      return notMentioned(field);
    }

    const built = supported(
      field,
      opt.value,
      opt.ordinal,
      pick.ordinal,
      noteSha256,
      (input.mappings ?? []).find((m) => m.fieldId === field.fieldId),
    );
    if (!built) return notMentioned(field);
    facts.push(built.fact);
    return built.resolution;
  });

  return { resolutions, facts };
}
