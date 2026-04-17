// ============================================================================
// Live-transcript flush — Redis list → ScribeTranscript
// ----------------------------------------------------------------------------
// Called from /api/uploads/:id/live-complete when the clinician clicks
// "End visit". Drains the Redis list, writes one ScribeTranscript row
// scoped to the visit's practice, and clears Redis so the list can't be
// double-flushed.
//
// Pure builder (buildTranscriptData) is unit-tested; the DB orchestrator
// (persistLiveTranscript) is exercised end-to-end in the manual smoke
// described in the M3 plan.
// ============================================================================

import prisma from '@meddoc/db';
import type IORedis from 'ioredis';
import { clearSegments, readAllSegments, type LiveSegment } from './redis-transcript';

export interface TranscriptData {
  segments: { speaker: string; startMs: number; endMs: number; text: string; confidence: number }[];
  rawFullText: string;
  language: string;
  provider: string;
}

/**
 * Pure builder: takes the raw Redis segment list and produces the shape
 * we persist into ScribeTranscript. No DB calls so this can be tested
 * without a running database.
 *
 * If there are no segments (e.g. user ended before speaking), we still
 * return a valid row — rawFullText is empty and downstream cleanup/SOAP
 * will flag confidence=low.
 */
export function buildTranscriptData(
  segments: LiveSegment[],
  model: string
): TranscriptData {
  const rawFullText = segments
    .map((s) => `${s.speaker}: ${s.text}`)
    .join('\n')
    .trim();

  return {
    segments: segments.map((s) => ({
      speaker: s.speaker,
      startMs: s.startMs,
      endMs: s.endMs,
      text: s.text,
      confidence: s.confidence,
    })),
    rawFullText,
    language: 'en',
    provider: `deepgram-${model}`,
  };
}

/**
 * Orchestrator: read Redis → build → upsert ScribeTranscript → clear Redis.
 * Returns the number of segments that were flushed so the caller can
 * include it in the audit event.
 *
 * We upsert (not create) in case the flush is retried after a network
 * blip on the client — idempotent on a single visit.
 */
export async function persistLiveTranscript(
  redis: IORedis,
  args: {
    visitId: string;
    practiceId: string;
    deepgramModel: string;
  }
): Promise<{ segmentCount: number; rawFullTextLength: number }> {
  const segments = await readAllSegments(redis, args.visitId);
  const data = buildTranscriptData(segments, args.deepgramModel);

  await prisma.scribeTranscript.upsert({
    where: { visitId: args.visitId },
    create: {
      practiceId: args.practiceId,
      visitId: args.visitId,
      segments: data.segments,
      rawFullText: data.rawFullText,
      language: data.language,
      provider: data.provider,
    },
    update: {
      segments: data.segments,
      rawFullText: data.rawFullText,
      language: data.language,
      provider: data.provider,
    },
  });

  await clearSegments(redis, args.visitId);

  return {
    segmentCount: segments.length,
    rawFullTextLength: data.rawFullText.length,
  };
}
