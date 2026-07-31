// ============================================================================
// ROUNDS — Screen 2's view model.
// ----------------------------------------------------------------------------
// The stage's identity header and its next-up peek, derived from the real visit
// row and the real queue. Pure, so both can be unit-tested without React and
// without a database.
//
// DATA HONESTY, same rule as the board: every field here comes from a column
// that exists. Where one does not, the slot is RESERVED and left empty rather
// than filled with something plausible — see `vitals` below, which the spec
// explicitly parks. A header that invents a value is worse than one with a gap,
// because a gap is visibly a gap.
// ============================================================================

import { ageYearsOf, formatDurationLabel } from '@/lib/patient-display';

export interface StageVisitRow {
  id: string;
  patientName: string | null;
  /** Fallback label when the patient relation has no name (unnamed encounter). */
  patientFallback?: string | null;
  /** `patient.externalId` — what the shipped meta strip already labels MRN. */
  patientExternalId?: string | null;
  patientDob?: string | Date | null;
  chiefComplaint?: string | null;
  /** When the encounter was recorded. */
  createdAt: string | Date;
  audioDurationSec?: number | null;
}

export interface StageIdentity {
  visitId: string;
  patientLabel: string;
  /** null when the patient carries no MRN — the cell is omitted, not blanked. */
  mrn: string | null;
  ageYears: number | null;
  /** ISO date only (no time) — a DOB has no meaningful time component. */
  dob: string | null;
  /** The reason line. null when there is no chief complaint recorded. */
  reason: string | null;
  recordedAtIso: string;
  /** "6m 03s", or null when no audio duration was captured (typed encounters). */
  durationLabel: string | null;
}

export interface StageQueuePosition {
  /** 1-based position of THIS visit among the ones still to review. */
  position: number | null;
  /** How many are still to review, in total. */
  total: number;
  /** The next visit to review after this one, for the peek. */
  nextVisitId: string | null;
  /** The previous one, for the peek's other edge. */
  prevVisitId: string | null;
  /**
   * The HEAD of the to-review queue — the next encounter to open, full stop.
   *
   * Distinct from `nextVisitId`, and Screen 4 needs this one. A signed visit has
   * LEFT the queue (`kindOf` classifies anything with a `signedAt` as signed, and
   * the queue keeps only `ready`), so `toQueuePosition` takes the not-found
   * branch and both neighbours are null — deliberately, because claiming a place
   * in a list it has left would put a signed note back in the review count.
   *
   * So a deck-advance wired to `nextVisitId` renders NOTHING on 100% of signed
   * visits and reads as a wiring bug. The head is what "next in-review" means
   * once this visit is done, and it is the same rule /board uses for its own
   * "open next review".
   *
   * null when nothing is left to review — which must render as an ABSENT
   * control, never as "all done for today": the queue is a 200-row window, and a
   * ready visit outside it produces the same empty result.
   */
  headVisitId: string | null;
}

const UNNAMED = 'Unnamed encounter';

function iso(v: string | Date): string {
  return v instanceof Date ? v.toISOString() : v;
}

/** The identity header's fields. Never throws on a malformed row. */
export function toStageIdentity(row: StageVisitRow): StageIdentity {
  const name = row.patientName?.trim();
  const fallback = row.patientFallback?.trim();

  const dobIso = row.patientDob
    ? iso(row.patientDob).slice(0, 10)
    : null;

  return {
    visitId: row.id,
    patientLabel: name || fallback || UNNAMED,
    mrn: row.patientExternalId?.trim() || null,
    ageYears: ageYearsOf(row.patientDob ?? null),
    dob: dobIso,
    reason: row.chiefComplaint?.trim() || null,
    recordedAtIso: iso(row.createdAt),
    durationLabel:
      typeof row.audioDurationSec === 'number' && row.audioDurationSec > 0
        ? formatDurationLabel(row.audioDurationSec)
        : null,
  };
}

/**
 * Where this visit sits in the to-review queue.
 *
 * `queue` is the ordered list of visit ids still to review — the caller builds
 * it from the SAME `sortLanes`/`laneMatchesFilter` the board uses, so the peek
 * and the board cannot disagree about what "next" means.
 *
 * A visit that is NOT in the queue (already signed, say) gets
 * `position: null` and no neighbours: it has no place in a list it has left,
 * and claiming one would put a signed note back in the review count.
 */
export function toQueuePosition(
  visitId: string,
  queue: readonly string[]
): StageQueuePosition {
  const i = queue.indexOf(visitId);
  const headVisitId = queue[0] ?? null;
  if (i === -1) {
    return {
      position: null,
      total: queue.length,
      nextVisitId: null,
      prevVisitId: null,
      headVisitId,
    };
  }
  return {
    position: i + 1,
    total: queue.length,
    nextVisitId: queue[i + 1] ?? null,
    prevVisitId: queue[i - 1] ?? null,
    headVisitId,
  };
}

/** "3 of 7 to review", or null when this visit is not in the queue. */
export function queueLabel(pos: StageQueuePosition): string | null {
  if (pos.position === null) return null;
  return `${pos.position} of ${pos.total} to review`;
}
