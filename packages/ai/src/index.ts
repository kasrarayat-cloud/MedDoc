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
  CrossProviderFallbackDisabledError,
  type TranscribeArgs,
  type TranscribeResult,
  type TranscribeAudioSource,
  type TranscribeStreamSource,
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
export {
  readAnthropicRequestId,
  readDeepgramRequestId,
  readOpenAIRequestId,
} from './vendor-request-id';
// FIND-P1-006/-007/-008/-009 (2026-05-14) — shared transient-error
// retry helper with full-jitter backoff + Retry-After parsing.
export {
  withRetry,
  defaultIsTransient,
  type RetryOptions,
  type RetryAttemptInfo,
} from './retry';
// FIND-P1-010 (2026-05-14) — typed error for Anthropic JSON.parse fails
// after retry exhaustion. instanceof gate replaces err.message scraping
// in model-client.ts retry loop + worker error-categorize.ts.
export { ModelOutputMalformedError, AnthropicRefusalError } from './errors';
// Round 3 PR-D — deterministic AI safety backstops (audit findings
// A06-P0-002, A06-P0-004). Allowlist + dose-range validators live in
// ./data and are consumed by the worker's 07a/07b/07c layers.
export {
  ICD10_ALLOWLIST,
  ICD10_ALLOWLIST_SIZE,
  ICD10_HEADERS,
  ICD10_HEADERS_SIZE,
  ICD10_EDITION,
  isValidIcd10,
  isIcd10Header,
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
// F-8 (2026-07-02) — deterministic drug-pair interaction floor.
export {
  checkDrugInteractions,
  DRUG_INTERACTION_RULE_COUNT,
  type InteractionMed,
  type InteractionWarning,
} from './data/drug-interactions';
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
// B4 step 3 — the mock seam, exported for the ONE production path that cannot
// go through `modelClient`. `llm-mdm.ts` builds its own Anthropic client to
// attach `cache_control` blocks the shared `CompleteTextArgs.system: string`
// cannot express, so it must read the flag and mark its own usage row. Every
// other caller gets both for free from `anthropic.ts`.
export { isMockEnabled, MOCK_FIXTURE_USAGE } from './mock';
// B4 closing step — the two utterances the mock transcript is built from, and
// the single source the anchored-draft fixture's `⟦A:…⟧` spans are derived
// from. Exported so a gate can build the SAME role-labeled transcript L3 builds
// instead of hardcoding a copy: an anchor only survives `deterministicStage`
// if its span is a literal substring of the transcript, and a copy that drifts
// puts the stage silently back to a zero its own expectation permits.
export { MOCK_TRANSCRIPT_UTTERANCES } from './mock';
// #106(a) — the slot-values sentinels the mocked `tm_soap_draft` speaks.
// ⚠️ EXPORTED SO THE APP CAN PIN THEM AGAINST ITS OWN COPY. `packages/ai`
// cannot import from `apps/transcribe-md`, so the protocol's tokens exist in
// two places; `slot-fill-protocol.test.ts` imports both and asserts equality,
// which turns a silent drift (the mock quietly stops recognising the prompt and
// every slot goes unfilled, indistinguishable from a transcript that said
// nothing) into a failing test.
export {
  MOCK_SLOT_VALUES_OPEN,
  MOCK_SLOT_VALUES_CLOSE,
  MOCK_SYSTEM_COMPOSED_MARKER,
} from './mock';
// B3 — the versioned price table reader, and B6 — the charge rule and the
// prod-only ledger writer.
//
// ⚠️ THESE ARE EXPORTED HERE FOR A REASON THAT IS NOT CONVENIENCE: WITHOUT IT
// NEITHER FILE IS TYPE-CHECKED AT ALL. `tsc` walks the import graph from the
// app's entry points, so a module that nothing in the app imports is simply not
// in the programme — and both of these were in exactly that position. Measured,
// not assumed: `tsc --listFiles` did not name either file, and a deliberately
// bogus Prisma field added to `commitVisitCharge`'s `create({ data })` produced
// ZERO errors. The gate tests import them, but vitest is not a type-checker.
//
// That is the AGENTS.md rule arriving in a new costume — "type-check is
// decisive only for TYPED sites" — where the site is fully typed and merely
// unreachable. A green `tsc` over a programme that does not contain your file
// is the emptiness failure, and it looks exactly like a clean build.
export {
  BILLABLE_PROVIDERS,
  commitVisitCharge,
  componentsOf,
  deliveryModeFor,
  priceUsageRows,
  visitChargeKey,
  type ChargeableUsageRow,
  type ChargeDecision,
  type CommitResult,
  type DeclinedChargeDecision,
  type PricedComponent,
  type UnpricedComponent,
} from './billing-charge';
export {
  decideAdmission,
  readPracticeBalance,
  type AdmissionDecision,
  type AdmissionRefusal,
  type BalanceQueryClient,
  type BalanceRead,
  type BalanceUnreadable,
} from './billing-balance';
// B7 step 3a — the draw order, and everything derived from it. Exported from
// the file that DEFINES them rather than through `billing-balance`'s
// compatibility re-export, so a reader following the import lands on the header
// that explains why the order is what it is.
export {
  DRAW_ORDER,
  LEDGER_BUCKETS,
  SPENDABLE_BUCKETS,
  splitCharge,
  type BucketDraw,
  type LedgerBucket,
} from './billing-buckets';
// B7 step 3b — the promo grant writer. It ships UNWIRED (ruling 90(e)'s
// precedent) and is exported anyway, because the two call sites step 3c takes
// live in another package (`auth.ts`) and in a script — so an unexported writer
// would make step 3c a bigger diff than the decision it executes.
export {
  grantPromoCredit,
  promoGrantKey,
  PROMO_GRANT_MICRO_USD,
  type GrantResult,
} from './billing-grant';
// B8 step 2 — the pipeline seam. The same reason as the block above applies
// with more force: `billing-usage-source.ts` is the file whose whole job is a
// column-name mapping (`timestamp` → `createdAt`), and that is precisely the
// class of defect `tsc` catches and nothing else does — but only if the file is
// in the programme at all.
export {
  admitVisitOrThrow,
  billingEnforced,
  chargeVisitUsage,
  BillingAdmissionError,
  BILLING_ENFORCED_ENV,
  type ChargeOutcome,
} from './billing-pipeline';
export { loadVisitChargeableUsage } from './billing-usage-source';
// B8 step 3 — the failure path. ⚠️ THIS MODULE CHARGES NOTHING, deliberately and
// by construction; it prices what a failed visit consumed and classifies whose
// fault it was. Exported here for the same reason as the block above — a file
// outside the programme is a file `tsc` never checks against its callers.
export {
  classifyFailureAccountability,
  observeFailedVisitUsage,
  type FailureAccountability,
  type FailedVisitObservation,
  type WorkerErrorCategory,
} from './billing-failure';
export { drainApiUsage, pendingApiUsageWrites } from './api-usage';
export {
  chargeMicroUsd,
  costMicroUsd,
  divRoundHalfUp,
  rateAt,
  selectRate,
  tokens,
  UNIT_QUANTITY,
  type AnyUnitType,
  type DeliveryMode,
  type PriceProvenance,
  type PriceProvider,
  type PriceRateRow,
  type PriceUnitType,
  type Quantity,
} from './price-table';
