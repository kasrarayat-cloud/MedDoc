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
  | 'judge'
  | 'eval'
  // T-M4: TranscribeMD 6-layer audio pipeline. Own tags so unit
  // economics per layer are cheap to pivot in SQL.
  | 'tm_transcribe'
  | 'tm_speaker_roles'
  | 'tm_entities'
  | 'tm_soap_draft'
  | 'tm_critique'
  | 'tm_polish'
  // T-M6: parallel automation layers that fan out after polish.
  | 'tm_icd_coding'
  | 'tm_cpt_coding'
  | 'tm_rx_drafting'
  | 'tm_referrals'
  | 'tm_patient_summary';

export interface AiLogContext {
  practiceId: string;
  visitId?: string | null;
  purpose: ModelCallPurpose;
}
