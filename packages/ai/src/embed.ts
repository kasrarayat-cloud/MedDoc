// ============================================================================
// @meddoc/ai — OpenAI text embedding backend (T-M14.1)
// ----------------------------------------------------------------------------
// One-shot embedText() for the per-doctor edit-capture hook. Separate
// from anthropicComplete / anthropicCompleteText because:
//   - Different provider (openai), different SDK, different cost math.
//   - No retry / no schema validation — embeddings are deterministic
//     vectors, either we got one or we didn't.
//   - Text-embedding-3-small is priced per input token; the pricing
//     helper lives in pricing.ts under openaiEmbedSmall* names.
//
// MOCK_AI_CALLS contract matches modelClient.complete() —
// short-circuits to packages/ai/src/mock.ts so Playwright E2E runs
// never touch OpenAI. See mock.ts for the fixture vector.
// ============================================================================

import OpenAI from 'openai';

import { logAiCall } from './log';
import { readOpenAIRequestId } from './vendor-request-id';
import { isMockEnabled, mockEmbedResponse } from './mock';
import { openaiEmbedSmallCostCents } from './pricing';
import { hashPrompt } from './prompt-hash';
import type { AiLogContext } from './types';
import { logApiUsage, buildOpenAIEmbedUsage } from './api-usage';

/** Dimension of text-embedding-3-small. Must match vector(1536) in
 *  the doctor_edit_patterns.embedding column. Changing the model
 *  means an ALTER TABLE + a backfill — not a silent swap. */
export const EMBED_DIMENSION = 1536;

/** Default model. Env-overridable for experimentation, but any swap
 *  to a different-dimension model requires a schema change (see
 *  EMBED_DIMENSION comment). */
const DEFAULT_EMBED_MODEL = 'text-embedding-3-small';

function embedModel(): string {
  return process.env.OPENAI_EMBED_MODEL || DEFAULT_EMBED_MODEL;
}

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

export interface EmbedTextArgs extends AiLogContext {
  /** Text to embed. Caller is responsible for truncation — at 8K token
   *  limits for the small model, a full SOAP note fits comfortably. */
  text: string;
}

export interface EmbedTextResult {
  /** Embedding vector. Length === EMBED_DIMENSION. */
  embedding: number[];
  inputTokens: number;
  costCents: number;
}

/** Embed one string, log an AiCall row, return the vector + usage.
 *  Caller inserts the vector into doctor_edit_patterns.embedding via
 *  raw SQL (Prisma's Unsupported() field doesn't round-trip natively). */
