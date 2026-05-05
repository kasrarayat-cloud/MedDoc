// ============================================================================
// @meddoc/ai — Anthropic Claude backend
// ----------------------------------------------------------------------------
// Used for transcript cleanup + SOAP generation (M2) and the other
// structured-output pipeline steps (M4+). Models are env-configurable;
// default is claude-sonnet-4-6 per the M2 plan. Never use aliases in
// prod — models are pinned to exact date-stamped IDs via env.
// ============================================================================

import Anthropic from '@anthropic-ai/sdk';
import type { z } from 'zod';
import { hashPrompt } from './prompt-hash';
import { logAiCall } from './log';
import { claudeCostCents } from './pricing';
import type { AiLogContext } from './types';
import { logApiUsage, buildAnthropicUsage } from './api-usage';

let clientSingleton: Anthropic | null = null;
function getClient(): Anthropic {
  if (clientSingleton) return clientSingleton;
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY is not set.');
  }
  clientSingleton = new Anthropic({ apiKey });
  return clientSingleton;
}

/** T-M17.1: cap persisted response bodies so a pathological 100 KB
 *  Claude stream doesn't bloat ai_calls rows. ~10 KB is ample for a
 *  failing JSON payload + Zod errors. */
const ERROR_DETAILS_MAX_BYTES = 10_240;
const TRUNCATED_SUFFIX = '\n... [truncated]';

function capErrorDetails(raw: string): string {
  if (raw.length <= ERROR_DETAILS_MAX_BYTES) return raw;
  return (
    raw.slice(0, ERROR_DETAILS_MAX_BYTES - TRUNCATED_SUFFIX.length) +
    TRUNCATED_SUFFIX
  );
}

/** Q2 follow-up — Anthropic deprecated `temperature` on the Opus 4
 *  family (4.7 returns 400 invalid_request_error("`temperature` is
 *  deprecated for this model.")). The Sonnet + Haiku families still
 *  accept it. Strip silently for Opus 4.x; pass through for everything
 *  else. Layer source files keep their `temperature: 0.x` lines as
 *  documentation of intent — the library honors the wire contract. */
function shouldOmitTemperature(model: string): boolean {
  return model.startsWith('claude-opus-4');
}

/** Q2 follow-up — when an Anthropic SDK call throws (network blip,
 *  4xx, 5xx, refusal), extract the structured error fields into a
 *  small JSON payload suitable for `ai_calls.errorDetails`.
 *
 *  Capped at 4 KB. Never includes request payloads (PHI / transcript
 *  content). Only the API's response body + status + request id. */
const ERROR_DETAILS_MAX_JSON_BYTES = 4096;

interface AnthropicErrorShape {
  httpStatus: number | null;
  apiErrorType: string | null;
  apiErrorMessage: string | null;
  requestId: string | null;
}

function extractAnthropicError(err: unknown): AnthropicErrorShape {
  const obj = err as Record<string, unknown> | null;
  if (!obj || typeof obj !== 'object') {
    return { httpStatus: null, apiErrorType: null, apiErrorMessage: null, requestId: null };
  }
  const httpStatus =
    typeof obj.status === 'number' && Number.isFinite(obj.status as number)
      ? (obj.status as number)
      : null;
  // SDK's BadRequestError exposes the parsed body at `.error`. The
  // body shape is { type: 'error', error: { type: string, message: string } }.
  const body = obj.error as Record<string, unknown> | undefined;
  const inner = body?.error as Record<string, unknown> | undefined;
  const apiErrorType =
    typeof inner?.type === 'string' ? (inner.type as string) : null;
  const apiErrorMessage =
    typeof inner?.message === 'string' ? (inner.message as string) : null;
  const requestId =
    typeof obj.request_id === 'string'
      ? (obj.request_id as string)
      : typeof (obj.headers as Record<string, unknown> | undefined)?.[
          'request-id'
        ] === 'string'
        ? ((obj.headers as Record<string, unknown>)['request-id'] as string)
        : null;
  return { httpStatus, apiErrorType, apiErrorMessage, requestId };
}

