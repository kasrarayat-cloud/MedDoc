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
  costUsdCents?: number | null;
  success: boolean;
  errorCode?: string | null;
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
        costUsdCents: input.costUsdCents ?? null,
        success: input.success,
        errorCode: input.errorCode ?? null,
      },
    })
    .catch((err: unknown) => {
      console.error('[ai] AiCall write failed:', err);
    });
}
