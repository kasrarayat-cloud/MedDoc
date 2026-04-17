// ============================================================================
// Pipeline — Referral letters (M4)
// ----------------------------------------------------------------------------
// One Claude call returns an array of letters (M4 D5). Simpler fan-in,
// one AiCall row per visit.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import {
  ReferralOutputSchema,
  type ReferralOutput,
  type SoapNote,
} from '@meddoc/types';
import { loadPromptFile } from './cleanup-transcript';
import type { PipelineOutcome } from './types';

export interface RunReferralsArgs {
  cleanedText: string;
  soap: SoapNote;
  practiceId: string;
  visitId: string;
}

export async function runDraftReferrals(
  args: RunReferralsArgs
): Promise<PipelineOutcome<ReferralOutput>> {
  const model = process.env.MODEL_FOR_REFERRAL?.trim() || 'claude-sonnet-4-6';
  try {
    const prompt = await loadPromptFile('draft-referrals');
    const user =
      `CLEANED TRANSCRIPT:\n${args.cleanedText}\n\n` +
      `SOAP NOTE:\n${JSON.stringify(args.soap, null, 2)}`;
    const output = await modelClient.complete({
      provider: 'anthropic',
      model,
      system: prompt,
      user,
      schema: ReferralOutputSchema,
      purpose: 'referral',
      practiceId: args.practiceId,
      visitId: args.visitId,
      maxTokens: 4096,
    });
    return { ok: true, output, modelUsed: model };
  } catch (err) {
    const code =
      err instanceof Error && err.message === 'SCHEMA_FAIL'
        ? 'SCHEMA_FAIL'
        : 'PROVIDER_ERROR';
    return {
      ok: false,
      modelUsed: model,
      error: {
        code,
        message: err instanceof Error ? err.message : String(err),
        attempts: 2,
        occurredAt: new Date().toISOString(),
      },
    };
  }
}