export async function embedText(args: EmbedTextArgs): Promise<EmbedTextResult> {
  // ── B4 — THE MOCK BOUNDARY MOVES BELOW THE METER, as it did for
  // `anthropic.ts` in B0-a and for `deepgram-batch.ts` in this same change.
  //
  // This used to `return mockEmbed({ purpose })` right here — above the two
  // `logApiUsage` calls below — so a mocked run emitted NO usage row for
  // `tm_embed`. That was not a suspicion: `gate-mock-suite-stubs-the-db.test.ts`
  // carried it as a written EXEMPTION ("the meter is never reached"), which is
  // this defect recorded accurately and lived with.
  //
  // Now the fixture supplies the RESPONSE and the dimension check, the vendor-id
  // read and the meter all run for real. `logAiCall` still suppresses itself
  // under mock (log.ts:66), so `ai_calls` stays real-vendor-only per ruling 66;
  // `unitsSource: 'mock'` is what marks the usage row.
  const mocked = isMockEnabled();
  const model = embedModel();
  // Hash the embed input the same way prompt hashing does for other
  // AiCall rows — keeps the promptHash column meaningful across call
  // types. System is empty; the "prompt" is just the raw text.
  const promptHash = hashPrompt('', args.text);
  const started = Date.now();

  try {
    // `getClient()` throws without OPENAI_API_KEY, so it stays INSIDE the
    // non-mock arm: a mocked run must not require a vendor credential.
    const response = mocked
      ? mockEmbedResponse(args.purpose)
      : await getClient().embeddings.create({
          model,
          input: args.text,
          // Explicit dimensions — safe when the model supports it (small
          // defaults to 1536 anyway, but pinning avoids surprises if the
          // default ever changes upstream).
          dimensions: EMBED_DIMENSION,
        });

    const latencyMs = Date.now() - started;
    const inputTokens = response.usage.total_tokens;
    const costCents = openaiEmbedSmallCostCents(inputTokens);

    const embedding = response.data[0]?.embedding;
    if (!embedding || embedding.length !== EMBED_DIMENSION) {
      logAiCall({
        ...args,
        provider: 'openai',
        model,
        promptHash,
        latencyMs,
        inputTokens,
        outputTokens: 0,
        costUsdCents: costCents,
        success: false,
        errorCode: 'EMBED_DIM_MISMATCH',
        // B1-b step 1. ⚠️ `success: false`, and it STILL carries a vendor id —
        // deliberately. The vendor call SUCCEEDED here; we rejected its payload
        // for the wrong dimension count. The id exists, we were billed for it,
        // and dropping it because our own column says `false` would discard a
        // real correlation id for a call that really happened.
        requestId: readOpenAIRequestId(response),
      });
      // ── B2 — AND THE DURABLE ROW, FOR THE REASON THE COMMENT ABOVE ALREADY
      // GIVES. This is the clearest case in the whole enumeration: OpenAI ran
      // the embedding, counted `response.usage.total_tokens`, returned an id
      // and will invoice it. Our own dimension check is what failed. Before B2
      // the tokens reached `ai_calls` and the meter never saw them.
      logApiUsage(
        buildOpenAIEmbedUsage(
          {
            // B4: `vendor` only when a vendor was actually called.
            unitsSource: mocked ? 'mock' : 'vendor',
            userId: args.userId ?? null,
            practiceId: args.practiceId,
            visitId: args.visitId ?? null,
            requestId: readOpenAIRequestId(response),
            metadata: {
              purpose: args.purpose,
              latencyMs,
              outcome: 'failed',
              errorCode: 'EMBED_DIM_MISMATCH',
            },
          },
          inputTokens,
          model
        )
      );
      throw new Error(
        `OpenAI embedding returned ${embedding?.length ?? 0} dims, expected ${EMBED_DIMENSION}.`
      );
    }

    logAiCall({
      ...args,
      provider: 'openai',
      model,
      promptHash,
      latencyMs,
      inputTokens,
      outputTokens: 0,
      costUsdCents: costCents,
      success: true,
      // B1-b step 1 — `tm_embed`, one of the three callers B1-a's gate did not
      // watch. OpenAI, not Anthropic; see readOpenAIRequestId's header.
      requestId: readOpenAIRequestId(response),
    });

    logApiUsage(
      buildOpenAIEmbedUsage(
        {
          // B0 / B4: a real vendor call says `vendor`; a mocked one says so.
          unitsSource: mocked ? 'mock' : 'vendor',
          userId: args.userId ?? null,
          practiceId: args.practiceId,
          visitId: args.visitId ?? null,
          // B1-b step 2 — the SAME id this call's `logAiCall` above records.
          // Step 1 threaded it into `ai_calls` and declared `api_usage_events`
          // out of scope, so until now this row minted a UUID instead: one real
          // call, two tables, two different "correlation ids", exactly one of
          // them real. Passed straight through — `| null` is the honest value
          // when OpenAI sends no `x-request-id`.
          requestId: readOpenAIRequestId(response),
          metadata: { purpose: args.purpose, latencyMs },
        },
        inputTokens,
        model
      )
    );

    return { embedding, inputTokens, costCents };
  } catch (err) {
    const latencyMs = Date.now() - started;
    // EMBED_DIM_MISMATCH already logged above. Any other error (network,
    // 429, auth) gets a row here.
    //
    // ── B2 — NO USAGE ROW HERE. The SDK threw, so no `response` exists and
    // OpenAI reported no tokens. `response.usage.total_tokens` is the only
    // source of units on this path and it is unreachable; a row could only
    // carry invented zeroes, which would read as "the vendor reported zero".
    // Declared by file and count in B2's gate, not waived.
    if (!(err instanceof Error) || err.message.indexOf('expected ' + EMBED_DIMENSION) === -1) {
      logAiCall({
        ...args,
        provider: 'openai',
        model,
        promptHash,
        latencyMs,
        success: false,
        errorCode: err instanceof Error ? err.name.toUpperCase() : 'UNKNOWN',
      });
    }
    throw err;
  }
}
