// ============================================================================
// @meddoc/ai — unified ModelClient
// ----------------------------------------------------------------------------
// The surface apps/scribe + apps/transcribe-md workers call for every AI
// operation. Handles:
//   - Provider routing (openai vs anthropic)
//   - Zod-validated structured output with one automatic retry on schema
//     fail (spec §11)
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

export interface CompleteTextArgs extends AiLogContext {
  provider: Exclude<ModelProvider, 'deepgram'>;
  model: string;
  system: string;
  user: string;
  maxTokens?: number;
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
      purpose: args.purpose,
      model: args.model,
      system: args.system,
      user: args.user,
      maxTokens: args.maxTokens,
    });
  },
};

export type ModelClient = typeof modelClient;
