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

import type { z } from "zod";
import {
  anthropicComplete,
  anthropicCompleteText,
  type AnthropicCompleteTextResult,
} from "./anthropic";
import { ModelOutputMalformedError } from "./errors";
import { isMockEnabled, mockComplete, mockCompleteText } from "./mock";
import { syntheticQaFixtureForProviderCall } from "./synthetic-qa-context";
import type { AiLogContext, ModelProvider } from "./types";

export type * from "./types";
export type { AnthropicCompleteTextResult };

/** T-M17.1: SCHEMA_FAIL and JSON_PARSE_FAIL from Claude have a ~5% per-call
 *  rate on dense-entity specialties (cardiology cohort saw 6/10 tm_entities
 *  calls fail before succeeding on a later attempt). Two retries catches
 *  >99% of these before BullMQ even sees the job as failed. */
const MAX_RETRIES = 2;

export interface CompleteArgs<T> extends AiLogContext {
  provider: Exclude<ModelProvider, "deepgram">;
  model: string;
  system: string;
  user: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
  /** Sampling temperature 0-1. Medical layers pin this low for
   *  determinism; undefined = provider default. */
  temperature?: number;
  /** Durable automation execution key. It is generated server-side and is
   * never accepted from a browser request. Provider support is best-effort;
   * the application ledger remains authoritative for replay safety. */
  idempotencyKey?: string;
  /** Retry on schema-fail or JSON-parse-fail with the prior output + error
   *  appended. Default true. Up to MAX_RETRIES attempts after the initial. */
  retryOnSchemaFail?: boolean;
  /** 2026-05-13 SCHEMA_FAIL hardening (cross-input-mode-audit Finding 1):
   *  opt-in to Anthropic's native tool_use structured output. When set,
   *  the model is forced to call a tool whose `input_schema` matches
   *  the Zod schema — eliminating free-form JSON.parse failures. See
   *  AnthropicCompleteArgs.useToolUse for details. Default: undefined
   *  (free-form JSON path, backwards-compatible with every existing
   *  layer). Should be enabled per-layer after empirical SCHEMA_FAIL
   *  monitoring. */
  useToolUse?: {
    name: string;
    description: string;
  };
}

export interface CompleteTextArgs extends AiLogContext {
  provider: Exclude<ModelProvider, "deepgram">;
  model: string;
  system: string;
  user: string;
  maxTokens?: number;
  /** Sampling temperature 0-1. Undefined = provider default. */
  temperature?: number;
  /** Durable server-generated execution key. Provider support is
   * best-effort; the application ownership ledger remains authoritative. */
  idempotencyKey?: string;
}

export const modelClient = {
  async complete<T>(args: CompleteArgs<T>): Promise<T> {
    const syntheticQaFixture = syntheticQaFixtureForProviderCall(args);
    if (syntheticQaFixture) {
      return mockComplete({
        purpose: args.purpose,
        schema: args.schema,
        fixtureVersion: syntheticQaFixture,
      });
    }
    // T-M10: MOCK_AI_CALLS short-circuit. See packages/ai/src/mock.ts
    // for the contract. No-op unless the env flag is true.
    if (isMockEnabled()) {
      return mockComplete({
        purpose: args.purpose,
        schema: args.schema,
        visitId: args.visitId,
      });
    }
    if (args.provider !== "anthropic") {
      throw new Error(
        `complete() with provider=${args.provider} is not wired yet — M2 only uses Anthropic.`,
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
        // FIND-P1-010 (2026-05-14): prefer instanceof over message scraping.
        // ModelOutputMalformedError is the new typed JSON.parse-fail; the
        // `.startsWith('Anthropic response was not valid JSON')` branch
        // stays as a belt-and-suspenders fallback while any in-flight
        // pre-typed throws drain.
        const isRetryable =
          err instanceof ModelOutputMalformedError ||
          (err instanceof Error &&
            (err.message === "SCHEMA_FAIL" ||
              err.message.startsWith("Anthropic response was not valid JSON")));
        if (!retryEnabled || !isRetryable || attempt === MAX_RETRIES) {
          throw err;
        }
        // Retry context: ModelOutputMalformedError carries the raw text
        // slice directly; SCHEMA_FAIL stamps it on the legacy fields.
        if (err instanceof ModelOutputMalformedError) {
          retryContext = `Previous response failed JSON.parse:\n${err.rawTextSlice}`;
        } else {
          const rawOutput = (err as Error & { rawOutput?: string }).rawOutput;
          const zodErrors = (err as Error & { zodErrors?: unknown }).zodErrors;
          retryContext = zodErrors
            ? `${rawOutput ?? ""}\n\nZod errors:\n${JSON.stringify(zodErrors, null, 2)}`
            : `Previous response failed to parse: ${(err as Error).message}`;
        }
      }
    }
    // TS needs a terminal return — unreachable given the loop above.
    throw new Error("modelClient.complete: retry loop exhausted unexpectedly");
  },

  /**
   * Plain-text completion for layers that output markdown rather than
   * JSON (T-M4 Layer 4 SOAP draft, Layer 6 polish). Returns the raw
   * text + the Anthropic-reported token counts so the caller can roll
   * them into a per-visit cost aggregate if it wants to, independent
   * of the AiCall row this call already wrote.
   */
  async completeText(
    args: CompleteTextArgs,
  ): Promise<AnthropicCompleteTextResult> {
    const syntheticQaFixture = syntheticQaFixtureForProviderCall(args);
    if (syntheticQaFixture) {
      return mockCompleteText({
        purpose: args.purpose,
        fixtureVersion: syntheticQaFixture,
      });
    }
    // T-M10: MOCK_AI_CALLS short-circuit. See packages/ai/src/mock.ts.
    if (isMockEnabled()) {
      return mockCompleteText({
        purpose: args.purpose,
        visitId: args.visitId,
      });
    }
    if (args.provider !== "anthropic") {
      throw new Error(
        `completeText() with provider=${args.provider} is not wired yet — T-M4 only uses Anthropic.`,
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
      idempotencyKey: args.idempotencyKey,
    });
  },
};

export type ModelClient = typeof modelClient;
