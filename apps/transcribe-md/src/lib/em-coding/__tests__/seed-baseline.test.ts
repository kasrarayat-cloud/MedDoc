// ============================================================================
// The baseline seed, exercised — not grepped.
// ----------------------------------------------------------------------------
// The tests this replaces asserted `toContain('priorSoap')`, which is satisfied
// by the interface field name alone: they would have passed verbatim if every
// caller had handed over the POST-mutation note, i.e. the one property that
// matters was untested. All three BLOCKs in the review were green under them.
//
// So these drive the function with a stubbed prisma and a stubbed scorer, and
// assert on what it WRITES.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const updateMany = vi.fn();
const computeDisplayedEmCode = vi.fn();

vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { updateMany: (...a: unknown[]) => updateMany(...a) } },
}));
vi.mock('@/lib/em-coding/displayed-level', () => ({
  computeDisplayedEmCode: (...a: unknown[]) => computeDisplayedEmCode(...a),
}));
vi.mock('@prisma/client', () => ({ TranscribeVisitStatus: { READY: 'READY' } }));

const BASE = {
  visitId: 'v1',
  priorSoap: '## Subjective\nPrior note.',
  currentScoredCode: null,
  signals: { icdCodes: [], rxDrafts: [], cptCodes: { em: {} } },
  ctx: { practiceId: 'p1', userId: 'u1' },
  applies: true,
};

beforeEach(() => {
  updateMany.mockReset().mockResolvedValue({ count: 1 });
  computeDisplayedEmCode.mockReset().mockResolvedValue('99213');
});
afterEach(() => vi.resetModules());

type Over = Partial<Omit<typeof BASE, 'currentScoredCode'>> & {
  currentScoredCode?: string | null;
  knownPriorCode?: string | null;
};

async function seed(over: Over = {}) {
  const { seedEmBaselineIfUnset } = await import('../seed-baseline');
  await seedEmBaselineIfUnset({ ...BASE, ...over });
}

describe('what it writes', () => {
  it('records the level of the PRE-MUTATION note', async () => {
    await seed();
    // The note it scored is the one it was given — not a later one.
    expect(computeDisplayedEmCode).toHaveBeenCalledWith(
      BASE.priorSoap,
      BASE.signals,
      expect.objectContaining({ visitId: 'v1' }),
    );
    expect(updateMany).toHaveBeenCalledTimes(1);
    expect(updateMany.mock.calls[0][0].data).toEqual({ emScoredCode: '99213' });
  });

  it('is idempotent and never overwrites: the WHERE demands a null baseline', async () => {
    await seed();
    expect(updateMany.mock.calls[0][0].where).toMatchObject({
      id: 'v1',
      emScoredCode: null,
    });
  });

  it('never stamps a row that is not READY', async () => {
    await seed();
    expect(updateMany.mock.calls[0][0].where).toMatchObject({ status: 'READY' });
  });

  it('does nothing when a baseline already exists', async () => {
    await seed({ currentScoredCode: '99214' });
    expect(computeDisplayedEmCode).not.toHaveBeenCalled();
    expect(updateMany).not.toHaveBeenCalled();
  });

  it('does nothing where there is no E/M to baseline', async () => {
    await seed({ applies: false });
    expect(updateMany).not.toHaveBeenCalled();
  });
});

describe('it refuses to write a non-code', () => {
  it("a caller's sentinel is not a CPT code — and must not be persisted", async () => {
    // computeEmLevelDelta returns { from: 'unknown' } when scoring fails.
    // Seeding that made every later re-score report a movement FROM 'unknown'
    // that never happened: a fabricated confirm and a fabricated audit row.
    await seed({ knownPriorCode: 'unknown' });
    expect(
      updateMany.mock.calls.map((c) => c[0].data.emScoredCode),
      "'unknown' must never reach emScoredCode",
    ).not.toContain('unknown');
  });

  it('a scoring failure leaves the baseline unset rather than wrong', async () => {
    computeDisplayedEmCode.mockRejectedValue(new Error('anthropic down'));
    await seed();
    expect(updateMany).not.toHaveBeenCalled();
  });

  it('an empty score is not written', async () => {
    computeDisplayedEmCode.mockResolvedValue('');
    await seed();
    expect(updateMany).not.toHaveBeenCalled();
  });
});

describe('a known prior code costs no scoring call', () => {
  it('uses it directly', async () => {
    await seed({ knownPriorCode: '99215' });
    expect(computeDisplayedEmCode).not.toHaveBeenCalled();
    expect(updateMany.mock.calls[0][0].data.emScoredCode).toBe('99215');
  });
});
