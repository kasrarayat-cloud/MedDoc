// ============================================================================
// @meddoc/ai — Anthropic Claude backend
// ----------------------------------------------------------------------------
// Used for transcript cleanup + SOAP generation (M2) and the other
// structured-output pipeline steps (M4+). Models are env-configurable;
// default is claude-sonnet-4-6 per the M2 plan. Never use aliases in
// prod — models are pinned to exact date-stamped IDs via env.
// ============================================================================

import Anthropic from '@anthropic-ai/sdk';
import { z } from 'zod';
import { hashPrompt } from './prompt-hash';
import { logAiCall } from './log';
import { readAnthropicRequestId } from './vendor-request-id';
import { claudeCostCents } from './pricing';
import { ModelOutputMalformedError, AnthropicRefusalError } from './errors';
import type { AiLogContext, ModelCallPurpose } from './types';
import { logApiUsage, buildAnthropicUsage } from './api-usage';
import { isMockEnabled, buildMockMessage } from './mock';

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

/**
 * ⚠️ B0 — THE MOCK BOUNDARY. Mock the VENDOR CALL, never the stage.
 *
 * Every caller below goes through this instead of `client.messages.create`
 * directly. Under `MOCK_AI_CALLS` it returns a fixture-built `Message`; the
 * parsing, validation, `extractUsage` and `logApiUsage` beneath it all run for
 * real, so a mocked QA pipeline EMITS USAGE EVENTS. That is what makes B1 and
 * B4 gateable at all — before B0 a mocked run produced zero events, which is
 * indistinguishable from a broken meter.
 *
 * ⚠️ `client` IS PASSED IN, ALREADY CONSTRUCTED, ON PURPOSE. `getClient()`
 * stays the FIRST statement of both public functions and OUTSIDE their `try` —
 * unchanged by B0. Moving it below this seam would have let a mocked run
 * proceed without `ANTHROPIC_API_KEY`, which sounds convenient and is the
 * two-condition doctrine collapsing to one: the flag stops the call, and the
 * dummy credential is what survives a code path that forgets the flag. It would
 * also have moved a throw from outside the `try` to inside it, turning a
 * fail-closed path fail-open — a production behaviour change smuggled into a QA
 * fix.
 */
