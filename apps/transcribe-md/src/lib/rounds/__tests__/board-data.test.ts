// ============================================================================
// The Board must not invent anything.
// ----------------------------------------------------------------------------
// A board that shows a confident wrong number is worse than one that admits a
// gap, because a clinician will believe it. These pin the honesty rules:
// a missing patient name stays missing, an unknown filter falls back, and NO
// criticals rather than throwing, and a critical card with no readable message
// renders a blank line rather than a composed one.
//
// Plus the two rules that are clinical rather than cosmetic: critical lanes
// sort FIRST, and a failed lane's line stops where it died.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  dayProgress,
  laneMatchesFilter,
  sortLanes,
  toBoardLane,
} from '../board-data';

const base = {
  id: 'v1',
  patientName: 'Aisha Rahman',
  patientFallback: null,
  specialty: 'primary-care',
  status: 'READY',
  createdAt: '2026-07-29T09:00:00.000Z',
  signedAt: null,
  audioDurationSec: 420,
};

const isImaging = (s: string) => s === 'ultrasound';

describe('nothing is invented', () => {
  it('a missing patient name stays missing', () => {
    const l = toBoardLane({ ...base, patientName: null, patientFallback: null });
    // Not a generated identity, not "Patient 1" — a plain admission.
    expect(l.patientLabel).toBe('Unnamed patient');
  });

  it('the stored fallback is used before giving up', () => {
    const l = toBoardLane({ ...base, patientName: null, patientFallback: 'MRN-4471' });
    expect(l.patientLabel).toBe('MRN-4471');
  });

  // ⚠️ Four tests covering `criticalWarningsOf` / `topInteractionLine` were
  // REMOVED here with the prescription-safety surface (owner ruling #109).
  // They proved the board tolerated a malformed `rxDrafts` blob rather than
  // taking the whole board down, and composed no interaction line it could not
  // read off the payload. Both properties belong with the helpers, and both
  // went with them.
});

describe('lane kind and run length', () => {
  it('SIGNED draws the full run', () => {
    const l = toBoardLane({ ...base, status: 'SIGNED', signedAt: '2026-07-29T08:52:00.000Z' });
    expect(l.kind).toBe('signed');
    expect(l.runTo).toBe(5);
  });

  it('a signedAt overrides the status — the timestamp is the truth', () => {
    const l = toBoardLane({ ...base, status: 'READY', signedAt: '2026-07-29T08:52:00.000Z' });
    expect(l.kind).toBe('signed');
  });

  it('FAILED stops at the stage it died in', () => {
    const l = toBoardLane({ ...base, status: 'FAILED', lastKnownStatus: 'DRAFTING' });
    expect(l.kind).toBe('failed');
    expect(l.failedAt?.id).toBe('drafted');
    expect(l.runTo).toBe(3);
  });

  it('FAILED with no history stops at stage 1 rather than guessing', () => {
    const l = toBoardLane({ ...base, status: 'FAILED' });
    expect(l.runTo).toBe(1);
  });

  it('QUEUED reads as recording — that is what the clinician was doing', () => {
    expect(toBoardLane({ ...base, status: 'QUEUED' }).kind).toBe('recording');
  });

  it('mid-pipeline reads as processing', () => {
    expect(toBoardLane({ ...base, status: 'POLISHING' }).kind).toBe('processing');
  });
});

describe('filters', () => {
  const lanes = [
    toBoardLane({ ...base, id: 'ready' }),
    toBoardLane({ ...base, id: 'signed', status: 'SIGNED', signedAt: '2026-07-29T08:00:00.000Z' }),
    toBoardLane({ ...base, id: 'failed', status: 'FAILED' }),
    toBoardLane({ ...base, id: 'us', specialty: 'ultrasound' }),
  ];
  const ids = (f: Parameters<typeof laneMatchesFilter>[1]) =>
    lanes.filter((l) => laneMatchesFilter(l, f, isImaging)).map((l) => l.id).sort();

  it('active excludes signed AND failed', () => {
    expect(ids('active')).toEqual(['ready', 'us']);
  });
  it('signed / failed / ultrasound each select their own', () => {
    expect(ids('signed')).toEqual(['signed']);
    expect(ids('failed')).toEqual(['failed']);
    expect(ids('ultrasound')).toEqual(['us']);
  });
  it('SOAP means "not imaging", so a NEW specialty is included for free', () => {
    // Defining SOAP as a specialty list would silently drop any specialty added
    // later off the board. Defining it as the complement cannot.
    const novel = toBoardLane({ ...base, id: 'new', specialty: 'nephrology' });
    expect(laneMatchesFilter(novel, 'soap', isImaging)).toBe(true);
  });
});

describe('ordering', () => {
  // ⚠️ 'CRITICAL lanes sort first' was REMOVED here — the critical-first band
  // went with the prescription-safety surface (owner ruling #109), so the
  // order is now newest-first with no bands at all.
  it('newest first', () => {
    const lanes = [
      toBoardLane({ ...base, id: 'old', createdAt: '2026-07-29T07:00:00.000Z' }),
      toBoardLane({ ...base, id: 'new', createdAt: '2026-07-29T11:00:00.000Z' }),
    ];
    expect(sortLanes(lanes).map((l) => l.id)).toEqual(['new', 'old']);
  });
});

describe('the day-progress meter is derived, never stored', () => {
  it('counts signed · to review · live', () => {
    const lanes = [
      toBoardLane({ ...base, id: 'a', status: 'SIGNED', signedAt: '2026-07-29T08:00:00.000Z' }),
      toBoardLane({ ...base, id: 'b', status: 'READY' }),
      toBoardLane({ ...base, id: 'c', status: 'READY' }),
      toBoardLane({ ...base, id: 'd', status: 'POLISHING' }),
      toBoardLane({ ...base, id: 'e', status: 'QUEUED' }),
    ];
    expect(dayProgress(lanes)).toEqual({ signed: 1, toReview: 2, live: 2, total: 5 });
  });

  it('a failed lane is in none of the three buckets', () => {
    // It is neither done, nor waiting on the doctor, nor in flight. Counting it
    // anywhere would overstate one of the three numbers on the meter.
    const lanes = [toBoardLane({ ...base, id: 'f', status: 'FAILED' })];
    expect(dayProgress(lanes)).toEqual({ signed: 0, toReview: 0, live: 0, total: 1 });
  });
});
