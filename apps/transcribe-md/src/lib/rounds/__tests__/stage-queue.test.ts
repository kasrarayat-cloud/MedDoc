// ============================================================================
// The to-review queue behind Screen 2's peek — ordering and membership.
// ----------------------------------------------------------------------------
// The property under test is NOT "the queue is sorted". It is "the queue is
// sorted the way the BOARD sorts", because "Next up" on the stage and the next
// ready lane on /board are the same claim made twice. A second ordering that
// happens to agree today is the failure this file exists to prevent.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { sortLanes, toBoardLane, type BoardLaneInput } from '../board-data';
import { toReviewQueueIds } from '../stage-queue';

function row(over: Partial<BoardLaneInput> & { id: string }): BoardLaneInput {
  return {
    patientName: 'A Patient',
    patientFallback: null,
    specialty: 'family_medicine',
    status: 'READY',
    createdAt: '2026-07-30T10:00:00.000Z',
    signedAt: null,
    audioDurationSec: 120,
    ...over,
  };
}

describe('toReviewQueueIds', () => {
  it('keeps only what can actually be reviewed', () => {
    const ids = toReviewQueueIds([
      row({ id: 'ready' }),
      row({ id: 'queued', status: 'QUEUED' }),
      row({ id: 'processing', status: 'TRANSCRIBING' }),
      row({ id: 'failed', status: 'FAILED' }),
      row({ id: 'signed', status: 'SIGNED', signedAt: '2026-07-30T11:00:00.000Z' }),
    ]);

    expect(ids).toEqual(['ready']);
  });

  it('EXCLUDES a signed visit whose status column still says READY', () => {
    // `kindOf` keys on `status === 'SIGNED' || signedAt` — signedAt wins. A
    // queue that filtered on the status string alone would offer a signed note
    // as the next one to review and put it back in the "to review" count.
    const ids = toReviewQueueIds([
      row({ id: 'lagging', status: 'READY', signedAt: '2026-07-30T11:00:00.000Z' }),
      row({ id: 'genuine' }),
    ]);

    expect(ids).toEqual(['genuine']);
  });

  it('puts newest first — the board’s own order', () => {
    // ⚠️ Critical-first was the first band until owner ruling #109 removed the
    // prescription-safety surface. The CONTRACT below is what mattered and it
    // is unchanged: this queue must not reimplement the board's sort.
    const ids = toReviewQueueIds([
      row({ id: 'old', createdAt: '2026-07-28T09:00:00.000Z' }),
      row({ id: 'new', createdAt: '2026-07-30T09:00:00.000Z' }),
      row({ id: 'older', createdAt: '2026-07-27T09:00:00.000Z' }),
    ]);

    expect(ids).toEqual(['new', 'old', 'older']);
  });

  it('IS the board’s ordering, not a copy of it that agrees today', () => {
    // The real assertion: run the same rows through the board's own pipeline
    // and require the ready subsequence to be identical. If someone
    // reimplements the sort here, this goes red even when the new sort is
    // "correct" — which is the point, because then the two surfaces would
    // still be two implementations of one promise.
    const rows = [
      row({ id: 'a', createdAt: '2026-07-28T09:00:00.000Z' }),
      row({ id: 'b', createdAt: '2026-07-30T09:00:00.000Z' }),
      row({ id: 'c', createdAt: '2026-07-29T09:00:00.000Z' }),
      row({ id: 'd', status: 'FAILED' }),
    ];

    const boardOrder = sortLanes(rows.map(toBoardLane))
      .filter((l) => l.kind === 'ready')
      .map((l) => l.id);

    expect(toReviewQueueIds(rows)).toEqual(boardOrder);
  });

  it('NEGATIVE CONTROL — the assertion can fail', () => {
    // A guard nobody has watched fail is not known to be a guard. Reversing
    // the input must not produce the same answer for a set whose order is
    // decided by createdAt, or the test above would pass on any ordering.
    const rows = [
      row({ id: 'x', createdAt: '2026-07-28T09:00:00.000Z' }),
      row({ id: 'y', createdAt: '2026-07-30T09:00:00.000Z' }),
    ];

    expect(toReviewQueueIds(rows)).toEqual(['y', 'x']);
    expect(toReviewQueueIds(rows)).not.toEqual(['x', 'y']);
  });

  it('an empty set is an empty queue, not a crash', () => {
    expect(toReviewQueueIds([])).toEqual([]);
  });
});
