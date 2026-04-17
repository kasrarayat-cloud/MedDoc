// ============================================================================
// LiveSession — one browser WS bound to one Deepgram live connection
// ----------------------------------------------------------------------------
// Responsibilities:
//   - Proxy browser audio frames → Deepgram
//   - Relay Deepgram interim/final transcripts → browser
//   - Append finalized segments to the Redis durability list
//   - Handle lifecycle: Open, Close, Error, user-initiated end
//   - Emit audit events + AiCall summary at close time
//   - Release the per-user concurrency lock on close
//
// Does NOT: write ScribeTranscript, update visit status, enqueue
// finalize_visit. Those happen in the HTTP /live-complete route so the
// flush logic is visible + testable from the web container (WS server
// stays single-responsibility).
// ============================================================================

import type { RawData, WebSocket } from 'ws';
import type IORedis from 'ioredis';
import {
  openLiveTranscription,
  LiveTranscriptionEvents,
  logLiveSession,
  redactPhi,
  type LiveTranscriptionEvent,
} from '@meddoc/ai';
import prisma from '@meddoc/db';
import { appendSegment, type LiveSegment } from './redis-transcript';
import { releaseLiveLock } from './concurrency';

export interface LiveSessionInit {
  ws: WebSocket;
  redis: IORedis;
  visitId: string;
  practiceId: string;
  userId: string;
}

type CloseReason =
  | 'user_end'
  | 'client_disconnect'
  | 'server_error'
  | 'deepgram_error';

/**
 * ws.RawData → ArrayBuffer. Deepgram's send() is typed as ArrayBufferLike
 * but the underlying ws.send accepts Buffer — we normalise here to keep
 * the types honest.
 */
function toArrayBuffer(data: RawData): ArrayBuffer {
  if (Buffer.isBuffer(data)) {
    return data.buffer.slice(
      data.byteOffset,
      data.byteOffset + data.byteLength
    ) as ArrayBuffer;
  }
  if (data instanceof ArrayBuffer) return data;
  // Buffer[] — concat.
  const parts = data as Buffer[];
  const total = parts.reduce((n, b) => n + b.byteLength, 0);
  const out = Buffer.allocUnsafe(total);
  let offset = 0;
  for (const part of parts) {
    part.copy(out, offset);
    offset += part.byteLength;
  }
  return out.buffer.slice(out.byteOffset, out.byteOffset + out.byteLength) as ArrayBuffer;
}

export function startLiveSession(init: LiveSessionInit): void {
  const { ws, redis, visitId, practiceId, userId } = init;
  const startedAt = Date.now();
  let utteranceCount = 0;
  let closed = false;

  const dg = openLiveTranscription();

  const safeSend = (payload: unknown): void => {
    if (ws.readyState !== ws.OPEN) return;
    ws.send(JSON.stringify(payload));
  };

  dg.client.on(LiveTranscriptionEvents.Open, () => {
    safeSend({ type: 'ready', model: dg.model });
  });

  dg.client.on(LiveTranscriptionEvents.Transcript, (data: LiveTranscriptionEvent) => {
    const alt = data.channel?.alternatives?.[0];
    if (!alt || !alt.transcript) return;
    // Deepgram returns `speaker: number` on each word when diarize=true.
    // We label the whole utterance by its first word's speaker — Deepgram
    // won't mix speakers within a single final in the normal flow.
    const firstSpeaker = alt.words?.[0]?.speaker;
    const speaker =
      typeof firstSpeaker === 'number' ? `speaker_${firstSpeaker}` : 'UNKNOWN';

    if (data.is_final) {
      const segment: LiveSegment = {
        speaker,
        startMs: Math.round(data.start * 1000),
        endMs: Math.round((data.start + data.duration) * 1000),
        text: alt.transcript,
        confidence: alt.confidence,
      };
      utteranceCount += 1;
      void appendSegment(redis, visitId, segment).catch((err) => {
        console.error(
          `[live ${visitId}] redis append failed:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
      });
      safeSend({ type: 'final', ...segment });
    } else {
      safeSend({ type: 'interim', speaker, text: alt.transcript });
    }
  });

  dg.client.on(LiveTranscriptionEvents.Error, (err: unknown) => {
    console.error(
      `[live ${visitId}] deepgram error:`,
      redactPhi(err instanceof Error ? err.message : err)
    );
    safeSend({ type: 'error', code: 'DEEPGRAM_ERROR' });
    close('deepgram_error');
  });

  dg.client.on(LiveTranscriptionEvents.Close, () => {
    if (!closed) close('deepgram_error');
  });

  ws.on('message', (data: RawData, isBinary: boolean) => {
    if (isBinary) {
      try {
        dg.client.send(toArrayBuffer(data));
      } catch (err) {
        console.error(
          `[live ${visitId}] deepgram send failed:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
      }
      return;
    }
    // Text frame — control message from the browser.
    let msg: unknown;
    try {
      msg = JSON.parse(data.toString());
    } catch {
      return;
    }
    if (msg && typeof msg === 'object' && (msg as { type?: unknown }).type === 'end') {
      // Ask Deepgram to flush pending audio so we get any trailing finals,
      // then close after a short grace window.
      try {
        dg.client.finalize();
      } catch {
        /* ignored — close path handles it */
      }
      setTimeout(() => close('user_end'), 1500);
    }
  });

  ws.on('close', () => close('client_disconnect'));
  ws.on('error', () => close('server_error'));

  function close(reason: CloseReason): void {
    if (closed) return;
    closed = true;
    const latencyMs = Date.now() - startedAt;

    try {
      dg.client.requestClose();
    } catch {
      /* already closed or closing */
    }
    safeSend({ type: 'closed', reason });
    try {
      ws.close();
    } catch {
      /* already closed */
    }

    void prisma.scribeAuditEvent
      .create({
        data: {
          practiceId,
          visitId,
          actorId: userId,
          action: 'WS_DISCONNECTED',
          diff: { reason, latencyMs, utteranceCount },
        },
      })
      .catch((err: unknown) => {
        console.error(
          `[live ${visitId}] WS_DISCONNECTED audit failed:`,
          redactPhi(err instanceof Error ? err.message : err)
        );
      });

    void releaseLiveLock(redis, userId, visitId).catch((err: unknown) => {
      console.error(
        `[live ${visitId}] releaseLock failed:`,
        redactPhi(err instanceof Error ? err.message : err)
      );
    });

    logLiveSession({
      practiceId,
      visitId,
      purpose: 'transcribe_realtime',
      model: dg.model,
      utteranceCount,
      latencyMs,
      success: reason === 'user_end' || reason === 'client_disconnect',
      errorCode:
        reason === 'deepgram_error' || reason === 'server_error' ? reason : undefined,
    });
  }
}
