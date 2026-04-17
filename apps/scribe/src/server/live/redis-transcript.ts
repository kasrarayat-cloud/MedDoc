// ============================================================================
// Redis-backed live transcript list
// ----------------------------------------------------------------------------
// Spec §9: "Finalized segments appended to Redis list `visit:{id}:transcript`
// for durability." The list is the source of truth between WS receiving a
// final-from-Deepgram and the end-of-visit HTTP flush into ScribeTranscript.
//
// Key shape:  scribe:live:transcript:{visitId}
// Entry:      JSON-encoded LiveSegment
// TTL:        72h — safety net for orphaned sessions where the browser
//             never fires end-of-visit. Long enough to let ops recover
//             manually but short enough that forgotten data expires.
// ============================================================================

import type IORedis from 'ioredis';

export interface LiveSegment {
  /** Deepgram diarization label, e.g. "speaker_0" / "speaker_1". "UNKNOWN" if diarize returned no speaker. */
  speaker: string;
  startMs: number;
  endMs: number;
  text: string;
  /** Deepgram 0–1 confidence for the whole utterance. */
  confidence: number;
}

const TTL_SECONDS = 72 * 3600;

export function transcriptKey(visitId: string): string {
  return `scribe:live:transcript:${visitId}`;
}

export async function appendSegment(
  redis: IORedis,
  visitId: string,
  segment: LiveSegment
): Promise<void> {
  const key = transcriptKey(visitId);
  // RPUSH so LRANGE 0 -1 returns in chronological order.
  await redis.rpush(key, JSON.stringify(segment));
  await redis.expire(key, TTL_SECONDS);
}

export async function readAllSegments(
  redis: IORedis,
  visitId: string
): Promise<LiveSegment[]> {
  const raw = await redis.lrange(transcriptKey(visitId), 0, -1);
  return raw.map((entry) => JSON.parse(entry) as LiveSegment);
}

export async function clearSegments(redis: IORedis, visitId: string): Promise<void> {
  await redis.del(transcriptKey(visitId));
}
