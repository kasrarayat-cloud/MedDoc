// ============================================================================
// criterion-to-section.ts — Phase 5.2 stub completion
// ----------------------------------------------------------------------------
// Maps a CodingRail EmCriterion id (e.g. `hpi.elements`) to the SOAP
// section + sub-heading where a corresponding addition belongs. Used
// by the bump-additions endpoint to merge doctor edits back into the
// SOAP draft on the right scaffold.
//
// The taxonomy is shared with `to-ui-score.ts:deriveGroups` — every id
// surfaced as a gap by that adapter must round-trip through this map.
//
// Section keys: 'S' / 'O' / 'A' / 'P' (matches parse-soap-sections.ts).
// ============================================================================

export type SoapSectionKey = 'S' | 'O' | 'A' | 'P';

export interface SectionTarget {
  /** Which top-level SOAP section the addition belongs under. */
  section: SoapSectionKey;
  /** Bold sub-heading inside that section (e.g. `**HPI:**`,
   *  `**Family History:**`). Null when the addition is appended to the
   *  section root (Plan items) rather than to a named sub-block. */
  subHeading: string | null;
  /** Doctor-facing label that explains what the addition adds — used in
   *  the audit row's metadata so the row reads "added 1 HPI element". */
  humanLabel: string;
}

/** Engine bump-gaps emit string prefixes; deriveBump assigns the
 *  matching id from this table so BumpModal carries a meaningful
 *  criterionId all the way to the server route. */
const TABLE: Record<string, SectionTarget> = {
  // History group — Subjective section sub-blocks.
  'hpi.elements': {
    section: 'S',
    subHeading: '**HPI:**',
    humanLabel: 'HPI element',
  },
  'ros.systems': {
    section: 'S',
    subHeading: '**ROS:**',
    humanLabel: 'ROS system',
  },
  'pfsh.categories': {
    section: 'S',
    // PFSH is a parent label — the actual addition might be PMH /
    // family / social. The merge logic prepends the sub-heading
    // verbatim so the doctor's text lands as a labeled bullet.
    subHeading: '**Social History:**',
    humanLabel: 'PFSH category',
  },

  // Exam group — Objective section.
  'exam.systems': {
    section: 'O',
    subHeading: null,
    humanLabel: 'exam system',
  },

  // MDM group — Assessment + Plan.
  'mdm.problems': {
    section: 'A',
    subHeading: null,
    humanLabel: 'MDM problem-complexity',
  },
  'mdm.data': {
    section: 'P',
    subHeading: null,
    humanLabel: 'MDM data-review',
  },
  'mdm.risk': {
    section: 'A',
    subHeading: null,
    humanLabel: 'MDM risk',
  },
};

/** Look up the section + sub-heading for a criterion id. Returns null
 *  when the id is unrecognised — the caller should treat unknown ids
 *  as "append to Plan" (least-destructive fallback) and log the
 *  unexpected id for diagnostics. */
export function sectionTargetFor(criterionId: string): SectionTarget | null {
  return TABLE[criterionId] ?? null;
}

/** Engine `bumpGaps` emits free-text strings like "HPI: 3 of 4
 *  elements". Map the prefix to the canonical criterion id so the
 *  BumpModal's gaps each carry a stable id rather than a positional
 *  `gap.0`. */
const PREFIX_TO_ID: Array<{ test: RegExp; id: string }> = [
  { test: /^HPI:/i, id: 'hpi.elements' },
  { test: /^ROS:/i, id: 'ros.systems' },
  { test: /^PFSH:/i, id: 'pfsh.categories' },
  { test: /^Exam:/i, id: 'exam.systems' },
  // MDM gaps don't have a clean 1:1 mapping (any of problems/data/
  // risk could be the lifting element). Default to mdm.problems —
  // the apply-additions endpoint appends to Assessment which is the
  // most common landing zone. The doctor-edited text is what carries
  // the actual content; the criterion id only steers which section
  // the merge targets.
  { test: /^MDM:/i, id: 'mdm.problems' },
];

export function criterionIdForGapLabel(label: string): string {
  for (const { test, id } of PREFIX_TO_ID) {
    if (test.test(label)) return id;
  }
  // Unknown shape — return a sentinel so callers can still attribute
  // the addition without crashing.
  return 'unknown';
}

/** Suggestion text for an "almost-there" gap. Rendered in the
 *  BumpModal's editable textarea — the doctor revises before applying.
 *  Kept short + clinically conservative; the doctor owns the wording. */
const SUGGESTION_BY_ID: Record<string, string> = {
  'hpi.elements':
    'e.g. "Severity 6/10, worsened by exertion, partially relieved by rest."',
  'ros.systems':
    'e.g. "Constitutional: denies fever, fatigue, weight changes."',
  'pfsh.categories':
    'e.g. "Family hx: HTN — mother. Lives with spouse; non-smoker."',
  'exam.systems':
    'e.g. "Cardiovascular: regular rate and rhythm, no murmurs."',
  'mdm.problems':
    'e.g. document the comorbidity that influenced today\'s plan.',
  'mdm.data':
    'e.g. "Reviewed CBC + BMP from 2026-04-12; trended A1c."',
  'mdm.risk':
    'e.g. note prescription-drug management or chronic-illness exacerbation explicitly.',
};

export function suggestionForCriterionId(criterionId: string): string {
  return (
    SUGGESTION_BY_ID[criterionId] ??
    'Add the additional documentation that supports the bump.'
  );
}
