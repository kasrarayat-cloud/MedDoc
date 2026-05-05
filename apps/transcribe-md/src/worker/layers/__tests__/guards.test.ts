// ============================================================================
// Round 3 PR-D — empty-transcript guard tests (audit A06-P0-001)
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

// Mock logAudit before importing the guard module — the guard's audit
// emit is fire-and-forget and the side-effect test would require a
// running Postgres. Tests here cover the pure-throw behavior.
vi.mock('@/lib/audit', () => ({
  logAudit: vi.fn(() => Promise.resolve()),
}));

import {
  assertSufficientTranscript,
  countWords,
  isPipelineRejectError,
  PipelineRejectError,
  MIN_AUDIO_DURATION_SEC,
  MIN_TRANSCRIPT_WORD_COUNT,
} from '../../layers/guards';

const visit = {
  visitId: 'visit-test',
  practiceId: 'practice-test',
  userId: 'user-test',
};

describe('countWords', () => {
  it('counts whitespace-separated words', () => {
    expect(countWords('hello world')).toBe(2);
    expect(countWords('one two three four five')).toBe(5);
  });

  it('handles empty + null + undefined', () => {
    expect(countWords('')).toBe(0);
    expect(countWords('   ')).toBe(0);
    expect(countWords(null as unknown as string)).toBe(0);
    expect(countWords(undefined as unknown as string)).toBe(0);
  });

  it('handles multiple whitespace + punctuation correctly', () => {
    expect(countWords('hi,  world.\n\nokay')).toBe(3);
  });
});

describe('assertSufficientTranscript — Guard A (audio duration)', () => {
  it('throws PipelineRejectError on 1-second clip', async () => {
    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: 1,
        transcriptText: 'enough words go here for guard B to not fire alone',
      })
    ).rejects.toMatchObject({
      name: 'PipelineRejectError',
      reasonCode: 'audio_too_short',
    });
  });

  it('throws on 0-second / NaN duration', async () => {
    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: 0,
        transcriptText: 'enough words go here for guard B to not fire alone',
      })
    ).rejects.toMatchObject({ reasonCode: 'audio_too_short' });

    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: NaN,
        transcriptText: 'enough words go here for guard B to not fire alone',
      })
    ).rejects.toMatchObject({ reasonCode: 'audio_too_short' });
  });

  it('does not throw audio_too_short at the threshold', async () => {
    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: MIN_AUDIO_DURATION_SEC, // exactly at threshold = OK
        transcriptText: 'enough words go here for guard B to not fire alone',
      })
    ).resolves.toBeUndefined();
  });
});

describe('assertSufficientTranscript — Guard B (transcript word count)', () => {
  it('throws transcript_too_short on a one-word transcript', async () => {
    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: 30,
        transcriptText: 'cough',
      })
    ).rejects.toMatchObject({
      reasonCode: 'transcript_too_short',
    });
  });

  it('throws on empty transcript even with long audio', async () => {
    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: 60,
        transcriptText: '',
      })
    ).rejects.toMatchObject({ reasonCode: 'transcript_too_short' });
  });

  it('passes at the word-count threshold', async () => {
    const exactly10words = 'a b c d e f g h i j';
    expect(countWords(exactly10words)).toBe(MIN_TRANSCRIPT_WORD_COUNT);
    await expect(
      assertSufficientTranscript({
        ...visit,
        durationSec: 30,
        transcriptText: exactly10words,
      })
    ).resolves.toBeUndefined();
  });
});

describe('PipelineRejectError type guard', () => {
  it('isPipelineRejectError returns true for the custom class', () => {
    const err = new PipelineRejectError('audio_too_short', 'too short');
    expect(isPipelineRejectError(err)).toBe(true);
  });

  it('returns false for a generic Error', () => {
    expect(isPipelineRejectError(new Error('something else'))).toBe(false);
  });

  it('returns false for non-Error values', () => {
    expect(isPipelineRejectError(null)).toBe(false);
    expect(isPipelineRejectError(undefined)).toBe(false);
    expect(isPipelineRejectError('string error')).toBe(false);
  });
});
