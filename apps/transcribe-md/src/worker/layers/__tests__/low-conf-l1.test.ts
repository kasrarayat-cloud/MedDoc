// ============================================================================
// Layer 1 low-confidence + fallback integration test
// ----------------------------------------------------------------------------
// Asserts that runLayer1Transcribe:
//   - Aggregates Deepgram per-utterance confidence into audioConfidenceStats
//     and persists it on the visit row.
//   - Flips needsReview + sets reviewReason when the aggregate triggers
//     shouldFlagForReview (median below 0.55 OR low-confidence pct > 30%).
//   - Leaves needsReview unchanged when the audio is clean.
//   - PR-L follow-up: persists `transcriptionProvider` on every visit and
//     emits a TRANSCRIPTION_PROVIDER_FALLBACK audit row when the
//     orchestrator fell back to Whisper.
//
// Closes audit Findings 02.5 (heavy accent / mumbling produces overconfident
// SOAPs) + 07.3 (Deepgram per-utterance confidence captured but not
// propagated). The transcribe() orchestrator is stubbed to return a shaped
// fixture; the helper + the L1 plumbing are exercised end-to-end.
// ============================================================================

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type {
  DeepgramBatchResult,
  TranscribeResult,
  WhisperBatchResult,
} from '@meddoc/ai';
// Real class (the @meddoc/ai mock below spreads ...actual, so this is the
// same reference L1 checks via instanceof).
import { CrossProviderFallbackDisabledError } from '@meddoc/ai';

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

// PR-L follow-up: capture every logAudit call so the fallback audit-row
// test can assert action + metadata. The real audit module pulls in
// next/headers + nextauth + redis — we stub it down to a spy that
// only records inputs.
type AuditCall = {
  action: string;
  targetId?: string | null;
  targetType?: string | null;
  userId?: string | null;
  practiceId?: string | null;
  metadata?: Record<string, unknown>;
  success?: boolean;
  errorCode?: string | null;
};
const auditCalls: AuditCall[] = [];

vi.mock('@/lib/audit', () => ({
  logAudit: vi.fn(async (input: AuditCall) => {
    auditCalls.push(input);
  }),
}));

// Per-test fixture for what the orchestrator returns. Each test sets
// it via `setNextTranscribeResult(...)` (resolve) or
// `setNextTranscribeError(...)` (reject) before invoking the layer.
let nextTranscribeResult: TranscribeResult | null = null;
let nextTranscribeError: unknown = null;
function setNextTranscribeResult(r: TranscribeResult): void {
  nextTranscribeResult = r;
  nextTranscribeError = null;
}
function setNextTranscribeError(e: unknown): void {
  nextTranscribeError = e;
  nextTranscribeResult = null;
}

