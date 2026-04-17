// ============================================================================
// @meddoc/ai — unified ModelClient
// ----------------------------------------------------------------------------
// The surface apps/scribe workers call for every AI operation. Handles:
//   - Provider routing (openai vs anthropic)
//   - Zod-validated structured output with one automatic retry on schema
//     fail (spec §11)
//   - Per-call AiCall row (via the backend modules)
// ============================================================================

import type { z } from 'zod';
import { anthropicComplete } from './anthropic';
import { openaiTranscribe, type TranscribeResult } from './openai';
import type { AiLogContext, ModelProvider } from './types';

export type * from './types';
export type { TranscribeResult };

export interface CompleteArgs<T> extends AiLogContext {
  provider: Exclude<ModelProvider, 'deepgram'>;
  model: string;
  system: string;
  user: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
  /** Retry once on schema-fail with the error appended. Default true. */
  retryOnSchemaFail?: boolean;
}

export interface TranscribeArgs extends AiLogContext {
  audio: Buffer;
  fileName: string;
  language?: string;
  model?: string;
}

export const modelClient = {
  async complete<T>(args: CompleteArgs<T>): Promise<T> {
    if (args.provider !== 'anthropic') {
      throw new Error(
        `complete() with provider=${args.provider} is not wired yet — M2 only uses Anthropic.`
      );
    }
    try {
      return await anthropicComplete<T>({
        ...args,
        model: args.model,
      });
    } catch (err) {
      const retry = args.retryOnSchemaFail ?? true;
      if (
        retry &&
        err instanceof Error &&
        err.message === 'SCHEMA_FAIL'
      ) {
        const rawOutput = (err as Error & { rawOutput?: string }).rawOutput;
        const zodErrors = (err as Error & { zodErrors?: unknown }).zodErrors;
        return await anthropicComplete<T>({
          ...args,
          model: args.model,
          retryContext: `${rawOutput ?? ''}\n\nZod errors:\n${JSON.stringify(zodErrors, null, 2)}`,
        });
      }
      throw err;
    }
  },

  async transcribe(args: TranscribeArgs): Promise<TranscribeResult> {
    return openaiTranscribe(args);
  },
};

export type ModelClient = typeof modelClient;
