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
import { claudeSonnet46CostCents } from './pricing';
import type { AiLogContext } from './types';

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

export interface AnthropicCompleteArgs<T> extends AiLogContext {
  model: string;
  system: string;
  user: string;
  schema: z.ZodType<T>;
  maxTokens?: number;
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
        costUsdCents: claudeSonnet46CostCents(
          response.usage.input_tokens,
          response.usage.output_tokens
        ),
        success: false,
        errorCode: 'JSON_PARSE_FAIL',
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
        costUsdCents: claudeSonnet46CostCents(
          response.usage.input_tokens,
          response.usage.output_tokens
        ),
        success: false,
        errorCode: 'SCHEMA_FAIL',
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
      costUsdCents: claudeSonnet46CostCents(
        response.usage.input_tokens,
        response.usage.output_tokens
      ),
      success: true,
    });

    return schemaResult.data;
  } catch (err) {
    // Re-throw after logging — schema fails and JSON parse fails already
    // logged themselves above, so this catches network / 429 / auth errors.
    const latencyMs = Date.now() - started;
    if (!(err instanceof Error) || (err.message !== 'SCHEMA_FAIL' && !err.message.startsWith('Anthropic response'))) {
      logAiCall({
        ...args,
        provider: 'anthropic',
        promptHash,
        latencyMs,
        success: false,
        errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
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
      costUsdCents: claudeSonnet46CostCents(
        response.usage.input_tokens,
        response.usage.output_tokens
      ),
      success: true,
    });

    return {
      text,
      inputTokens: response.usage.input_tokens,
      outputTokens: response.usage.output_tokens,
    };
  } catch (err) {
    const latencyMs = Date.now() - started;
    logAiCall({
      ...args,
      provider: 'anthropic',
      promptHash,
      latencyMs,
      success: false,
      errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
    });
    throw err;
  }
}
