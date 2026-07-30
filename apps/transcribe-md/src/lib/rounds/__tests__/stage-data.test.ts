// ============================================================================
// Screen 2's view model says what the row says, and stays quiet otherwise.
// ----------------------------------------------------------------------------
// The identity header is the one place on this screen where a fabricated value
// would be indistinguishable from a real one — a plausible MRN or a plausible
// age reads exactly like a true one. So the rules pinned here are all about
// ABSENCE: a missing field yields null and the cell is omitted, never blanked
// and never filled with a default.
// ============================================================================

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  queueLabel,
  toQueuePosition,
  toStageIdentity,
  type StageVisitRow,
} from '../stage-data';

afterEach(() => vi.useRealTimers());

const row = (over: Partial<StageVisitRow> = {}): StageVisitRow => ({
  id: 'v1',
  patientName: 'Aisha Rahman',
  createdAt: '2026-07-30T09:15:00.000Z',
  ...over,
});

describe('identity', () => {
  it('carries the patient label and the encounter facts', () => {
    const id = toStageIdentity(
      row({
        patientExternalId: 'MRN-4471',
        patientDob: '1990-01-01',
        chiefComplaint: 'Chest pain on exertion',
        audioDurationSec: 363,
      })
    );
    expect(id.patientLabel).toBe('Aisha Rahman');
    expect(id.mrn).toBe('MRN-4471');
    expect(id.reason).toBe('Chest pain on exertion');
    expect(id.durationLabel).toBe('6m 03s');
    expect(id.recordedAtIso).toBe('2026-07-30T09:15:00.000Z');
  });

  it('falls back, then to a named placeholder — never to an empty header', () => {
    expect(toStageIdentity(row({ patientName: null })).patientLabel).toBe(
      'Unnamed encounter'
    );
    expect(
      toStageIdentity(row({ patientName: null, patientFallback: 'Room 4' }))
        .patientLabel
    ).toBe('Room 4');
    expect(toStageIdentity(row({ patientName: '   ' })).patientLabel).toBe(
      'Unnamed encounter'
    );
  });

  it('omits MRN, reason and duration rather than blanking them', () => {
    const id = toStageIdentity(row());
    expect(id.mrn).toBeNull();
    expect(id.reason).toBeNull();
    expect(id.durationLabel).toBeNull();
    expect(id.ageYears).toBeNull();
    expect(id.dob).toBeNull();
  });

  it('NEGATIVE CONTROL — the same fields ARE populated when present', () => {
    // Without this, the test above passes against a builder that always
    // returns nulls.
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-07-30T12:00:00Z'));
    const id = toStageIdentity(
      row({
        patientExternalId: 'X1',
        chiefComplaint: 'Cough',
        audioDurationSec: 60,
        patientDob: '2000-01-01',
      })
    );
    expect(id.mrn).toBe('X1');
    expect(id.reason).toBe('Cough');
    expect(id.durationLabel).toBe('1m 00s');
    expect(id.ageYears).toBe(26);
    expect(id.dob).toBe('2000-01-01');
  });

  it('a zero-length recording is not a duration', () => {
    // 0 renders as "0m 00s", which claims a recording that did not happen.
    expect(toStageIdentity(row({ audioDurationSec: 0 })).durationLabel).toBeNull();
    expect(toStageIdentity(row({ audioDurationSec: null })).durationLabel).toBeNull();
  });

  it('trims a DOB to a date — a birth date has no time of day', () => {
    expect(
      toStageIdentity(row({ patientDob: '1990-01-01T00:00:00.000Z' })).dob
    ).toBe('1990-01-01');
    expect(toStageIdentity(row({ patientDob: new Date('1990-01-01') })).dob).toBe(
      '1990-01-01'
    );
  });

  it('accepts a Date createdAt as well as an ISO string', () => {
    expect(
      toStageIdentity(row({ createdAt: new Date('2026-07-30T09:15:00.000Z') }))
        .recordedAtIso
    ).toBe('2026-07-30T09:15:00.000Z');
  });
});

describe('queue position', () => {
  const q = ['a', 'b', 'c'];

  it('is 1-based and names both neighbours', () => {
    const p = toQueuePosition('b', q);
    expect(p.position).toBe(2);
    expect(p.total).toBe(3);
    expect(p.prevVisitId).toBe('a');
    expect(p.nextVisitId).toBe('c');
  });

  it('has no neighbour past either end', () => {
    expect(toQueuePosition('a', q).prevVisitId).toBeNull();
    expect(toQueuePosition('c', q).nextVisitId).toBeNull();
  });

  it('a visit NOT in the queue has no position and no neighbours', () => {
    // A signed note has left the review queue; giving it a place would put it
    // back in the count the day meter reports.
    const p = toQueuePosition('zzz', q);
    expect(p.position).toBeNull();
    expect(p.prevVisitId).toBeNull();
    expect(p.nextVisitId).toBeNull();
    expect(queueLabel(p)).toBeNull();
  });

  it('NEGATIVE CONTROL — a visit that IS in the queue gets a label', () => {
    expect(queueLabel(toQueuePosition('b', q))).toBe('2 of 3 to review');
  });

  it('a single-visit queue reads 1 of 1, with no peek', () => {
    const p = toQueuePosition('only', ['only']);
    expect(queueLabel(p)).toBe('1 of 1 to review');
    expect(p.nextVisitId).toBeNull();
    expect(p.prevVisitId).toBeNull();
  });

  it('an empty queue produces nothing rather than 0 of 0', () => {
    const p = toQueuePosition('a', []);
    expect(p.position).toBeNull();
    expect(queueLabel(p)).toBeNull();
  });
});
