// ============================================================================
// @meddoc/ai — unified ModelClient
// ----------------------------------------------------------------------------
// The surface apps/scribe + apps/transcribe-md workers call for every AI
// operation. Handles:
//   - Provider routing (openai vs anthropic)
//   - Zod-validated structured output with automatic retry on schema-fail
//     or JSON-parse-fail (T-M17.1: up to 2 retries)
//   - Plain-text completion for markdown-producing layers (T-M4 §L4, §L6)
//   - Per-call AiCall row (via the backend modules)
// ============================================================================

import type { z } from 'zod';
import {
  anthropicComplete,
  anthropicCompleteText,
  type AnthropicCompleteTextResult,
} from './anthropic';
import {
  isMockEnabled,
  mockComplete,
  mockCompleteText,
} from './mock';
import type { AiLogContext, ModelProvider } from './types';

export type * from './types';
export type { AnthropicCompleteTextResult };

/** T-M17.1: SCHEMA_FAIL and JSON_PARSE_FAIL from Claude have a ~5% per-call
 *  rate on dense-entity specialties (cardiology cohort saw 6/10 tm_entities
 *  calls fail before succeeding on a later attempt). Two retries catches
 *  >99% of these before BullMQ even sees the job as failed. */
const MAX_RETRIES = 2;

export interface CompleteArgs<T> extends AiLogContext {
  provider: Exclude<ModelProvider, 'deepgram'>;
  model: string;
  system: string;
  user: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
  /** Sampling temperature 0-1. Medical layers pin this low for
   *  determinism; undefined = provider default. */
  temperature?: number;
  /** Retry on schema-fail or JSON-parse-fail with the prior output + error
   *  appended. Default true. Up to MAX_RETRIES attempts after the initial. */
  retryOnSchemaFail?: boolean;
}

export interface CompleteTextArgs extends AiLogContext {
  provider: Exclude<ModelProvider, 'deepgram'>;
  model: string;
  system: string;
  user: string;
  maxTokens?: number;
  /** Sampling temperature 0-1. Undefined = provider default. */
  temperature?: number;
}

export const modelClient = {
  async complete<T>(args: CompleteArgs<T>): Promise<T> {
    // T-M10: MOCK_AI_CALLS short-circuit. See packages/ai/src/mock.ts
    // for the contract. No-op unless the env flag is true.
    if (isMockEnabled()) {
      return mockComplete({ purpose: args.purpose, schema: args.schema });
    }
    if (args.provider !== 'anthropic') {
      throw new Error(
        `complete() with provider=${args.provider} is not wired yet — M2 only uses Anthropic.`
      );
    }
    const retryEnabled = args.retryOnSchemaFail ?? true;
    let retryContext: string | undefined;
    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        return await anthropicComplete<T>({
          ...args,
          model: args.model,
          retryContext,
        });
      } catch (err) {
        const isRetryable =
          err instanceof Error &&
          (err.message === 'SCHEMA_FAIL' ||
            err.message.startsWith('Anthropic response was not valid JSON'));
        if (!retryEnabled || !isRetryable || attempt === MAX_RETRIES) {
          throw err;
        }
        const rawOutput = (err as Error & { rawOutput?: string }).rawOutput;
        const zodErrors = (err as Error & { zodErrors?: unknown }).zodErrors;
        retryContext = zodErrors
          ? `${rawOutput ?? ''}\n\nZod errors:\n${JSON.stringify(zodErrors, null, 2)}`
          : `Previous response failed to parse: ${err.message}`;
      }
    }
    // TS needs a terminal return — unreachable given the loop above.
    throw new Error('modelClient.complete: retry loop exhausted unexpectedly');
  },

  /**
   * Plain-text completion for layers that output markdown rather than
   * JSON (T-M4 Layer 4 SOAP draft, Layer 6 polish). Returns the raw
   * text + the Anthropic-reported token counts so the caller can roll
   * them into a per-visit cost aggregate if it wants to, independent
   * of the AiCall row this call already wrote.
   */
  async completeText(args: CompleteTextArgs): Promise<AnthropicCompleteTextResult> {
    // T-M10: MOCK_AI_CALLS short-circuit. See packages/ai/src/mock.ts.
    if (isMockEnabled()) {
      return mockCompleteText({ purpose: args.purpose });
    }
    if (args.provider !== 'anthropic') {
      throw new Error(
        `completeText() with provider=${args.provider} is not wired yet — T-M4 only uses Anthropic.`
      );
    }
    return anthropicCompleteText({
      practiceId: args.practiceId,
      visitId: args.visitId,
      // Phase 6F — userId was being silently dropped here, which made
      // every api_usage_events row for completeText carry NULL userId
      // even after the worker started passing userId in.
      userId: args.userId ?? null,
      purpose: args.purpose,
      model: args.model,
      system: args.system,
      user: args.user,
      maxTokens: args.maxTokens,
      temperature: args.temperature,
    });
  },
};

export type ModelClient = typeof modelClient;
