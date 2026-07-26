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
  // L6 post-polish fabrication gate (2026-06-11, RED finding fix) — a
  // focused verifier that diffs the polished note against its input and
  // rejects new clinical claims. Own tag so rejection-path unit
  // economics + call rates are cheap to pivot in SQL.
  | 'tm_polish_gate'
  // Hybrid anchored generation (2026-06-11) — per-claim entailment verifier:
  // judges each anchored claim against its quoted transcript span(s).
  // Fail-closed (uncertain/error → claim demoted to the suggestions lane).
  | 'tm_anchor_entailment'
  // T-M6: parallel automation layers that fan out after polish.
  | 'tm_icd_coding'
  | 'tm_cpt_coding'
  | 'tm_rx_drafting'
  | 'tm_referrals'
  | 'tm_patient_summary'
  // T-M14.1: OpenAI text-embedding-3-small for per-doctor edit
  // pattern capture at sign time. One call per signed visit.
  | 'tm_embed'
  // Note-format customization Phase 2a — bring-your-own-note parse engine.
  // `tm_template_parse` extracts FORMAT/STYLE from a doctor's note;
  // `tm_template_phi_scan` is the separate PHI-detection gate over the
  // parsed output. Stateless — the source note is never persisted.
  | 'tm_template_parse'
  | 'tm_template_phi_scan'
  // Template Twin native-DOCX — PHI gate over physician-supplied SYNTHETIC test
  // evidence at certify time (distinct from tm_template_phi_scan over parsed
  // output). Separate purpose keeps telemetry/cost attribution clean.
  | 'tm_template_synthetic_phi_scan'
  // The pre-sign chat editor. The model NEVER writes: it returns a structured
  // intent, and the server dispatches into the same audited actions the buttons
  // call. Its own purpose so its cost and volume are attributable separately
  // from the generation pipeline.
  | 'tm_chat_edit';

export interface AiLogContext {
  practiceId: string;
  visitId?: string | null;
  purpose: ModelCallPurpose;
  /** Phase 6 — owner of the call for per-user cost rollups. Optional
   *  for back-compat: legacy callers that didn't plumb a user (e.g.,
   *  background sweeps) still type-check. The api_usage_events row
   *  records null `userId` in that case, attributed only by practice. */
  userId?: string | null;
}
