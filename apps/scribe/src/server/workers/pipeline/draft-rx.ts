// ============================================================================
// Pipeline — Prescription draft (M4)
// ----------------------------------------------------------------------------
// Fetches patient clinical safety (active meds + allergies) from the
// MedDoc Pro internal API and hands it to Claude alongside the cleaned
// transcript + SOAP. The generator is instructed to emit safety
// `warnings[]` on each Rx draft (interaction / allergy / duplicate /
// controlled) per spec §11 + M4 D4.
//
// Returns a PipelineOutcome so the orchestrator can Promise.allSettled
// this alongside coding / referrals / patient-summary.
// ============================================================================

import { modelClient } from '@meddoc/ai';
import { RxOutputSchema, type RxOutput, type SoapNote } from '@meddoc/types';
import { fetchClinicalSafety } from '@/lib/meddoc-client';
import { loadPromptFile } from './cleanup-transcript';
import type { PipelineOutcome } from './types';

export interface RunRxArgs {
  cleanedText: string;
  soap: SoapNote;
  patientId: string;
  practiceId: string;
  visitId: string;
}

export async function runDraftRx(args: RunRxArgs): Promise<PipelineOutcome<RxOutput>> {
  const model = process.env.MODEL_FOR_RX?.trim() || 'claude-sonnet-4-6';
  try {
    // If the safety-API call itself fails we surface that as a
    // PROVIDER_ERROR — we intentionally do NOT proceed to Claude without
    // the meds/allergies list, because the warnings check would be a lie.
    const safety = await fetchClinicalSafety(args.patientId);
    const prompt = await loadPromptFile('draft-rx');
    const user =
      `CLEANED TRANSCRIPT:\n${args.cleanedText}\n\n` +
      `SOAP NOTE:\n${JSON.stringify(args.soap, null, 2)}\n\n` +
      `PATIENT CLINICAL SAFETY:\n${JSON.stringify(
        { medications: safety.medications, allergies: safety.allergies },
        null,
        2
      )}`;
    const output = await modelClient.complete({
      provider: 'anthropic',
      model,
      system: prompt,
      user,
      schema: RxOutputSchema,
      purpose: 'rx',
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
