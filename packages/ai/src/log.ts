// ============================================================================
// @meddoc/ai — AiCall logger
// ----------------------------------------------------------------------------
// Fire-and-forget writes to the AiCall table. A failed log must never
// block the caller — metrics failing is not worse than the caller
// failing. We do log to console.error so ops sees a DB outage.
// ============================================================================

import prisma from '@meddoc/db';
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
}

export function logAiCall(input: AiCallLogInput): void {
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
