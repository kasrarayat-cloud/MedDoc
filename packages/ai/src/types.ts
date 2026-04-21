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
  | 'tm_patient_summary'
  // T-M24: custom-SOAP template fill (opt-in; gated on visit.templateId).
  | 'tm_template_fill'
  // T-M14.1: OpenAI text-embedding-3-small for per-doctor edit
  // pattern capture at sign time. One call per signed visit.
  | 'tm_embed';

export interface AiLogContext {
  practiceId: string;
  visitId?: string | null;
  purpose: ModelCallPurpose;
}
