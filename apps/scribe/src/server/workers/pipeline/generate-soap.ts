// ============================================================================
// Pipeline — Pass 2: SOAP note generation
// ----------------------------------------------------------------------------
// Extracted from the M2/M3 monolithic finalize-visit.ts. Feeds the
// cleaned diarized transcript + the specialty template into Claude,
// returns a SoapNote validated against SoapNoteSchema. Throws on final
// failure — SOAP is the anchor for every M4 downstream extraction, so
// its failure fails the whole job (visit → ERROR).
// ============================================================================

import { modelClient } from '@meddoc/ai';
import { SoapNoteSchema, type SoapNote } from '@meddoc/types';
import { loadPromptFile } from './cleanup-transcript';

export interface RunSoapArgs {
  cleanedText: string;
  specialtySystemPrompt: string;
  specialtySoapSchema: unknown;
  specialtyRequiredExamElements: unknown;
  practiceId: string;
  visitId: string;
}

export interface RunSoapResult {
  soap: SoapNote;
  model: string;
}

export async function runGenerateSoap(args: RunSoapArgs): Promise<RunSoapResult> {
  const prompt = await loadPromptFile('generate-soap');
  const model = process.env.MODEL_FOR_SOAP?.trim() || 'claude-sonnet-4-6';

  const soap = await modelClient.complete({
    provider: 'anthropic',
    model,
    system:
      `${prompt}\n\n---\nSPECIALTY-SPECIFIC GUIDANCE:\n${args.specialtySystemPrompt}\n\n` +
      `SPECIALTY SOAP SCHEMA:\n${JSON.stringify(args.specialtySoapSchema, null, 2)}\n\n` +
      `REQUIRED EXAM ELEMENTS:\n${JSON.stringify(args.specialtyRequiredExamElements)}`,
    user: args.cleanedText,
    schema: SoapNoteSchema,
    purpose: 'soap',
    practiceId: args.practiceId,
    visitId: args.visitId,
    maxTokens: 4096,
  });

  return { soap, model };
}
