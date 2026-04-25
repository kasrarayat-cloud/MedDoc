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
  EMBED_DIMENSION,
  embedText,
  type EmbedTextArgs,
  type EmbedTextResult,
} from './embed';
export {
  claudeSonnet46CostCents,
  deepgramBatchCostCents,
  sonnetInputCentsPerM,
  sonnetOutputCentsPerM,
  deepgramCentsPerMin,
  openaiEmbedSmallCentsPerM,
  openaiEmbedSmallCostCents,
} from './pricing';
export { hashPrompt } from './prompt-hash';
export { logAiCall, redactPhi } from './log';
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
