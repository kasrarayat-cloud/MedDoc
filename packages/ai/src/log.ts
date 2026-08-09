// ============================================================================
// @meddoc/ai — AiCall logger
// ----------------------------------------------------------------------------
// Fire-and-forget writes to the AiCall table. A failed log must never
// block the caller — metrics failing is not worse than the caller
// failing. We do log to console.error so ops sees a DB outage.
//
// ⚠️ `ai_calls` IS A REAL-VENDOR-CALLS-ONLY TABLE. RULED 2026-08-08 (B0 Q1).
//
//     A ROW HERE MEANS A REAL VENDOR WAS CALLED.
//     MOCK RUNS WRITE NOTHING, BY DESIGN.
//
// B0 moved the mock boundary down to the vendor call so that METERING
// (`api_usage_events`) happens under mock — that is what makes B1/B4 gateable.
// This table deliberately did NOT follow. One discriminator, on one table:
// `api_usage_events.unitsSource`. Adding a second here would mean two
// provenance concepts to keep consistent, which is the shape that rots.
//
// ⚠️ THE SUPPRESSION LIVES HERE, ON THE WRITER, NOT ON ITS CALLERS.
// `anthropic.ts` alone has TEN call sites, and `llm-mdm.ts` has another. A
// per-caller `if (!isMockEnabled())` would be a hand-kept list, and hand-kept
// lists are wrong eventually — the R3.4 lesson: put the behaviour where it
// cannot be forgotten, so every present AND FUTURE caller inherits it.
// ============================================================================

import prisma from '@meddoc/db';
import { isMockEnabled } from './mock';
import type { AiLogContext, ModelProvider } from './types';

export interface AiCallLogInput extends AiLogContext {
  provider: ModelProvider;
  model: string;
  promptHash: string;
  latencyMs: number;
  inputTokens?: number | null;
  outputTokens?: number | null;
  /** Anthropic prompt-caching: cache_read_input_tokens from the SDK
   *  response.usage. Stored to credit the 0.10x rate at cost time. */
  cacheReadInputTokens?: number | null;
  /** Anthropic prompt-caching: cache_creation_input_tokens. Billed at
   *  1.25x (5-min) or 2x (1-hour). Today everything we write uses
   *  ephemeral so the 1.25x multiplier applies. */
  cacheCreationInputTokens?: number | null;
  costUsdCents?: number | null;
  success: boolean;
  errorCode?: string | null;
  /** T-M17.1: raw model response body on failed calls, capped upstream. */
  errorDetails?: string | null;
  /**
   * B1-a — the VENDOR's own correlation id, verbatim, or null/undefined when
   * the vendor did not supply one.
   *
   * ⚠️ NEVER pass a `randomUUID()` here. This table is real-vendor-only, so a
   * non-null value is read as "the vendor said this". An absent id is recorded
   * as NULL on purpose — see the schema comment on `AiCall.requestId`.
   *
   * Read it with `readAnthropicRequestId` / `readDeepgramRequestId`; Anthropic's
   * is non-enumerable and any spread of the response silently loses it.
   */
  requestId?: string | null;
}

export function logAiCall(input: AiCallLogInput): void {
  // See the header: a row here asserts a real vendor was called. Under mock no
  // vendor was called, so there is nothing truthful to write.
  if (isMockEnabled()) return;
  void prisma.aiCall
    .create({
      data: {
        practiceId: input.practiceId,
        visitId: input.visitId ?? null,
        purpose: input.purpose,
        provider: input.provider,
        model: input.model,
        promptHash: input.promptHash,
        latencyMs: input.latencyMs,
        inputTokens: input.inputTokens ?? null,
        outputTokens: input.outputTokens ?? null,
        cacheReadInputTokens: input.cacheReadInputTokens ?? 0,
        cacheCreationInputTokens: input.cacheCreationInputTokens ?? 0,
        costUsdCents: input.costUsdCents ?? null,
        success: input.success,
        errorCode: input.errorCode ?? null,
        errorDetails: input.errorDetails ?? null,
        // No fabricated fallback. `?? randomUUID()` here would make an absent
        // vendor id indistinguishable from a real one for every future reader.
        requestId: input.requestId ?? null,
      },
    })
    .catch((err: unknown) => {
      console.error('[ai] AiCall write failed:', err);
    });
}

// ----------------------------------------------------------------------------
// PHI scrubber for log lines
// ----------------------------------------------------------------------------
// Spec §13: "No PHI in logs, Sentry, or analytics." Most of the AI
// surface already honours this (AiCall carries only metadata + prompt
// hash). M3 adds Deepgram error paths where raw messages may contain
// transcript text — redactPhi() is the defense-in-depth used on those
// paths before console.error / log writes.
//
// Not a full clinical-NER pass — that's M7. Approach is minimal:
//   1. Mask common PII patterns (email / phone / SSN).
//   2. If the resulting string is longer than MAX_WORDS_BEFORE_REDACT
//      words, assume it's free-text transcript content and collapse it
//      to a length marker. Short structured log values are preserved so
//      ops can still debug.
// ----------------------------------------------------------------------------

const EMAIL_RE = /\b[\w.+-]+@[\w-]+\.[\w.-]+\b/g;
// No leading \b so an opening paren like "(415) 555-0142" is covered.
// Minimum 10 total digits once separators are stripped — covers US 10-digit
// numbers, international +E.164, and the SSN-without-dashes edge case
// already handled by SSN_RE before this runs.
const PHONE_RE = /\(?\+?\d[\d \-()]{8,}\d/g;
const SSN_RE = /\b\d{3}-?\d{2}-?\d{4}\b/g;
const MAX_WORDS_BEFORE_REDACT = 20;

export function redactPhi(input: unknown): string {
  if (input === null || input === undefined) return String(input);
  let s = typeof input === 'string' ? input : JSON.stringify(input);
  s = s.replace(EMAIL_RE, '[EMAIL]');
  // SSN before PHONE — the phone regex is loose enough that a dashed SSN
  // like "123-45-6789" would otherwise match PHONE first and never get
  // the SSN label.
  s = s.replace(SSN_RE, '[SSN]');
  s = s.replace(PHONE_RE, '[PHONE]');
  const words = s.trim().split(/\s+/).filter(Boolean);
  if (words.length > MAX_WORDS_BEFORE_REDACT) {
    return `[REDACTED:${words.length}w]`;
  }
  return s;
}
