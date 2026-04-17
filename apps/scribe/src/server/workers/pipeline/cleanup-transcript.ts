// ============================================================================
// Pipeline — Pass 1: transcript cleanup + diarization
// ----------------------------------------------------------------------------
// Extracted from the M2/M3 monolithic finalize-visit.ts. Same behavior:
// reads raw transcript, asks Claude to re-diarize + fix obvious ASR
// errors, validates against CleanedTranscriptSchema. Throws on final
// failure — cleanup is a hard prerequisite for every downstream step,
// so we don't wrap its failure in a PipelineOutcome.
// ============================================================================

import fs from 'node:fs/promises';
import path from 'node:path';
import { modelClient } from '@meddoc/ai';
import { CleanedTranscriptSchema, type CleanedTranscript } from '@meddoc/types';

const PROMPTS_DIR = path.join(process.cwd(), 'apps', 'scribe', 'src', 'server', 'prompts');

export async function loadPromptFile(
  name:
    | 'cleanup-transcript'
    | 'generate-soap'
    | 'extract-coding'
    | 'draft-rx'
    | 'draft-referrals'
    | 'patient-summary'
    | 'llm-judge'
): Promise<string> {
  const byCwd = path.join(PROMPTS_DIR, `${name}.md`);
  try {
    return await fs.readFile(byCwd, 'utf8');
  } catch {
    const fallback = path.join(__dirname, '..', '..', 'prompts', `${name}.md`);
    return fs.readFile(fallback, 'utf8');
  }
}

export interface RunCleanupArgs {
  rawFullText: string;
  practiceId: string;
  visitId: string;
}

export interface RunCleanupResult {
  cleaned: CleanedTranscript;
  model: string;
}

export async function runCleanupTranscript(
  args: RunCleanupArgs
): Promise<RunCleanupResult> {
  const prompt = await loadPromptFile('cleanup-transcript');
  const model = process.env.MODEL_FOR_CLEANUP?.trim() || 'claude-sonnet-4-6';

  const cleaned = await modelClient.complete({
    provider: 'anthropic',
    model,
    system: prompt,
    user: args.rawFullText,
    schema: CleanedTranscriptSchema,
    purpose: 'cleanup',
    practiceId: args.practiceId,
    visitId: args.visitId,
    maxTokens: 4096,
  });

  return { cleaned, model };
}
