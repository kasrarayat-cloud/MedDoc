// ============================================================================
// @meddoc/ai — Deepgram live transcription backend
// ----------------------------------------------------------------------------
// Owned by the scribe-ws sidecar (M3). Exposes a narrow surface: open a
// LiveClient with the mandated nova-3-medical + diarize + interim config,
// and log one AiCall row per session at close time. Per-utterance logging
// is intentionally skipped — it would add noise without new signal.
//
// Spec §5 + §9: Deepgram is the real-time ASR provider. Options are
// locked here (diarize / interim / punctuate / smart_format) so no
// caller can weaken them per-visit.
// ============================================================================

import {
  createClient,
  LiveTranscriptionEvents,
  type LiveClient,
  type LiveSchema,
  type LiveTranscriptionEvent,
} from '@deepgram/sdk';
import { logAiCall } from './log';
import type { AiLogContext } from './types';

let clientSingleton: ReturnType<typeof createClient> | null = null;

function getClient(): ReturnType<typeof createClient> {
  if (clientSingleton) return clientSingleton;
  const apiKey = process.env.DEEPGRAM_API_KEY;
  if (!apiKey) {
    throw new Error('DEEPGRAM_API_KEY is not set.');
  }
  clientSingleton = createClient(apiKey);
  return clientSingleton;
}

export const DEFAULT_LIVE_MODEL = 'nova-3-medical';

export interface OpenLiveTranscriptionArgs {
  /** Optional model override; defaults to DEEPGRAM_MODEL env or nova-3-medical. */
  model?: string;
  /** IETF language tag. Defaults to en. */
  language?: string;
}

export interface OpenedLiveTranscription {
  client: LiveClient;
  model: string;
}

/**
 * Open a live transcription stream. Caller owns the returned client:
 * attach event handlers via `client.on(LiveTranscriptionEvents.X, ...)`,
 * push audio frames via `client.send(buf)`, and call
 * `client.requestClose()` on end.
 *
 * We do NOT pass `encoding`/`sample_rate` — browser `MediaRecorder` emits
 * a WebM/Opus container which Deepgram auto-detects (spec §9 D2 decision).
 */
export function openLiveTranscription(
  args: OpenLiveTranscriptionArgs = {}
): OpenedLiveTranscription {
  const model = args.model ?? process.env.DEEPGRAM_MODEL?.trim() ?? DEFAULT_LIVE_MODEL;
  const client = getClient().listen.live({
    model,
    language: args.language ?? 'en',
    diarize: true,
    interim_results: true,
    punctuate: true,
    smart_format: true,
  } satisfies LiveSchema);
  return { client, model };
}

export interface LogLiveSessionArgs extends AiLogContext {
  model: string;
  /** How many finalized utterances the session produced. */
  utteranceCount: number;
  /** Wall-clock duration of the Deepgram connection, in ms. */
  latencyMs: number;
  success: boolean;
  errorCode?: string;
}

/**
 * Log one AiCall row summarising a live-transcription session at close
 * time. promptHash is a marker ("live:<N>u") — there is no text prompt
 * for streaming ASR, and we must not hash transcript content (spec §5
 * "no PHI in this table").
 */
export function logLiveSession(args: LogLiveSessionArgs): void {
  logAiCall({
    practiceId: args.practiceId,
    visitId: args.visitId,
    purpose: args.purpose,
    provider: 'deepgram',
    model: args.model,
    promptHash: `live:${args.utteranceCount}u`,
    latencyMs: args.latencyMs,
    success: args.success,
    errorCode: args.errorCode,
  });
}

export {
  LiveTranscriptionEvents,
  type LiveTranscriptionEvent,
  type LiveClient,
};
