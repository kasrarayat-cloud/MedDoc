// ============================================================================
// The five Rounds stages must stay derived from the REAL statuses.
// ----------------------------------------------------------------------------
// A board that shows a stage the pipeline cannot be in is a lie about the
// system, and the failure mode is silent: someone adds a status to the Prisma
// enum, no column claims it, and those visits simply stop appearing on the
// board. Nothing errors. The doctor just never sees them.
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  ROUNDS_STAGES,
  ROUNDS_OUTCOME_STATUSES,
  completedStageCount,
  failureStageOf,
  stageOf,
  unmappedStatuses,
} from '../stages';

describe('every real status is accounted for', () => {
  it('NOTHING is unmapped', () => {
    // The one that matters. If this fails, a status exists that no column and
    // no outcome claims — visits in it would vanish from the board.
    expect(unmappedStatuses(), 'statuses with nowhere to go').toEqual([]);
  });

  it('the strip is exactly five nodes', () => {
    expect(ROUNDS_STAGES).toHaveLength(5);
    expect(ROUNDS_STAGES.map((s) => s.n)).toEqual([1, 2, 3, 4, 5]);
  });

  it('no status is claimed by two stages', () => {
    const all = ROUNDS_STAGES.flatMap((s) => s.statuses);
    expect(new Set(all).size, 'a status in two columns').toBe(all.length);
  });

  it('SIGNED and FAILED are outcomes, not stages', () => {
    // They are drawn as the END of a lane's run — green to the finish, or red
    // stopping where it died — so a column for either would be wrong.
    expect(stageOf('SIGNED')).toBeNull();
    expect(stageOf('FAILED')).toBeNull();
    expect(ROUNDS_OUTCOME_STATUSES).toContain('SIGNED');
    expect(ROUNDS_OUTCOME_STATUSES).toContain('FAILED');
  });
});

describe('a visit lands in the stage a clinician would expect', () => {
  it.each([
    ['QUEUED', 'captured'],
    ['TRANSCRIBING', 'transcribed'],
    ['DRAFTING', 'drafted'],
    ['EXTRACTING', 'drafted'],
    ['POLISHING', 'checked'],
    ['AUTOMATING', 'checked'],
    ['READY', 'ready'],
  ])('%s → %s', (status, stageId) => {
    expect(stageOf(status)?.id).toBe(stageId);
  });

  it('the three internal layers collapse into one visible step', () => {
    // CRITIQUING / POLISHING / AUTOMATING are three pipeline layers and one
    // clinician-facing idea: "the system is going over it". Three columns for
    // three internal layers would be an org chart, not a board.
    const checked = ROUNDS_STAGES.find((s) => s.id === 'checked')!;
    expect(checked.statuses).toEqual(['CRITIQUING', 'POLISHING', 'AUTOMATING']);
  });
});

describe('track progress', () => {
  it('a SIGNED lane is a complete run', () => {
    expect(completedStageCount('SIGNED')).toBe(5);
  });

  it('READY counts as five — the pipeline finished, a human has not', () => {
    expect(completedStageCount('READY')).toBe(5);
  });

  it('a mid-pipeline visit has NOT completed the stage it is in', () => {
    // Drawing the current stage as done is the classic off-by-one, and on this
    // board it would tell a doctor the note is further along than it is.
    expect(completedStageCount('DRAFTING')).toBe(2);
    expect(completedStageCount('QUEUED')).toBe(0);
  });

  it('FAILED has completed nothing by itself — the stage comes from history', () => {
    expect(completedStageCount('FAILED')).toBe(0);
  });
});

describe('a failed lane stops where it died, and does not guess', () => {
  it('stops at the stage it was last known to be in', () => {
    expect(failureStageOf('DRAFTING').id).toBe('drafted');
    expect(failureStageOf('TRANSCRIBING').id).toBe('transcribed');
  });

  it('with NO history it stops at stage 1 rather than inventing progress', () => {
    // Claiming a failure got further than we can show is fiction, and on a
    // board whose whole job is "where do I look", fiction is expensive.
    expect(failureStageOf(null).n).toBe(1);
    expect(failureStageOf(undefined).n).toBe(1);
  });
});