export function anthropicErrorDetailsJson(err: unknown): string {
  const shape = extractAnthropicError(err);
  // Truncate apiErrorMessage if needed to keep JSON under cap.
  const trimmedMsg = shape.apiErrorMessage
    ? shape.apiErrorMessage.length > 1024
      ? shape.apiErrorMessage.slice(0, 1024) + '… [truncated]'
      : shape.apiErrorMessage
    : null;
  const payload = {
    httpStatus: shape.httpStatus,
    apiErrorType: shape.apiErrorType,
    apiErrorMessage: trimmedMsg,
    requestId: shape.requestId,
  };
  const json = JSON.stringify(payload);
  if (json.length <= ERROR_DETAILS_MAX_JSON_BYTES) return json;
  // Pathological — fall back to the bare httpStatus + truncated marker.
  return JSON.stringify({
    httpStatus: shape.httpStatus,
    apiErrorType: shape.apiErrorType,
    apiErrorMessage: '[truncated — payload exceeded 4KB]',
    requestId: shape.requestId,
  });
}

export interface AnthropicCompleteArgs<T> extends AiLogContext {
  model: string;
  system: string;
  user: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
  /** Sampling temperature 0-1. Undefined = SDK/provider default (≈1).
   *  Medical layers should pass low values for determinism. */
  temperature?: number;
  /** Extra messages appended for retry — e.g. the prior invalid response + error. */
  retryContext?: string;
}

export async function anthropicComplete<T>(args: AnthropicCompleteArgs<T>): Promise<T> {
  const client = getClient();
  const userContent = args.retryContext
    ? `${args.user}\n\n---\nPrevious attempt was rejected by schema validation:\n${args.retryContext}\n\nReturn ONLY the corrected JSON that passes the schema.`
    : args.user;

  const promptHash = hashPrompt(args.system, userContent);
  const started = Date.now();

  try {
    const response = await client.messages.create({
      model: args.model,
      max_tokens: args.maxTokens ?? 4096,
      ...(args.temperature !== undefined && !shouldOmitTemperature(args.model)
        ? { temperature: args.temperature }
        : {}),
      system: args.system,
      messages: [{ role: 'user', content: userContent }],
    });

    const latencyMs = Date.now() - started;

    // Concatenate all text content blocks. Anthropic responses usually
    // have one block but the API is arrayed.
    const text = response.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim();

    // Claude sometimes wraps JSON in ```json … ``` fences even when told
    // not to. Strip fences before parsing.
    const unfenced = text
      .replace(/^```(?:json)?\s*/i, '')
      .replace(/```$/, '')
      .trim();

    let parsed: unknown;
    try {
      parsed = JSON.parse(unfenced);
    } catch (err) {
      logAiCall({
        ...args,
        provider: 'anthropic',
        promptHash,
        latencyMs,
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
        costUsdCents: claudeCostCents(
          args.model,
          response.usage.input_tokens,
          response.usage.output_tokens
        ),
        success: false,
        errorCode: 'JSON_PARSE_FAIL',
        errorDetails: capErrorDetails(unfenced),
      });
      throw new Error(`Anthropic response was not valid JSON: ${String(err)}`);
    }

    const schemaResult = args.schema.safeParse(parsed);
    if (!schemaResult.success) {
      logAiCall({
        ...args,
        provider: 'anthropic',
        promptHash,
        latencyMs,
        inputTokens: response.usage.input_tokens,
        outputTokens: response.usage.output_tokens,
        costUsdCents: claudeCostCents(
          args.model,
          response.usage.input_tokens,
          response.usage.output_tokens
        ),
        success: false,
        errorCode: 'SCHEMA_FAIL',
        errorDetails: capErrorDetails(
          `${unfenced}\n\n--- Zod errors ---\n${JSON.stringify(schemaResult.error.issues, null, 2)}`
        ),
      });
      const err = new Error('SCHEMA_FAIL') as Error & {
        rawOutput?: string;
        zodErrors?: unknown;
      };
      err.rawOutput = unfenced;
      err.zodErrors = schemaResult.error.issues;
      throw err;
    }

    logAiCall({
      ...args,
      provider: 'anthropic',
      promptHash,
      latencyMs,
      inputTokens: response.usage.input_tokens,
      outputTokens: response.usage.output_tokens,
      costUsdCents: claudeCostCents(
        args.model,
        response.usage.input_tokens,
        response.usage.output_tokens
      ),
      success: true,
    });

    logApiUsage(
      buildAnthropicUsage(
        {
          userId: args.userId ?? null,
          practiceId: args.practiceId,
          visitId: args.visitId ?? null,
          metadata: { purpose: args.purpose, latencyMs },
        },
        response.usage.input_tokens,
        response.usage.output_tokens,
        args.model,
        args.purpose
      )
    );

    return schemaResult.data;
  } catch (err) {
    // Re-throw after logging — schema fails and JSON parse fails already
    // logged themselves above, so this catches network / 429 / auth errors.
    // Q2 follow-up: persist the structured Anthropic error body to
    // ai_calls.errorDetails so the forensic chain doesn't have to scrape
    // worker logs to find the actual failure mode (e.g., the Opus 4.7
    // temperature-deprecation 400 was invisible at the DB level until now).
    const latencyMs = Date.now() - started;
    if (!(err instanceof Error) || (err.message !== 'SCHEMA_FAIL' && !err.message.startsWith('Anthropic response'))) {
      logAiCall({
        ...args,
        provider: 'anthropic',
        promptHash,
        latencyMs,
        success: false,
        errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
        errorDetails: anthropicErrorDetailsJson(err),
      });
    }
    throw err;
  }
}

