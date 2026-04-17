// ============================================================================
// buildTranscriptData — Redis live segments → ScribeTranscript shape
// ----------------------------------------------------------------------------
// Pure function test. The orchestrator persistLiveTranscript() is
// exercised in the post-merge manual smoke (per M1/M2 convention);
// here we lock in the builder semantics that the route + any future
// caller rely on.
// ============================================================================

import { describe, it, expect } from 'vitest';
import {
  buildTranscriptData,
  type TranscriptData,
} from '../../../scribe/src/server/live/flush';
import type { LiveSegment } from '../../../scribe/src/server/live/redis-transcript';

describe('buildTranscriptData', () => {
  const model = 'nova-3-medical';

  it('returns an empty but valid transcript when no segments arrived', () => {
    const out: TranscriptData = buildTranscriptData([], model);
    expect(out.segments).toEqual([]);
    expect(out.rawFullText).toBe('');
    expect(out.language).toBe('en');
    expect(out.provider).toBe('deepgram-nova-3-medical');
  });

  it('preserves order + joins rawFullText with speaker-prefixed lines', () => {
    const segments: LiveSegment[] = [
      { speaker: 'speaker_0', startMs: 0, endMs: 1500, text: 'Hello there.', confidence: 0.97 },
      { speaker: 'speaker_1', startMs: 1800, endMs: 3000, text: 'My chest hurts.', confidence: 0.91 },
      { speaker: 'speaker_0', startMs: 3200, endMs: 4500, text: 'How long?', confidence: 0.95 },
    ];
    const out = buildTranscriptData(segments, model);

    expect(out.rawFullText).toBe(
      'speaker_0: Hello there.\nspeaker_1: My chest hurts.\nspeaker_0: How long?'
    );
    expect(out.segments).toHaveLength(3);
    expect(out.segments[0]).toEqual(segments[0]);
    expect(out.segments[2].text).toBe('How long?');
  });

  it('propagates UNKNOWN speaker labels without rewriting them', () => {
    const segments: LiveSegment[] = [
      { speaker: 'UNKNOWN', startMs: 0, endMs: 500, text: 'Hmm.', confidence: 0.8 },
    ];
    const out = buildTranscriptData(segments, model);
    expect(out.rawFullText).toBe('UNKNOWN: Hmm.');
    expect(out.segments[0].speaker).toBe('UNKNOWN');
  });

  it('stamps the Deepgram model on provider so downstream knows the source', () => {
    const out = buildTranscriptData([], 'nova-3-medical');
    expect(out.provider).toBe('deepgram-nova-3-medical');

    const out2 = buildTranscriptData([], 'nova-2');
    expect(out2.provider).toBe('deepgram-nova-2');
  });
});
