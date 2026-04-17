// ============================================================================
// @meddoc/ai — shared types
// ============================================================================

export type ModelProvider = 'openai' | 'anthropic' | 'deepgram';

/**
 * Semantic tag on every AiCall row. Matches the set named in spec §11 +
 * a few extras for observability.
 */
export type ModelCallPurpose =
  | 'transcribe_batch'
  | 'transcribe_realtime'
  | 'cleanup'
  | 'soap'
  | 'coding'
  | 'rx'
  | 'referral'
  | 'summary'
  | 'eval';

export interface AiLogContext {
  practiceId: string;
  visitId?: string | null;
  purpose: ModelCallPurpose;
}
