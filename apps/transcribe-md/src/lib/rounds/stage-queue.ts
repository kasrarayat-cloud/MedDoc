// ============================================================================
// ROUNDS — the to-review queue behind Screen 2's peek and "N of M to review".
// ----------------------------------------------------------------------------
// THE PEEK AND THE BOARD MUST NOT BE ABLE TO DISAGREE. "Next up" on the stage
// and the next ready lane on the board are the same claim about the same list,
// so this does not re-implement an ordering — it maps rows through the board's
// own `toBoardLane` and `sortLanes` and takes the ids. Two orderings would
// eventually diverge, and the doctor would be told two different things about
// which patient is next.
//
// "TO REVIEW" IS `kind === 'ready'`, AND ONLY THAT. It is what the board's own
// day meter counts (`dayProgress.toReview`) and what its "next review" button
// targets. It is deliberately NOT `laneMatchesFilter(l, 'active', …)`, which is
// broader — `active` includes QUEUED and processing lanes, which cannot be
// reviewed at all. `queueLabel` renders the words "to review", so counting a
// lane that is still transcribing would make the sentence false.
//
// THE STATUS FILTER IS NOT IN THE WHERE CLAUSE, on purpose. `kindOf` is the one
// definition of what is reviewable; narrowing in SQL would create a second one,
// in a different language, that nothing keeps in step.
//
// Split into a pure half and a thin database half so the ordering can be
// unit-tested without a database.
// ============================================================================

import prisma from '@meddoc/db';

import { sortLanes, toBoardLane, type BoardLaneInput } from './board-data';

/**
 * How many of the doctor's most recent visits the queue window covers.
 *
 * The board pages at 20; that is a UI page size and inheriting it would make
 * "next up" empty for the 21st visit. This is a different quantity — how far
 * back the queue looks — and it is bounded because an unbounded read of a PHI
 * table on every visit render is not a thing to leave open.
 *
 * A READY visit outside the window gets `position: null` from
 * `toQueuePosition`, which renders the label and BOTH peeks as absent rather
 * than wrong. Degrading to silence is honest; degrading to "1 of 200" is not.
 */
export const STAGE_QUEUE_MAX = 200;

/** The ordered ids of the visits still to review. Pure — no I/O. */
export function toReviewQueueIds(rows: readonly BoardLaneInput[]): string[] {
  return sortLanes(rows.map(toBoardLane))
    .filter((lane) => lane.kind === 'ready')
    .map((lane) => lane.id);
}

/**
 * The same read the board does, minus its search predicate and its paging.
 *
 * `createdAt`/`signedAt` are handed over as ISO strings because
 * `BoardLaneInput.createdAt` is typed `string` and `sortLanes` compares them
 * with `localeCompare` — passing a `Date` through would sort by whatever
 * `localeCompare` does to a coerced object rather than throwing.
 */
export async function fetchStageQueueIds(userId: string): Promise<string[]> {
  const rows = await prisma.transcribeVisit.findMany({
    // Identical scope to the board's, so neither can show a visit the other
    // hides. The search predicate is absent because the queue is not a search.
    where: { userId, deletedAt: null, archivedAt: null },
    orderBy: [{ createdAt: 'desc' }, { id: 'desc' }],
    take: STAGE_QUEUE_MAX,
    select: {
      id: true,
      patientName: true,
      specialty: true,
      status: true,
      createdAt: true,
      signedAt: true,
      audioDurationSec: true,
      // Required, not incidental: `sortLanes` puts critical lanes first, and
      // `criticalCount` is derived from this column. Omitting it would order
      // the queue differently from the board while looking correct.
      rxDrafts: true,
      patient: { select: { name: true } },
    },
  });

  // Named explicitly for the same reason board/page.tsx names its row shape:
  // the generated client's select-narrowed type does not survive across the
  // workspace boundary here, and an implicit `any` would let a renamed column
  // through silently.
  type QueueRow = {
    id: string;
    patientName: string | null;
    specialty: string;
    status: string;
    createdAt: Date;
    signedAt: Date | null;
    audioDurationSec: number | null;
    rxDrafts: unknown;
    patient: { name: string } | null;
  };

  return toReviewQueueIds(
    (rows as QueueRow[]).map((v) => ({
      id: v.id,
      patientName: v.patient?.name ?? null,
      patientFallback: v.patientName ?? null,
      specialty: v.specialty,
      status: v.status,
      createdAt: v.createdAt.toISOString(),
      signedAt: v.signedAt?.toISOString() ?? null,
      audioDurationSec: v.audioDurationSec,
      rxDrafts: v.rxDrafts,
    }))
  );
}
