// ============================================================================
// Layer 1 low-confidence integration test (Round 3 quality fix-pack Q0-5)
// ----------------------------------------------------------------------------
// Asserts that runLayer1Transcribe:
//   - Aggregates Deepgram per-utterance confidence into audioConfidenceStats
//     and persists it on the visit row.
//   - Flips needsReview + sets reviewReason when the aggregate triggers
//     shouldFlagForReview (median below 0.55 OR low-confidence pct > 30%).
//   - Leaves needsReview unchanged when the audio is clean.
//
// Closes audit Findings 02.5 (heavy accent / mumbling produces overconfident
// SOAPs) + 07.3 (Deepgram per-utterance confidence captured but not
// propagated). The deepgramBatchTranscribe call is stubbed to return a
// shaped fixture; the helper + the L1 plumbing are exercised end-to-end.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DeepgramBatchResult } from '@meddoc/ai';

// Captured Prisma update calls — the test inspects the data argument to
// verify the new column + reviewReason.
type Captured = { where: unknown; data: Record<string, unknown> };
const updateCalls: Captured[] = [];

vi.mock('@meddoc/db', () => ({
  default: {
    transcribeVisit: {
      update: vi.fn(async (args: Captured) => {
        updateCalls.push(args);
        return {};
      }),
    },
  },
}));

// Per-test fixture for what the Deepgram client returns. Each test sets
// it via `setNextDeepgramResult(...)` before invoking the layer.
let nextDeepgramResult: DeepgramBatchResult | null = null;
function setNextDeepgramResult(r: DeepgramBatchResult): void {
  nextDeepgramResult = r;
}

vi.mock('@meddoc/ai', async () => {
  const actual =
    await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    deepgramBatchTranscribe: vi.fn(async () => {
      if (!nextDeepgramResult) {
        throw new Error('test forgot to setNextDeepgramResult');
      }
      return nextDeepgramResult;
    }),
  };
});

// MinIO is contacted before the Deepgram call to size + stream the audio.
// The streaming path is tested upstream; here we only need stat + stream
// to resolve without throwing.
vi.mock('@/lib/minio', () => ({
  statAudio: vi.fn(async () => ({ size: 1024 })),
  streamAudio: vi.fn(async () => {
    const { Readable } = await import('node:stream');
    return Readable.from([Buffer.from('test-audio-bytes')]);
  }),
}));

// Avoid pulling the full vocabulary list into the test process.
// Q2 fix-pack — L1 now consumes CLINICAL_KEYTERMS (medications +
// anatomy + labs + procedures + diagnoses). Mock both names with
// empty arrays since the test cares about confidence-stat plumbing,
// not keyterm payload content.
vi.mock('@/lib/deepgram-vocabulary', () => ({
  CLINICAL_KEYTERMS: [],
  MEDICATION_KEYTERMS: [],
}));

import { runLayer1Transcribe } from '../01-transcribe';

const baseInput = {
  visitId: 'visit-low-conf-test',
  practiceId: 'practice-test',
  userId: 'user-test',
  audioKey: 'audio/test.webm',
  audioMimeType: 'audio/webm',
};

function makeUtterance(confidence: number, idx: number) {
  return {
    start: idx * 2,
    end: idx * 2 + 2,
    confidence,
    channel: 0,
    transcript: `utterance ${idx}`,
    words: [],
    speaker: idx % 2,
  };
}

function makeResult(confidences: number[]): DeepgramBatchResult {
  const utterances = confidences.map((c, i) => makeUtterance(c, i));
  return {
    raw: { results: { utterances } } as unknown as DeepgramBatchResult['raw'],
    transcript: utterances.map((u) => u.transcript).join(' '),
    utterances,
    durationSec: utterances.length * 2,
  };
}

beforeEach(() => {
  updateCalls.length = 0;
  nextDeepgramResult = null;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('runLayer1Transcribe — audio confidence wiring', () => {
  it('persists audioConfidenceStats and flips needsReview on low-confidence audio', async () => {
    setNextDeepgramResult(
      makeResult([0.42, 0.38, 0.5, 0.3, 0.45, 0.48, 0.4, 0.35, 0.55, 0.4])
    );

    await runLayer1Transcribe(baseInput);

    expect(updateCalls).toHaveLength(1);
    const data = updateCalls[0].data;

    // The aggregate stats made it onto the row.
    const stats = data.audioConfidenceStats as
      | { median: number; lowConfPct: number; totalUtterances: number; threshold: number }
      | null;
    expect(stats).not.toBeNull();
    expect(stats!.totalUtterances).toBe(10);
    expect(stats!.median).toBeLessThan(0.55);
    expect(stats!.threshold).toBe(0.6);

    // The low-confidence guard fired.
    expect(data.needsReview).toBe(true);
    expect(typeof data.reviewReason).toBe('string');
    expect(data.reviewReason as string).toContain('Audio confidence is below threshold');
    expect(data.reviewReason as string).toContain('median');
    // Threshold the message reports must match LOW_CONFIDENCE_THRESHOLD.
    expect(data.reviewReason as string).toContain('0.6');
  });

  it('persists audioConfidenceStats but does NOT flip needsReview on clean audio', async () => {
    setNextDeepgramResult(makeResult(Array(10).fill(0.95)));

    await runLayer1Transcribe(baseInput);

    expect(updateCalls).toHaveLength(1);
    const data = updateCalls[0].data;

    const stats = data.audioConfidenceStats as
      | { median: number; lowConfPct: number }
      | null;
    expect(stats).not.toBeNull();
    expect(stats!.median).toBeCloseTo(0.95, 6);
    expect(stats!.lowConfPct).toBe(0);

    // Clean audio → no needsReview / reviewReason in the data shape.
    expect(data.needsReview).toBeUndefined();
    expect(data.reviewReason).toBeUndefined();
  });

  it('persists audioConfidenceStats=null when Deepgram returned no utterances', async () => {
    setNextDeepgramResult({
      raw: {} as unknown as DeepgramBatchResult['raw'],
      transcript: '',
      utterances: [],
      durationSec: 0,
    });

    await runLayer1Transcribe(baseInput);

    expect(updateCalls).toHaveLength(1);
    const data = updateCalls[0].data;

    expect(data.audioConfidenceStats).toBeNull();
    expect(data.needsReview).toBeUndefined();
  });

  it('flips needsReview via the lowConfPct branch (clean median, rough patches)', async () => {
    // 10 utterances: 6 clean, 4 rough — 40% > 30% threshold; median high.
    setNextDeepgramResult(
      makeResult([0.95, 0.95, 0.92, 0.9, 0.88, 0.86, 0.45, 0.42, 0.38, 0.35])
    );

    await runLayer1Transcribe(baseInput);

    const data = updateCalls[0].data;
    const stats = data.audioConfidenceStats as {
      median: number;
      lowConfPct: number;
    };
    expect(stats.lowConfPct).toBeGreaterThan(30);
    expect(data.needsReview).toBe(true);
    expect(data.reviewReason as string).toContain('40%');
  });
});
