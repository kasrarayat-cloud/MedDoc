// ============================================================================
// @meddoc/ai — OpenAI backend (Whisper transcription + optional chat)
// ----------------------------------------------------------------------------
// Whisper is used for batch transcription (M2) via the default
// gpt-4o-transcribe model. Env override via TRANSCRIPTION_MODEL so we
// can swap to whisper-1 or a future model without code changes.
// ============================================================================

import OpenAI, { toFile } from 'openai';
import { logAiCall } from './log';
import type { AiLogContext } from './types';

let clientSingleton: OpenAI | null = null;
function getClient(): OpenAI {
  if (clientSingleton) return clientSingleton;
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY is not set.');
  }
  clientSingleton = new OpenAI({ apiKey });
  return clientSingleton;
}

export interface OpenAITranscribeArgs extends AiLogContext {
  audio: Buffer;
  fileName: string;
  language?: string;
  model?: string;
}

export interface TranscribeResult {
  text: string;
  durationSec: number | null;
  model: string;
}

export async function openaiTranscribe(args: OpenAITranscribeArgs): Promise<TranscribeResult> {
  const client = getClient();
  const model = args.model ?? process.env.TRANSCRIPTION_MODEL ?? 'gpt-4o-transcribe';
  const started = Date.now();

  try {
    const file = await toFile(args.audio, args.fileName);
    // `verbose_json` gives us duration; works with whisper-1. For
    // gpt-4o-transcribe the response shape is simpler — guard below.
    const response = (await client.audio.transcriptions.create({
      file,
      model,
      language: args.language,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      response_format: model === 'whisper-1' ? ('verbose_json' as any) : ('json' as any),
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
    })) as any;

    const latencyMs = Date.now() - started;
    const text = String(response.text ?? '').trim();
    const durationSec =
      typeof response.duration === 'number' ? Math.round(response.duration) : null;

    logAiCall({
      ...args,
      provider: 'openai',
      model,
      promptHash: 'audio', // transcription has no text prompt
      latencyMs,
      success: true,
    });

    return { text, durationSec, model };
  } catch (err) {
    const latencyMs = Date.now() - started;
    logAiCall({
      ...args,
      provider: 'openai',
      model,
      promptHash: 'audio',
      latencyMs,
      success: false,
      errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
    });
    throw err;
  }
}
