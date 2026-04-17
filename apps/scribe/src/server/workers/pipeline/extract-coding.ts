// ============================================================================
// Pipeline — ICD-10 + CPT extraction (M4)
// ----------------------------------------------------------------------------
// Runs post-SOAP in the finalize-visit parallel fan-out. Returns a
// PipelineOutcome (never throws to the orchestrator) so one extraction
// failing doesn't block the others — per M4 D1.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import { CodingOutputSchema, type CodingOutput, type SoapNote } from '@meddoc/types';
import { loadPromptFile } from './cleanup-transcript';
import type { PipelineOutcome } from './types';

export interface RunCodingArgs {
  cleanedText: string;
  soap: SoapNote;
  specialtyDefaultIcd10Hints: string[];
  /** M5 D1 — optional; callers not yet updated default to []. */
  specialtyDefaultCptHints?: string[];
  practiceId: string;
  visitId: string;
}

export async function runExtractCoding(
  args: RunCodingArgs
): Promise<PipelineOutcome<CodingOutput>> {
  const model = process.env.MODEL_FOR_CODING?.trim() || 'claude-sonnet-4-6';
  try {
    const prompt = await loadPromptFile('extract-coding');
    const user =
      `CLEANED TRANSCRIPT:\n${args.cleanedText}\n\n` +
      `SOAP NOTE:\n${JSON.stringify(args.soap, null, 2)}\n\n` +
      `SPECIALTY ICD-10 HINTS:\n${JSON.stringify(args.specialtyDefaultIcd10Hints)}\n\n` +
      `SPECIALTY CPT HINTS:\n${JSON.stringify(args.specialtyDefaultCptHints ?? [])}`;
    const output = await modelClient.complete({
      provider: 'anthropic',
      model,
      system: prompt,
      user,
      schema: CodingOutputSchema,
      purpose: 'coding',
      practiceId: args.practiceId,
      visitId: args.visitId,
      maxTokens: 3000,
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