// ============================================================================
// Text completion — T-M4 layers 4 (SOAP draft) + 6 (polish) expect
// markdown output, not JSON. Mirror the logging surface of
// anthropicComplete so AiCall rows are homogeneous; only difference is
// we don't parse the output.
// ============================================================================

export interface AnthropicCompleteTextArgs extends AiLogContext {
  model: string;
  system: string;
  user: string;
  maxTokens?: number;
  /** Sampling temperature 0-1. Undefined = SDK/provider default (≈1). */
  temperature?: number;
  /** How many text tokens we want the model to be willing to produce.
   *  SOAP notes can run long — default 8192 rather than 4096. */
}

export interface AnthropicCompleteTextResult {
  text: string;
  inputTokens: number;
  outputTokens: number;
}

export async function anthropicCompleteText(
  args: AnthropicCompleteTextArgs
): Promise<AnthropicCompleteTextResult> {
  const client = getClient();
  const promptHash = hashPrompt(args.system, args.user);
  const started = Date.now();

  try {
    const response = await client.messages.create({
      model: args.model,
      max_tokens: args.maxTokens ?? 8192,
      ...(args.temperature !== undefined && !shouldOmitTemperature(args.model)
        ? { temperature: args.temperature }
        : {}),
      system: args.system,
      messages: [{ role: 'user', content: args.user }],
    });

    const latencyMs = Date.now() - started;

    const text = response.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim();

    logAiCall({
      ...args,
      provider: 'anthropic',
      promptHash,
      latencyMs,
      inputTokens: response.usage.input_tokens,
      outputTokens: response.usage.output_tokens,
      costUsdCents: claudeCostCents(
        args.model,
        response.usage.input_tokens,
        response.usage.output_tokens
      ),
      success: true,
    });

    logApiUsage(
      buildAnthropicUsage(
        {
          userId: args.userId ?? null,
          practiceId: args.practiceId,
          visitId: args.visitId ?? null,
          metadata: { purpose: args.purpose, latencyMs },
        },
        response.usage.input_tokens,
        response.usage.output_tokens,
        args.model,
        args.purpose
      )
    );

    return {
      text,
      inputTokens: response.usage.input_tokens,
      outputTokens: response.usage.output_tokens,
    };
  } catch (err) {
    // Q2 follow-up — capture the structured Anthropic error body so
    // post-mortems read directly from ai_calls.errorDetails (no worker
    // log scrape required).
    const latencyMs = Date.now() - started;
    logAiCall({
      ...args,
      provider: 'anthropic',
      promptHash,
      latencyMs,
      success: false,
      errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
      errorDetails: anthropicErrorDetailsJson(err),
    });
    throw err;
  }
}
