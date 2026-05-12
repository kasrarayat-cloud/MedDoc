// ============================================================================
// E&M Coding — bump-CTA logic (Phase 5.2, rubric §5)
// ----------------------------------------------------------------------------
// Decides whether the right-rail should surface a "Bump to 99214 · +$32"
// CTA. The rule (rubric §5):
//   * already-at-top-tier  → null
//   * gap === 0            → mode='confirm-bump' (already meets next level)
//   * gap ≤ 2 criteria     → mode='almost-there' with the gap list
//   * gap > 2              → null (gap too large; don't surface)
// ============================================================================

import {
  ESTABLISHED_LADDER,
  LEVEL_RANK,
  NEW_LADDER,
  REVENUE_DELTA,
} from './rubric';
import type { BumpSuggestion, ElementLevel, EmCode, EmScore, MdmTier } from './types';

/** What it takes to reach a given target code. We express this in
 *  terms of the four deterministic counts + the three MDM elements
 *  so we can diff against `EmScore.satisfied`. */
interface CodeRequirements {
  hpiElements: number;
  rosSystems: number;
  pfshCategories: number;
  examSystems: number;
  /** Minimum-MDM-tier (resolved 2-of-3) for this code. */
  mdmTier: MdmTier;
  /** Highest individual-level any element must reach (effectively 2-of-3
   *  threshold). */
  elementLevelFloor: ElementLevel;
}

/** The MDM tier (and its single-element floor) required for each code.
 *  Counts are illustrative (per rubric §3 thresholds: 4+ HPI for 99214+,
 *  10+ ROS for "complete"). The diff is keyed on whether the SOAP
 *  satisfies the count threshold for that level. */
function requirementsFor(code: EmCode): CodeRequirements {
  switch (code) {
    case '99202':
    case '99212':
      return { hpiElements: 1, rosSystems: 1, pfshCategories: 0, examSystems: 1, mdmTier: 'straightforward', elementLevelFloor: 'minimal' };
    case '99203':
    case '99213':
      return { hpiElements: 4, rosSystems: 2, pfshCategories: 1, examSystems: 2, mdmTier: 'low', elementLevelFloor: 'low' };
    case '99204':
    case '99214':
      return { hpiElements: 4, rosSystems: 2, pfshCategories: 2, examSystems: 5, mdmTier: 'moderate', elementLevelFloor: 'moderate' };
    case '99205':
    case '99215':
      return { hpiElements: 4, rosSystems: 10, pfshCategories: 3, examSystems: 8, mdmTier: 'high', elementLevelFloor: 'high' };
    case '99211':
      return { hpiElements: 0, rosSystems: 0, pfshCategories: 0, examSystems: 0, mdmTier: 'straightforward', elementLevelFloor: 'minimal' };
  }
}

/** "Next level up" lookup for a given code. Returns null when already
 *  at the top of the visit-type ladder. */
function nextLevelUp(code: EmCode): EmCode | null {
  const ladder = ESTABLISHED_LADDER.includes(code)
    ? ESTABLISHED_LADDER
    : NEW_LADDER.includes(code)
      ? NEW_LADDER
      : null;
  if (!ladder) return null;
  const idx = ladder.indexOf(code);
  if (idx < 0 || idx >= ladder.length - 1) return null;
  return ladder[idx + 1];
}

/** Diff the satisfied criteria against the next-level requirements,
 *  emitting a flat list of human-readable gap strings. */
function diffRequirements(
  satisfied: EmScore['satisfied'],
  required: CodeRequirements,
): string[] {
  const gaps: string[] = [];
  if (satisfied.hpiElements < required.hpiElements) {
    gaps.push(`HPI: ${satisfied.hpiElements} of ${required.hpiElements} elements`);
  }
  if (satisfied.rosSystems < required.rosSystems) {
    gaps.push(`ROS: ${satisfied.rosSystems} of ${required.rosSystems} systems`);
  }
  if (satisfied.pfshCategories < required.pfshCategories) {
    gaps.push(`PFSH: ${satisfied.pfshCategories} of ${required.pfshCategories} categories`);
  }
  if (satisfied.examSystems < required.examSystems) {
    gaps.push(`Exam: ${satisfied.examSystems} of ${required.examSystems} systems`);
  }
  // MDM gap — at least 2 of 3 elements must reach the floor for the
  // resolved tier to land at that level.
  const required_rank = LEVEL_RANK[required.elementLevelFloor];
  const elementLevels: ElementLevel[] = [
    satisfied.problems,
    satisfied.data,
    satisfied.risk,
  ];
  const meeting = elementLevels.filter((l) => LEVEL_RANK[l] >= required_rank).length;
  if (meeting < 2) {
    const need = 2 - meeting;
    gaps.push(`MDM: ${need} more element(s) at ${required.elementLevelFloor}+`);
  }
  return gaps;
}

/** Look up the static revenue delta for a code pair (rubric §5
 *  reference table). Returns 0 if the pair isn't in the table. */
function revenueDelta(from: EmCode, to: EmCode): number {
  return REVENUE_DELTA[`${from}->${to}`] ?? 0;
}

/** Maximum number of gaps to surface as an "almost-there" bump CTA.
 *
 *  Pre-2026-05-12 this was 2. That choked the bump CTA on text_notes
 *  visits whose SOAPs are shorter than transcribed audio: the
 *  deterministic counters land lower (e.g. 3 ROS systems vs 6-10 in a
 *  transcribed visit), so a 99214 visit looking at 99215 routinely
 *  produced 3 gaps (ROS + Exam + MDM) and the CTA never surfaced —
 *  zero EM_BUMP_APPLIED rows across 9 text_notes + 4 voice_dictation
 *  visits in the 30-day window pre-fix, vs 12 / 35 for audio_upload.
 *
 *  Raised to 4 so doctors see the gap list and can act on it via the
 *  BumpModal even when 3-4 dimensions need work. >4 still hides —
 *  that's the "you'd need to rewrite the note from scratch" case
 *  where the CTA noise exceeds the value. */
const ALMOST_THERE_GAP_THRESHOLD = 4;

/** Produce a BumpSuggestion or null per rubric §5. */
export function shouldShowBumpCta(
  current: EmCode,
  score: EmScore,
): BumpSuggestion | null {
  const next = nextLevelUp(current);
  if (!next) return null; // already at top — no bump CTA

  const required = requirementsFor(next);
  const gaps = diffRequirements(score.satisfied, required);

  if (gaps.length === 0) {
    return {
      mode: 'confirm-bump',
      toCode: next,
      gaps: [],
      revenueDelta: revenueDelta(current, next),
    };
  }
  if (gaps.length <= ALMOST_THERE_GAP_THRESHOLD) {
    return {
      mode: 'almost-there',
      toCode: next,
      gaps,
      revenueDelta: revenueDelta(current, next),
    };
  }
  return null; // gap too large — don't surface
}

/** Internal export so score.ts can compute the bumpableTo / bumpGaps
 *  fields without re-implementing the diff. */
export const _internal = {
  nextLevelUp,
  requirementsFor,
  diffRequirements,
  revenueDelta,
};
