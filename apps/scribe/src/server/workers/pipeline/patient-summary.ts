// ============================================================================
// Pipeline — Patient-facing summary (M4)
// ----------------------------------------------------------------------------
// 6th-grade reading target. Client-side Flesch-Kincaid check in the
// review UI (user-added M4 addition) scores the concatenated body after
// any edits. Server-side, we trust the prompt's reading-level rule and
// let the LLM-as-judge eval verify.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import {
  PatientSummarySchema,
  type PatientSummary,
  type SoapNote,
} from '@meddoc/types';
import { loadPromptFile } from './cleanup-transcript';
import type { PipelineOutcome } from './types';

export interface RunPatientSummaryArgs {
  cleanedText: string;
  soap: SoapNote;
  practiceId: string;
  visitId: string;
}

export async function runPatientSummary(
  args: RunPatientSummaryArgs
): Promise<PipelineOutcome<PatientSummary>> {
  const model = process.env.MODEL_FOR_PATIENT_SUMMARY?.trim() || 'claude-sonnet-4-6';
  try {
    const prompt = await loadPromptFile('patient-summary');
    const user =
      `CLEANED TRANSCRIPT:\n${args.cleanedText}\n\n` +
      `SOAP NOTE:\n${JSON.stringify(args.soap, null, 2)}`;
    const output = await modelClient.complete({
      provider: 'anthropic',
      model,
      system: prompt,
      user,
      schema: PatientSummarySchema,
      purpose: 'summary',
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
