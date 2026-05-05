// ============================================================================
// audio-confidence helper tests (Round 3 quality fix-pack Q0-5)
// ----------------------------------------------------------------------------
// Pure-function tests — no Prisma, no Deepgram, no Anthropic. The helper is
// the reference oracle for what L1 persists into transcribe_visits and what
// L4/L5 read to decide whether to expand their prompts.
// ============================================================================

import { describe, expect, it } from 'vitest';
import {
  computeAudioConfidenceStats,
  shouldFlagForReview,
  LOW_CONFIDENCE_THRESHOLD,
  NEEDS_REVIEW_MEDIAN,
  NEEDS_REVIEW_LOW_CONF_PCT,
} from '../audio-confidence';

describe('computeAudioConfidenceStats', () => {
  it('returns null for empty input', () => {
    expect(computeAudioConfidenceStats([])).toBeNull();
  });

  it('returns null when no utterance has a numeric confidence', () => {
    expect(
      computeAudioConfidenceStats([{}, { confidence: null }, { confidence: undefined }])
    ).toBeNull();
  });

  it('skips utterances without a confidence value but uses the rest', () => {
    const stats = computeAudioConfidenceStats([
      { confidence: 0.9 },
      { confidence: undefined },
      {},
      { confidence: null },
      { confidence: 0.8 },
    ]);
    expect(stats).not.toBeNull();
    expect(stats!.totalUtterances).toBe(2);
    expect(stats!.mean).toBeCloseTo(0.85, 6);
  });

  it('reports clean audio when all utterances are high-confidence', () => {
    const utt = Array.from({ length: 20 }, () => ({ confidence: 0.95 }));
    const stats = computeAudioConfidenceStats(utt)!;
    expect(stats.mean).toBeCloseTo(0.95, 6);
    expect(stats.median).toBeCloseTo(0.95, 6);
    expect(stats.p10).toBeCloseTo(0.95, 6);
    expect(stats.lowConfCount).toBe(0);
    expect(stats.lowConfPct).toBe(0);
    expect(stats.totalUtterances).toBe(20);
    expect(stats.threshold).toBe(LOW_CONFIDENCE_THRESHOLD);
    expect(shouldFlagForReview(stats)).toBe(false);
  });

  it('flags mostly-low audio for review (low median path)', () => {
    // 10 utterances, all low — median is well below 0.55.
    const utt = [0.42, 0.38, 0.5, 0.3, 0.45, 0.48, 0.4, 0.35, 0.55, 0.4].map(
      (confidence) => ({ confidence })
    );
    const stats = computeAudioConfidenceStats(utt)!;
    expect(stats.median).toBeLessThan(NEEDS_REVIEW_MEDIAN);
    expect(stats.lowConfCount).toBe(10);
    expect(stats.lowConfPct).toBe(100);
    expect(shouldFlagForReview(stats)).toBe(true);
  });

  it('flags a mostly-clean visit with rough patches via the lowConfPct path', () => {
    // 10 utterances, 4 rough (40% — exceeds the 30% threshold) but the
    // median is still high (0.9). Triggers via the lowConfPct branch.
    const utt = [
      0.95, 0.95, 0.92, 0.9, 0.88, 0.86,
      0.45, 0.42, 0.38, 0.35,
    ].map((confidence) => ({ confidence }));
    const stats = computeAudioConfidenceStats(utt)!;
    expect(stats.median).toBeGreaterThan(NEEDS_REVIEW_MEDIAN);
    expect(stats.lowConfPct).toBeGreaterThan(NEEDS_REVIEW_LOW_CONF_PCT);
    expect(stats.lowConfCount).toBe(4);
    expect(shouldFlagForReview(stats)).toBe(true);
  });

  it('does NOT flag a clean visit with one rough utterance under the pct threshold', () => {
    // 10 utterances, 1 rough — 10% < 30%. Median high. No flag.
    const utt = [
      0.95, 0.93, 0.92, 0.9, 0.89, 0.88, 0.87, 0.86, 0.85,
      0.4,
    ].map((confidence) => ({ confidence }));
    const stats = computeAudioConfidenceStats(utt)!;
    expect(stats.lowConfPct).toBe(10);
    expect(stats.median).toBeGreaterThan(NEEDS_REVIEW_MEDIAN);
    expect(shouldFlagForReview(stats)).toBe(false);
  });

  it('computes the median correctly on odd counts (middle value)', () => {
    const stats = computeAudioConfidenceStats([
      { confidence: 0.1 },
      { confidence: 0.5 },
      { confidence: 0.9 },
    ])!;
    expect(stats.median).toBeCloseTo(0.5, 6);
  });

  it('computes the median correctly on even counts (avg of two middles)', () => {
    const stats = computeAudioConfidenceStats([
      { confidence: 0.2 },
      { confidence: 0.4 },
      { confidence: 0.6 },
      { confidence: 0.8 },
    ])!;
    expect(stats.median).toBeCloseTo(0.5, 6); // (0.4 + 0.6) / 2
  });

  it('p10 surfaces the bottom-decile utterance via interpolation', () => {
    // 11 confidences from 0.0..1.0 in 0.1 steps. p10 of an 11-point
    // distribution lands at rank = 0.1 * 10 = 1.0 → the 0.1 value.
    const utt = Array.from({ length: 11 }, (_, i) => ({
      confidence: i / 10,
    }));
    const stats = computeAudioConfidenceStats(utt)!;
    expect(stats.p10).toBeCloseTo(0.1, 6);
  });

  it('survives a single-utterance input (median = mean = p10 = that one value)', () => {
    const stats = computeAudioConfidenceStats([{ confidence: 0.73 }])!;
    expect(stats.totalUtterances).toBe(1);
    expect(stats.mean).toBeCloseTo(0.73, 6);
    expect(stats.median).toBeCloseTo(0.73, 6);
    expect(stats.p10).toBeCloseTo(0.73, 6);
  });

  it('treats Infinity / NaN as missing values', () => {
    const stats = computeAudioConfidenceStats([
      { confidence: Number.NaN },
      { confidence: Number.POSITIVE_INFINITY },
      { confidence: 0.8 },
      { confidence: 0.9 },
    ])!;
    expect(stats.totalUtterances).toBe(2);
    expect(stats.mean).toBeCloseTo(0.85, 6);
  });
});

describe('shouldFlagForReview', () => {
  it('fires when median is below threshold even if pct is fine', () => {
    expect(
      shouldFlagForReview({
        mean: 0.5,
        median: 0.5, // < 0.55
        p10: 0.4,
        lowConfPct: 0,
        lowConfCount: 0,
        totalUtterances: 10,
        threshold: 0.6,
      })
    ).toBe(true);
  });

  it('fires when pct is above threshold even if median is fine', () => {
    expect(
      shouldFlagForReview({
        mean: 0.7,
        median: 0.8,
        p10: 0.3,
        lowConfPct: 35, // > 30
        lowConfCount: 4,
        totalUtterances: 11,
        threshold: 0.6,
      })
    ).toBe(true);
  });

  it('does NOT fire when both axes are fine', () => {
    expect(
      shouldFlagForReview({
        mean: 0.9,
        median: 0.9,
        p10: 0.7,
        lowConfPct: 5,
        lowConfCount: 1,
        totalUtterances: 20,
        threshold: 0.6,
      })
    ).toBe(false);
  });
});
