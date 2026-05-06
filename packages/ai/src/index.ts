// ============================================================================
// @meddoc/ai — shared AI model client for the MedDoc monorepo
// ----------------------------------------------------------------------------
// Scoped per the M1 plan decision: Anthropic SDK lives HERE only, not in
// apps/meddoc-pro. apps/scribe is the only consumer in M2. apps/meddoc-pro
// continues to call OpenAI directly from src/lib/ai-service.ts for Doc
// Editor + Clinical Notes.
// ============================================================================

export * from './types';
export * from './model-client';
export * from './deepgram-batch';
export {
  whisperBatchTranscribe,
  isPermanent4xxError,
  WHISPER_MAX_BYTES,
  DEFAULT_WHISPER_MODEL,
  __setOpenAIClientForTests,
  type WhisperBatchArgs,
  type WhisperBatchResult,
  type WhisperSegment,
} from './whisper-batch';
export {
  transcribe,
  type TranscribeArgs,
  type TranscribeResult,
  type TranscriptionProvider,
} from './transcribe';
export {
  EMBED_DIMENSION,
  embedText,
  type EmbedTextArgs,
  type EmbedTextResult,
} from './embed';
export {
  claudeSonnet46CostCents,
  claudeOpus47CostCents,
  claudeCostCents,
  deepgramBatchCostCents,
  sonnetInputCentsPerM,
  sonnetOutputCentsPerM,
  opusInputCentsPerM,
  opusOutputCentsPerM,
  deepgramCentsPerMin,
  openaiEmbedSmallCentsPerM,
  openaiEmbedSmallCostCents,
} from './pricing';
export { hashPrompt } from './prompt-hash';
export { logAiCall, redactPhi } from './log';
// Round 3 PR-D — deterministic AI safety backstops (audit findings
// A06-P0-002, A06-P0-004). Allowlist + dose-range validators live in
// ./data and are consumed by the worker's 07a/07b/07c layers.
export {
  ICD10_ALLOWLIST,
  ICD10_ALLOWLIST_SIZE,
  isValidIcd10,
} from './data/icd10-allowlist';
export {
  CPT_ALLOWLIST,
  CPT_ALLOWLIST_SIZE,
  isValidCpt,
} from './data/cpt-allowlist';
export {
  DOSE_RANGES,
  DOSE_RANGE_TABLE_SIZE,
  getDoseRange,
  isInDoseRangeTable,
  type DoseRangeEntry,
} from './data/dose-ranges';
export {
  validateRxDose,
  type RxValidationResult,
  type RxValidationWarning,
} from './data/dose-ranges-validator';
// Round 3 PR-J — prompt-injection delimiter helpers (audit finding A07-P0).
export {
  wrapAsData,
  delimiterSystemSuffix,
  type WrapAsDataResult,
} from './prompt-delimiters';
// Phase 6 — per-call usage events (separate table from ai_calls; this
// one carries the cost rollups for the admin usage dashboard).
export {
  PRICING,
  logApiUsage,
  buildDeepgramUsage,
  buildWhisperUsage,
  buildAnthropicUsage,
  buildOpenAIEmbedUsage,
  buildResendUsage,
  type Provider as ApiUsageProvider,
  type UsageEvent as ApiUsageEvent,
} from './api-usage';