vi.mock('@meddoc/ai', async () => {
  const actual =
    await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    transcribe: vi.fn(async () => {
      if (nextTranscribeError) {
        throw nextTranscribeError;
      }
      if (!nextTranscribeResult) {
        throw new Error('test forgot to setNextTranscribeResult');
      }
      return nextTranscribeResult;
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

// Stub the legacy aggregate lists with empty arrays so the test
// doesn't pull the full pre-PR-1 vocabulary into the test process.
// L1 itself no longer consumes those — the per-visit keyterm builder
// (PR-1 #246) reads SPECIALTY_KEYTERMS + CORE_KEYTERMS via
// buildKeytermsForVisit, and PR-2 wires CONFUSED_DRUG_NAMES_FLAT
// in as the safetyFloor argument. Those imports must resolve, so we
// preserve them via importOriginal — only the two big legacy
// aggregates get the empty-array override.
vi.mock('@/lib/deepgram-vocabulary', async (importOriginal) => {
  const actual =
    await importOriginal<typeof import('@/lib/deepgram-vocabulary')>();
  return {
    ...actual,
    CLINICAL_KEYTERMS: [],
    MEDICATION_KEYTERMS: [],
  };
});

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

function makeDeepgramResult(confidences: number[]): DeepgramBatchResult {
  const utterances = confidences.map((c, i) => makeUtterance(c, i));
  return {
    raw: { results: { utterances } } as unknown as DeepgramBatchResult['raw'],
    transcript: utterances.map((u) => u.transcript).join(' '),
    utterances,
    durationSec: utterances.length * 2,
  };
}

/** Wrap a DeepgramBatchResult into the orchestrator's TranscribeResult
 *  with provider='deepgram-batch' (no fallback). */
function makeResult(confidences: number[]): TranscribeResult {
  const dg = makeDeepgramResult(confidences);
  return {
    provider: 'deepgram-batch',
    transcript: dg.transcript,
    durationSec: dg.durationSec,
    language: 'en',
    costCents: 0,
    fallbackUsed: false,
    raw: { kind: 'deepgram', data: dg },
  };
}

/** Wrap a Whisper-shaped fixture as a fallback TranscribeResult. */
function makeWhisperFallbackResult(transcript: string): TranscribeResult {
  const whisper: WhisperBatchResult = {
    provider: 'whisper',
    transcript,
    durationSec: 30,
    segments: [
      {
        id: 0,
        start: 0,
        end: 30,
        text: transcript,
        avg_logprob: -0.3,
        no_speech_prob: 0.05,
        compression_ratio: 1.4,
        temperature: 0,
      },
    ],
    language: 'en',
    costCents: 18,
  };
  return {
    provider: 'whisper-fallback',
    transcript,
    durationSec: whisper.durationSec,
    language: whisper.language,
    costCents: whisper.costCents,
    fallbackUsed: true,
    primaryError: { message: 'Deepgram 503 Service Unavailable', status: 503 },
    raw: { kind: 'whisper', data: whisper },
  };
}

beforeEach(() => {
  updateCalls.length = 0;
  auditCalls.length = 0;
  nextTranscribeResult = null;
  nextTranscribeError = null;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('runLayer1Transcribe — audio confidence wiring', () => {
  it('persists audioConfidenceStats and flips needsReview on low-confidence audio', async () => {
    setNextTranscribeResult(
      makeResult([0.42, 0.38, 0.5, 0.3, 0.45, 0.48, 0.4, 0.35, 0.55, 0.4])
    );

    await runLayer1Transcribe(baseInput);

    // L1 may schedule a fire-and-forget keytermsApplied metadata write
    // (PR-1 #246) after the main visit-row update; that's an audit-
    // attribution side-effect, not part of the confidence-stats path.
    // The confidence-stats call is the awaited one and always sits at
    // updateCalls[0].
    expect(updateCalls.length).toBeGreaterThanOrEqual(1);
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
    setNextTranscribeResult(makeResult(Array(10).fill(0.95)));

    await runLayer1Transcribe(baseInput);

    // See note above: keytermsApplied write may trail; updateCalls[0] is the
    // confidence-stats row.
    expect(updateCalls.length).toBeGreaterThanOrEqual(1);
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
    setNextTranscribeResult({
      provider: 'deepgram-batch',
      transcript: '',
      durationSec: 0,
      language: 'en',
      costCents: 0,
      fallbackUsed: false,
      raw: {
        kind: 'deepgram',
        data: {
          raw: {} as unknown as DeepgramBatchResult['raw'],
          transcript: '',
          utterances: [],
          durationSec: 0,
        },
      },
    });

    await runLayer1Transcribe(baseInput);

    // See note above: keytermsApplied write may trail; updateCalls[0] is the
    // confidence-stats row.
    expect(updateCalls.length).toBeGreaterThanOrEqual(1);
    const data = updateCalls[0].data;

    expect(data.audioConfidenceStats).toBeNull();
    expect(data.needsReview).toBeUndefined();
  });

  it('flips needsReview via the lowConfPct branch (clean median, rough patches)', async () => {
    // 10 utterances: 6 clean, 4 rough — 40% > 30% threshold; median high.
    setNextTranscribeResult(
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

  it('persists transcriptionProvider=deepgram-batch on the happy path', async () => {
    setNextTranscribeResult(makeResult(Array(5).fill(0.9)));

    await runLayer1Transcribe(baseInput);

    const data = updateCalls[0].data;
    expect(data.transcriptionProvider).toBe('deepgram-batch');
    // No audit row on the happy path.
    expect(auditCalls).toHaveLength(0);
  });
});

describe('runLayer1Transcribe — Whisper fallback (PR-L follow-up)', () => {
  it('persists transcriptionProvider=whisper-fallback, flags review, emits audit row', async () => {
    setNextTranscribeResult(makeWhisperFallbackResult('patient reports headache'));

    const out = await runLayer1Transcribe(baseInput);

    // Visit row tagged with the canary provider. The L1 layer may
    // schedule an additional keytermsApplied fire-and-forget update
    // (PR-1 #246) — the awaited primary write at updateCalls[0] is
    // the one the canary check inspects.
    expect(updateCalls.length).toBeGreaterThanOrEqual(1);
    const data = updateCalls[0].data;
    expect(data.transcriptionProvider).toBe('whisper-fallback');
    expect(data.transcriptText).toBe('patient reports headache');

    // No diarization on Whisper → speakerCount falls back to 1, audioStats null.
    expect(out.speakerCount).toBe(1);
    expect(out.utteranceCount).toBe(0);
    expect(data.audioConfidenceStats).toBeNull();

    // Fallback flips review with a Whisper-specific reason.
    expect(data.needsReview).toBe(true);
    expect(data.reviewReason as string).toMatch(/whisper-fallback/i);
    expect(data.reviewReason as string).toMatch(/Deepgram failed/i);

    // Whisper raw shape persisted under the discriminator.
    const raw = data.transcriptRaw as { kind: string; segments: unknown[] };
    expect(raw.kind).toBe('whisper');
    expect(Array.isArray(raw.segments)).toBe(true);

    // Audit row emitted with metadata that ops can grep for.
    expect(auditCalls).toHaveLength(1);
    const audit = auditCalls[0];
    expect(audit.action).toBe('TRANSCRIPTION_PROVIDER_FALLBACK');
    expect(audit.targetType).toBe('TranscribeVisit');
    expect(audit.targetId).toBe(baseInput.visitId);
    expect(audit.userId).toBe(baseInput.userId);
    expect(audit.practiceId).toBe(baseInput.practiceId);
    expect(audit.metadata?.layer).toBe('L1');
    expect(audit.metadata?.primaryProvider).toBe('deepgram-batch');
    expect(audit.metadata?.fallbackProvider).toBe('whisper-fallback');
    expect(audit.metadata?.primaryStatus).toBe(503);
    expect(audit.metadata?.primaryError).toMatch(/503/);
  });
});

describe('runLayer1Transcribe — cross-provider fallback kill-switch (audit 4.2)', () => {
  it('re-throws + emits a suppressed-fallback audit (no visit write) when the fallback is disabled', async () => {
    // The orchestrator throws this when Deepgram fails, a Whisper
    // fallback WAS eligible, but the kill-switch is off — see
    // packages/ai/src/transcribe.ts.
    setNextTranscribeError(
      new CrossProviderFallbackDisabledError({
        message: 'Deepgram 503 Service Unavailable',
        status: 503,
      })
    );

    // The visit fails closed — L1 re-throws so the worker's outer catch
    // moves it to FAILED + the DLQ. (Retryable: categorizeError defaults
    // to transient, so BullMQ re-runs the job with a fresh Deepgram try.)
    await expect(runLayer1Transcribe(baseInput)).rejects.toBeInstanceOf(
      CrossProviderFallbackDisabledError
    );

    // No transcript was produced → the visit row is NOT stamped with a
    // provider (the success-path update never runs).
    expect(updateCalls.length).toBe(0);

    // A suppressed-fallback audit row IS emitted so ops can see how
    // often a real Deepgram failure WOULD have shipped audio to OpenAI.
    expect(auditCalls).toHaveLength(1);
    const audit = auditCalls[0];
    expect(audit.action).toBe('TRANSCRIPTION_PROVIDER_FALLBACK');
    expect(audit.targetId).toBe(baseInput.visitId);
    expect(audit.errorCode).toBe('CROSS_PROVIDER_FALLBACK_DISABLED');
    expect(audit.success).toBe(false);
    expect(audit.metadata?.layer).toBe('L1');
    expect(audit.metadata?.suppressed).toBe(true);
    expect(audit.metadata?.reason).toBe('fallback_disabled');
    expect(audit.metadata?.wouldHaveUsed).toBe('whisper-fallback');
    expect(audit.metadata?.primaryStatus).toBe(503);
  });
});