async function createMessage(
  client: Anthropic,
  params: Anthropic.Messages.MessageCreateParamsNonStreaming,
  ctx: { purpose: ModelCallPurpose; kind: 'tool' | 'text' | 'completeText'; toolName?: string; user?: string }
): Promise<Anthropic.Messages.Message> {
  if (isMockEnabled()) {
    return buildMockMessage({
      purpose: ctx.purpose,
      kind: ctx.kind,
      toolName: ctx.toolName,
      user: ctx.user,
      model: params.model,
    });
  }
  return client.messages.create(params);
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

/** Normalised view of `response.usage`. The Anthropic SDK returns four
 *  token counts per call; we extract them once at the top of each
 *  request and pass the shape through every log site so cost + cache
 *  attribution stays consistent. `cache_*_input_tokens` are nullable in
 *  the SDK — coalesce to 0 so the dispatcher sees a clean number. */
interface NormalizedUsage {
  inputTokens: number;
  outputTokens: number;
  cacheReadInputTokens: number;
  cacheCreationInputTokens: number;
}
function extractUsage(u: Anthropic.Messages.Usage): NormalizedUsage {
  return {
    inputTokens: u.input_tokens,
    outputTokens: u.output_tokens,
    cacheReadInputTokens: u.cache_read_input_tokens ?? 0,
    cacheCreationInputTokens: u.cache_creation_input_tokens ?? 0,
  };
}

/** Q2 follow-up — Anthropic deprecated `temperature` on the Opus 4
 *  family (4.7 returns 400 invalid_request_error("`temperature` is
 *  deprecated for this model.")). The Mythos-class Fable 5 family does
 *  the same (confirmed 2026-06-10 in the feat/fable5-eval smoke). The
 *  Sonnet + Haiku families still accept it. Strip silently for those
 *  families; pass through for everything else. Layer source files keep
 *  their `temperature: 0.x` lines as documentation of intent — the
 *  library honors the wire contract. */
function shouldOmitTemperature(model: string): boolean {
  return model.startsWith('claude-opus-4') || model.startsWith('claude-fable');
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
  /** 2026-05-13 (cross-input-mode-audit Finding 1 hardening): when set,
   *  use Anthropic's native tool_use feature for structured output
   *  instead of free-form text + JSON.parse. The schema is converted
   *  to JSON Schema via Zod's built-in `z.toJSONSchema()` and forced
   *  via `tool_choice: { type: 'tool', name }`. The tool's `input` is
   *  read directly off the response — there's no JSON to malform.
   *  Eliminates the SCHEMA_FAIL / JSON_PARSE_FAIL class entirely on
   *  this layer.
   *
   *  Backwards-compatible — callers that omit this field keep the
   *  historic free-form-text path. */
  useToolUse?: {
    /** Tool name surfaced to the model. Keep snake_case + short
     *  (the model echoes it in reasoning when the call works). */
    name: string;
    /** One-sentence description of what the tool does. */
    description: string;
  };
}

export async function anthropicComplete<T>(args: AnthropicCompleteArgs<T>): Promise<T> {
  const client = getClient();
  const userContent = args.retryContext
    ? `${args.user}\n\n---\nPrevious attempt was rejected by schema validation:\n${args.retryContext}\n\nReturn ONLY the corrected JSON that passes the schema.`
    : args.user;

  const promptHash = hashPrompt(args.system, userContent);
  const started = Date.now();

  // 2026-05-13 tool_use path (cross-input-mode-audit Finding 1
  // hardening). When the caller opts in, build the request with
  // `tools` + `tool_choice` so the model returns a structured
  // `tool_use` content block. No free-form text → no JSON.parse fail.
  // The model's output is the tool's `input` object, which we still
  // validate with the Zod schema (Anthropic's tool_use is
  // best-effort on schema adherence; defense-in-depth via Zod).
  const useToolUse = args.useToolUse;

  try {
    let parsed: unknown;
    let unfenced: string;
    let usage: ReturnType<typeof extractUsage>;
    let latencyMs: number;
    // B1-a — the vendor's own id for whichever branch actually ran. Declared
    // beside `usage` and set in BOTH branches for the same reason `usage` is:
    // the log sites below are shared, so a value set in only one branch would
    // be silently null for every call that took the other.
    let vendorRequestId: string | null = null;

    if (useToolUse) {
      // Convert Zod → JSON Schema via Zod v4's built-in. Cast through
      // `unknown` because the Anthropic SDK's InputSchema type is
      // narrowly typed (`type: 'object'` literal) while Zod's output
      // is a more general JSONSchema7-ish shape.
      const jsonSchema = z.toJSONSchema(args.schema) as unknown as Anthropic.Messages.Tool.InputSchema;

      const response = await createMessage(
        client,
        {
          model: args.model,
          max_tokens: args.maxTokens ?? 4096,
          ...(args.temperature !== undefined && !shouldOmitTemperature(args.model)
            ? { temperature: args.temperature }
            : {}),
          system: args.system,
          messages: [{ role: 'user', content: userContent }],
          tools: [
            {
              name: useToolUse.name,
              description: useToolUse.description,
              input_schema: jsonSchema,
            },
          ],
          tool_choice: { type: 'tool', name: useToolUse.name },
        },
        { purpose: args.purpose, kind: 'tool', toolName: useToolUse.name, user: userContent }
      );

      latencyMs = Date.now() - started;
      usage = extractUsage(response.usage);
      // Direct property access — `_request_id` is non-enumerable, so it must be
      // read off `response` itself and never off a copy. See vendor-request-id.ts.
      vendorRequestId = readAnthropicRequestId(response);

      // Q1 #09.1: the model declined (content-policy / safety). A refusal
      // is deterministic for the same input — log the token-spending call
      // as AI_REFUSAL and throw a typed PERMANENT error so the retry
      // budget isn't burned. (`stop_reason as string` is a defensive
      // widening kept for SDK forward/backward-compat — harmless.)
      if ((response.stop_reason as string | null) === 'refusal') {
        logAiCall({
          ...args,
          provider: 'anthropic',
          promptHash,
          latencyMs,
          inputTokens: usage.inputTokens,
          outputTokens: usage.outputTokens,
          cacheReadInputTokens: usage.cacheReadInputTokens,
          cacheCreationInputTokens: usage.cacheCreationInputTokens,
          costUsdCents: claudeCostCents(
            args.model,
            usage.inputTokens,
            usage.outputTokens,
            usage.cacheReadInputTokens,
            usage.cacheCreationInputTokens,
          ),
          success: false,
          errorCode: 'AI_REFUSAL',
        });
        throw new AnthropicRefusalError(args.model, args.purpose);
      }

      // Find the tool_use content block. Anthropic guarantees one
      // when `tool_choice: { type: 'tool', name }` is set + the
      // call succeeds; we still defend against the empty case in
      // logs because malformed responses are rare-but-possible.
      const toolBlock = response.content.find(
        (b): b is Anthropic.ToolUseBlock => b.type === 'tool_use',
      );
      if (!toolBlock) {
        unfenced = '(no tool_use block returned)';
        logAiCall({
          ...args,
          provider: 'anthropic',
          promptHash,
          latencyMs,
          inputTokens: usage.inputTokens,
          outputTokens: usage.outputTokens,
          cacheReadInputTokens: usage.cacheReadInputTokens,
          cacheCreationInputTokens: usage.cacheCreationInputTokens,
          costUsdCents: claudeCostCents(
            args.model,
            usage.inputTokens,
            usage.outputTokens,
            usage.cacheReadInputTokens,
            usage.cacheCreationInputTokens,
          ),
          success: false,
          errorCode: 'JSON_PARSE_FAIL',
          errorDetails: capErrorDetails(unfenced),
        });
        throw new Error(
          'Anthropic response was not valid JSON: tool_use block missing',
        );
      }
      parsed = toolBlock.input;
      // Keep `unfenced` populated so the retry-context surface
      // downstream gets a useful payload (the tool input as JSON).
      unfenced = JSON.stringify(parsed);
    } else {
      const response = await createMessage(
        client,
        {
          model: args.model,
          max_tokens: args.maxTokens ?? 4096,
          ...(args.temperature !== undefined && !shouldOmitTemperature(args.model)
            ? { temperature: args.temperature }
            : {}),
          system: args.system,
          messages: [{ role: 'user', content: userContent }],
        },
        { purpose: args.purpose, kind: 'text', user: userContent }
      );

      latencyMs = Date.now() - started;

      // Concatenate all text content blocks. Anthropic responses usually
      // have one block but the API is arrayed.
      const text = response.content
        .filter((b): b is Anthropic.TextBlock => b.type === 'text')
        .map((b) => b.text)
        .join('\n')
        .trim();

      // Claude sometimes wraps JSON in ```json … ``` fences even when told
      // not to. Strip fences before parsing.
      unfenced = text
        .replace(/^```(?:json)?\s*/i, '')
        .replace(/```$/, '')
        .trim();

      usage = extractUsage(response.usage);
      vendorRequestId = readAnthropicRequestId(response);

      // Q1 #09.1: refusal → AI_REFUSAL + PERMANENT (see tool branch above).
      if ((response.stop_reason as string | null) === 'refusal') {
        logAiCall({
          ...args,
          provider: 'anthropic',
          promptHash,
          latencyMs,
          inputTokens: usage.inputTokens,
          outputTokens: usage.outputTokens,
          cacheReadInputTokens: usage.cacheReadInputTokens,
          cacheCreationInputTokens: usage.cacheCreationInputTokens,
          costUsdCents: claudeCostCents(
            args.model,
            usage.inputTokens,
            usage.outputTokens,
            usage.cacheReadInputTokens,
            usage.cacheCreationInputTokens,
          ),
          success: false,
          errorCode: 'AI_REFUSAL',
        });
        throw new AnthropicRefusalError(args.model, args.purpose);
      }

      try {
        parsed = JSON.parse(unfenced);
      } catch (err) {
        logAiCall({
          ...args,
          provider: 'anthropic',
          promptHash,
          latencyMs,
          inputTokens: usage.inputTokens,
          outputTokens: usage.outputTokens,
          cacheReadInputTokens: usage.cacheReadInputTokens,
          cacheCreationInputTokens: usage.cacheCreationInputTokens,
          costUsdCents: claudeCostCents(
            args.model,
            usage.inputTokens,
            usage.outputTokens,
            usage.cacheReadInputTokens,
            usage.cacheCreationInputTokens,
          ),
          success: false,
          errorCode: 'JSON_PARSE_FAIL',
          errorDetails: capErrorDetails(unfenced),
        });
        // FIND-P1-010 (2026-05-14): typed error replaces the prior
        // generic `Error('Anthropic response was not valid JSON: ...')`.
        // The error class carries the truncated body + parseError; the
        // message preserves the legacy "Anthropic response was not valid
        // JSON" prefix so the model-client retry loop (which still does
        // the message-startsWith check as a fallback) keeps working.
        // categorizeError.ts now keys off the class via instanceof for
        // permanent classification.
        throw new ModelOutputMalformedError(unfenced, err);
      }
    }

    const schemaResult = args.schema.safeParse(parsed);
    if (!schemaResult.success) {
      logAiCall({
        ...args,
        provider: 'anthropic',
        promptHash,
        latencyMs,
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        cacheReadInputTokens: usage.cacheReadInputTokens,
        cacheCreationInputTokens: usage.cacheCreationInputTokens,
        costUsdCents: claudeCostCents(
          args.model,
          usage.inputTokens,
          usage.outputTokens,
          usage.cacheReadInputTokens,
          usage.cacheCreationInputTokens,
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
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
      cacheReadInputTokens: usage.cacheReadInputTokens,
      cacheCreationInputTokens: usage.cacheCreationInputTokens,
      costUsdCents: claudeCostCents(
        args.model,
        usage.inputTokens,
        usage.outputTokens,
        usage.cacheReadInputTokens,
        usage.cacheCreationInputTokens,
      ),
      success: true,
      requestId: vendorRequestId,
    });

    logApiUsage(
      buildAnthropicUsage(
        {
          // B0: a REAL vendor call — see UnitsSource.
          // B0: mirrors the seam. Under mock no vendor was called, so the row
          // says so and its money columns are zeroed by the writer.
          unitsSource: isMockEnabled() ? 'mock' : 'vendor',
          userId: args.userId ?? null,
          practiceId: args.practiceId,
          visitId: args.visitId ?? null,
          // B1-a captured it; B1-b step 2 lets it through UNCHANGED. The old
          // `?? undefined` existed only to hand the absent case to the builder's
          // `randomUUID()` fallback — that fallback is gone, so `null` now
          // reaches the column and means what it says: the vendor gave no id.
          requestId: vendorRequestId,
          metadata: { purpose: args.purpose, latencyMs },
        },
        usage.inputTokens,
        usage.outputTokens,
        args.model,
        args.purpose,
        usage.cacheReadInputTokens,
        usage.cacheCreationInputTokens,
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
    // FIND-P1-010: instanceof check supersedes the message-startsWith
    // fallback for ModelOutputMalformedError; the message-prefix branch
    // remains so legacy/in-flight Error throws stay deduped.
    if (
      !(err instanceof Error) ||
      (err.message !== 'SCHEMA_FAIL' &&
        !err.message.startsWith('Anthropic response') &&
        !(err instanceof ModelOutputMalformedError) &&
        // Q1 #09.1 (SF-1): the refusal branch already logged AI_REFUSAL above
        // — don't double-log a spurious ANTHROPICREFUSALERROR row here.
        !(err instanceof AnthropicRefusalError))
    ) {
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
    const response = await createMessage(
      client,
      {
        model: args.model,
        max_tokens: args.maxTokens ?? 8192,
        ...(args.temperature !== undefined && !shouldOmitTemperature(args.model)
          ? { temperature: args.temperature }
          : {}),
        system: args.system,
        messages: [{ role: 'user', content: args.user }],
      },
      { purpose: args.purpose, kind: 'completeText', user: args.user }
    );

    const latencyMs = Date.now() - started;
    // B1-a — read off `response` itself; `_request_id` is non-enumerable and a
    // spread copy silently drops it. See vendor-request-id.ts.
    const vendorRequestId = readAnthropicRequestId(response);

    const text = response.content
      .filter((b): b is Anthropic.TextBlock => b.type === 'text')
      .map((b) => b.text)
      .join('\n')
      .trim();

    const usage = extractUsage(response.usage);

    // Q1 #09.1: refusal → AI_REFUSAL + PERMANENT (completeText path).
    if ((response.stop_reason as string | null) === 'refusal') {
      logAiCall({
        ...args,
        provider: 'anthropic',
        promptHash,
        latencyMs,
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        cacheReadInputTokens: usage.cacheReadInputTokens,
        cacheCreationInputTokens: usage.cacheCreationInputTokens,
        costUsdCents: claudeCostCents(
          args.model,
          usage.inputTokens,
          usage.outputTokens,
          usage.cacheReadInputTokens,
          usage.cacheCreationInputTokens,
        ),
        success: false,
        errorCode: 'AI_REFUSAL',
      });
      throw new AnthropicRefusalError(args.model, args.purpose);
    }

    logAiCall({
      ...args,
      provider: 'anthropic',
      promptHash,
      latencyMs,
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
      cacheReadInputTokens: usage.cacheReadInputTokens,
      cacheCreationInputTokens: usage.cacheCreationInputTokens,
      costUsdCents: claudeCostCents(
        args.model,
        usage.inputTokens,
        usage.outputTokens,
        usage.cacheReadInputTokens,
        usage.cacheCreationInputTokens,
      ),
      success: true,
      requestId: vendorRequestId,
    });

    logApiUsage(
      buildAnthropicUsage(
        {
          // B0: a REAL vendor call — see UnitsSource.
          // B0: mirrors the seam. Under mock no vendor was called, so the row
          // says so and its money columns are zeroed by the writer.
          unitsSource: isMockEnabled() ? 'mock' : 'vendor',
          userId: args.userId ?? null,
          practiceId: args.practiceId,
          visitId: args.visitId ?? null,
          // B1-a captured it; B1-b step 2 lets it through unchanged — see the
          // twin block in anthropicComplete. `null` now reaches the column.
          requestId: vendorRequestId,
          metadata: { purpose: args.purpose, latencyMs },
        },
        usage.inputTokens,
        usage.outputTokens,
        args.model,
        args.purpose,
        usage.cacheReadInputTokens,
        usage.cacheCreationInputTokens,
      )
    );

    return {
      text,
      inputTokens: usage.inputTokens,
      outputTokens: usage.outputTokens,
    };
  } catch (err) {
    // Q2 follow-up — capture the structured Anthropic error body so
    // post-mortems read directly from ai_calls.errorDetails (no worker
    // log scrape required).
    const latencyMs = Date.now() - started;
    // Q1 #09.1 (SF-1): the refusal branch already logged AI_REFUSAL above —
    // don't double-log a spurious ANTHROPICREFUSALERROR row here.
    if (!(err instanceof AnthropicRefusalError)) {
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
