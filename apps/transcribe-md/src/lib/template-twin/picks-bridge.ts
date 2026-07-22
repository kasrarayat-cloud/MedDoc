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

function supported(field: TemplateField, value: string, ordinal: number): FieldResolution {
  return FieldResolutionSchema.parse({
    fieldId: field.fieldId,
    status: 'supported',
    value,
    sourceFactIds: [`ttfact_${'0'.repeat(24)}`],
    evidenceAnchorIds: ['choice-slot-pick'],
    selectedOptionOrdinal: ordinal,
    reasonCode: 'choice_slot_pick',
    clinicianReviewed: false,
  });
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
  /** The {{one of}} marker text the template was compiled/parsed from. */
  markerText: string;
  /** The LIVE brain's generated note (markers filled with picks). */
  filledNote: string;
}

/**
 * Map the note's CHOICE_SLOT picks onto exact-option single-select resolutions.
 * Every field in `ir` gets a resolution (selects filled from picks; everything
 * else not_mentioned). Constrained-fill invariants hold: only listed options,
 * blank when unsaid, never off-list.
 */
export function bridgeChoiceSlotPicks(input: BridgeChoiceSlotPicksInput): FieldResolution[] {
  const { ir, markerText, filledNote } = input;
  const selectFields = ir.fields
    .filter((f) => f.kind === 'single_select' && f.detectionStatus !== 'unsupported' && !f.rowPrototype)
    .sort((a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId));

  const filledLines = filledNote.split('\n');
  const picks: (string | null)[] = [];
  let cursor = 0;
  for (const line of markerText.split('\n')) {
    MARKER_RE.lastIndex = 0;
    if (!MARKER_RE.test(line)) continue;
    MARKER_RE.lastIndex = 0;
    const { picks: linePicks, matchedAt } = alignLineFrom(line, filledLines, cursor);
    picks.push(...linePicks);
    if (matchedAt >= 0) cursor = matchedAt + 1;
  }

  // Nth pick -> Nth single_select field (document order).
  const pickByFieldId = new Map<string, string | null>();
  selectFields.forEach((field, i) => pickByFieldId.set(field.fieldId, picks[i] ?? null));

  return ir.fields.map((field) => {
    if (!pickByFieldId.has(field.fieldId)) return notMentioned(field);
    const pick = pickByFieldId.get(field.fieldId);
    if (pick == null || pick === '') return notMentioned(field);
    const opt = field.allowedOptions.find((o) => norm(o.displayText) === norm(pick) || norm(o.value) === norm(pick));
    return opt ? supported(field, opt.value, opt.ordinal) : notMentioned(field); // never off-list
  });
}
