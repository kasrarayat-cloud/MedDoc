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
export * from './deepgram';
export { hashPrompt } from './prompt-hash';
export { logAiCall, redactPhi } from './log';
