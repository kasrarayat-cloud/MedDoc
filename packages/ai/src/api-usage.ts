// ============================================================================
// API Usage Logger (Phase 6)
// ----------------------------------------------------------------------------
// Records every external-API call (Deepgram / Anthropic / Whisper / OpenAI /
// Resend) with cost calculation. Called from each provider wrapper AFTER
// the call completes — successful or failed (failed calls often still cost
// money: a Deepgram socket that ran for 30s before erroring is still 30s
// of billed audio).
//
// Fire-and-forget pattern (mirrors `lib/audit.ts`): never blocks the
// calling request. A failed log write goes to console.warn and is dropped.
// The `setImmediate` defers past the response flush so a slow Postgres
// write can't extend request latency.
//
// ── Pricing constants ──
// Snapshot of provider pricing at the time of this commit. The TOTAL cost
// is computed at log time and stored on the row (`totalCostUsd`), so
// historical billing rollups always reflect the rate that was charged at
// the time of the call. Update PRICING when the provider changes pricing —
// do NOT back-rewrite historical rows.
// ============================================================================

// ⚠️ `randomUUID` USED TO BE IMPORTED HERE, AND ITS ABSENCE IS THE POINT.
// Every builder below once ended `requestId: ctx.requestId ?? randomUUID()`.
// B1-b step 2 removed all five; if a future edit reaches for a UUID to satisfy
// this column, read {@link UsageEvent.requestId} first — the column is nullable
// precisely so that nothing has to invent a value for it, and the database now
// refuses an invented one on any non-vendor row.

import prisma from '@meddoc/db';

import { claudeCostCents, deepgramCentsPerMin } from './pricing';

// Rates refreshed 2026-05-12 from docs.anthropic.com/en/docs/about-
// claude/pricing. Opus 4.7 was the dominant overcount source: the
// $15/$75 stored here were the Opus 4.x rates; Anthropic cut Opus
// 4.5/4.6/4.7 to $5/$25 (matching their new pricing tier) and we had
// never caught up — every Opus row on the admin dashboard was 3x
// over. Haiku also updated to 4.5 family ($1/$5; was Haiku 3 rates).
export const PRICING = {
  // Deepgram Nova-3 Medical — per minute. Single source of truth lives
  // in pricing.ts (deepgramCentsPerMin()), env-overridable. Mirrored
  // here as a cents-fraction for callers that still read this constant
  // directly; refreshed at module load. Previously this duplicated the
  // value and disagreed with pricing.ts ($0.0043 vs $0.0145) — the
  // Deepgram surface on the dashboard read this value while ai_calls
  // read pricing.ts, producing two non-matching cost rollups. Now both
  // surfaces point at the same number.
  deepgram_nova3_medical: deepgramCentsPerMin() / 100,
  // OpenAI Whisper API — per minute
  whisper: 0.006,
  // Anthropic Sonnet 4.6 — per 1M tokens
  anthropic_sonnet_input: 3.0,
  anthropic_sonnet_output: 15.0,
  // Anthropic Opus 4.7 — per 1M tokens  (was 15 / 75 — STALE; 3x over)
  anthropic_opus_input: 5.0,
  anthropic_opus_output: 25.0,
  // Anthropic Haiku 4.5 — per 1M tokens  (was 0.25 / 1.25 — Haiku 3 rates)
  anthropic_haiku_input: 1.0,
  anthropic_haiku_output: 5.0,
  // Anthropic prompt-caching multipliers
  anthropic_cache_read_multiplier: 0.10,    // 90% discount
  anthropic_cache_write_5min_multiplier: 1.25,
  anthropic_cache_write_1h_multiplier: 2.0,
  // OpenAI text-embedding-3-small — per 1M tokens
  openai_embedding: 0.13,
  // OpenAI GPT-4o — per 1M tokens (kept for completeness; not currently
  // a primary provider on this stack)
  openai_gpt4_input: 2.5,
  openai_gpt4_output: 10.0,
  // Resend transactional — per email
  resend_email: 0.001,
} as const;

export type Provider =
  | 'deepgram'
  | 'anthropic'
  | 'whisper'
  | 'openai'
  | 'resend';

export type UnitType = 'minutes' | 'tokens_in' | 'tokens_out' | 'emails';

/**
 * Where this row's UNITS came from. **RULED 2026-08-08 (B0).**
 *
 * `vendor` — a real vendor was called and reported these numbers.
 * `mock`   — a mocked run. NO vendor was called; the units are fixture-derived
 *            and the money columns are zero, because zero is the TRUE cost.
 *
 * ⚠️ **REQUIRED, WITH NO DEFAULT, ON PURPOSE.** A provenance column whose
 * default is the TRUSTED value is fail-open: every future writer that has never
 * heard of it silently produces a row claiming a real vendor reported these
 * numbers. Making it required means a new writer either states its provenance or
 * fails to compile — which is the only version of this that stays true.
 *
 * ⚠️ **AND IT IS A COLUMN, NOT A `metadata` KEY.** Every rollup and every
 * reconciliation query has to be able to exclude mock rows in a `WHERE`, and a
 * JSON key is exactly the thing a future query author never learns about.
 */
export type UnitsSource = 'vendor' | 'mock';

export interface UsageEvent {
  /** See {@link UnitsSource}. Required — no default, by ruling. */
  unitsSource: UnitsSource;
  userId?: string | null;
  practiceId?: string | null;
  provider: Provider;
  operation: string;
  audioSeconds?: number;
  inputTokens?: number;
  outputTokens?: number;
  /** Anthropic prompt-caching: cache_read_input_tokens (billed 0.10x). */
  cacheReadInputTokens?: number;
  /** Anthropic prompt-caching: cache_creation_input_tokens (billed 1.25x ephemeral). */
  cacheCreationInputTokens?: number;
  emailCount?: number;
  unitCount: number;
  unitType: UnitType;
  unitCostUsd: number;
  totalCostUsd: number;
  visitId?: string | null;
  /**
   * THE VENDOR'S OWN CORRELATION ID for this call, verbatim — or `null`/absent
   * when the vendor did not supply one. **NEVER FABRICATED.**
   *
   * ⚠️ **B1-b step 2 CHANGED THIS FROM `string` TO OPTIONAL, AND THE OLD SHAPE
   * IS WHY.** It used to be required, and every builder satisfied that with
   * `ctx.requestId ?? randomUUID()`. The column was therefore 100% populated
   * and 0% trustworthy — a minted UUID and a real vendor id are the same shape,
   * so one row later nothing could tell them apart. Making it required did not
   * produce ids; it produced *indistinguishable* ids, which is worse than the
   * NULL it was avoiding.
   *
   * The database now agrees: `requestId IS NOT NULL ⇒ unitsSource = 'vendor'`
   * (`api_usage_events_request_id_requires_vendor`).
   */
  requestId?: string | null;
  modelName?: string;
  metadata?: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// ⚠️ B8 step 2 — THE IN-FLIGHT SET, AND WHY A DRAIN IS THE ONLY HONEST FIX
// ---------------------------------------------------------------------------
// `logApiUsage` returns BEFORE its row exists. That is deliberate and stays —
// a slow Postgres write must never extend a doctor's request. The cost is a
// read-after-write race that ruling 90(e) named and assigned to B8 in as many
// words: "a caller that reads `api_usage_events` at pipeline end inherits
// exactly the `worker.ts:983` race... whoever wires this must solve the
// ordering, and cannot do it by accident."
//
// B8 step 2 is that caller. It reads a visit's usage rows to price them, and a
// row still sitting in a `setImmediate` queue is a row it will not see — so the
// visit is charged for less than it consumed. **The failure is SILENT and it is
// always an UNDER-charge**, which is the direction nobody notices: no error, no
// missing visit, just a smaller number in an append-only ledger that can only
// be corrected by an `adjustment` row.
//
// ⚠️ THE FIX IS NOT "AWAIT THE WRITE". Making `logApiUsage` awaitable would put
// a database round-trip in every vendor call's hot path — the exact thing the
// `setImmediate` exists to prevent — and B6's header is explicit that the
// fire-and-forget shape is correct. The fix is to make the pending set
// OBSERVABLE, so one caller that genuinely needs the rows can wait for them
// while every other caller keeps not waiting.
//
// ⚠️ AND A SLEEP WOULD HAVE LOOKED IDENTICAL ON EVERY TEST. `await sleep(50)`
// drains this queue in practice today and is not a guarantee about anything: it
// passes locally, passes in CI, and under-charges on the one loaded night when
// a write takes 60ms. A promise you can await is a fact; a delay you tuned is a
// hope, and the two are indistinguishable from a green suite.
const inFlightUsageWrites = new Set<Promise<void>>();

/**
 * WAIT UNTIL EVERY `logApiUsage` CALL MADE SO FAR HAS FINISHED ITS WRITE.
 *
 * Resolves when the pending set is empty. **Never rejects** — each write
 * already swallows its own error, so a drain reports "nothing is still in
 * flight", never "every write succeeded". Those are different claims and only
 * the first one is available here.
 *
 * ⚠️ THE LOOP IS NOT DEFENSIVE PADDING. `Promise.all` is taken over a SNAPSHOT,
 * so a `logApiUsage` call that lands while the drain is awaiting would not be
 * covered by it. Re-checking until the set is empty closes that, and it is the
 * realistic case rather than a theoretical one: the pipeline's last stage can
 * still be metering when the finalize step begins draining.
 */
export async function drainApiUsage(): Promise<void> {
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const pending = [...inFlightUsageWrites];
    if (pending.length === 0) return;
    await Promise.all(pending);
  }
}

/** How many usage writes have not yet settled. Exported for the gate, which
 *  needs to observe the set being non-empty BEFORE the drain to prove the
 *  drain had something to do — a drain over an empty set proves nothing, and
 *  is exactly what a broken instrument would also report. */
export function pendingApiUsageWrites(): number {
  return inFlightUsageWrites.size;
}

/** Fire-and-forget: schedules the row write via setImmediate so the
 *  caller's promise chain never waits on it. Errors are caught and
 *  logged at warn — the audit story for usage is "best-effort".
 *
 *  ⚠️ Still returns `void` and still does not block. {@link drainApiUsage} is
 *  how a caller that needs the rows waits for them; nothing else changed. */
export function logApiUsage(event: UsageEvent): void {
  // ⚠️ B0 — A MOCK ROW'S MONEY COLUMNS ARE ZERO, AND ZERO IS THE TRUE COST.
  // No vendor was called, so no money was spent. Pricing the fixture units with
  // the real rate "to show what it would have cost" would put a number in
  // `totalCostUsd`, and a number there IS a claim that money was spent.
  //
  // It is enforced HERE, on the writer, not in each builder: five builders
  // exist today and a sixth will not remember. It is also defence in depth —
  // a naive `SUM(totalCostUsd)` written by someone who never heard of
  // `unitsSource` still cannot over-charge.
  //
  // ⚠️ B1-b STEP 2 — AND A MOCK ROW CARRIES NO REQUEST ID, FOR THE SAME REASON.
  // No vendor was called, so no vendor gave us an id, so any value here would
  // be one we invented. The database refuses it outright
  // (`requestId IS NOT NULL ⇒ unitsSource = 'vendor'`) — and because this
  // writer is fire-and-forget, that refusal would be SWALLOWED: the row would
  // simply not exist, no test would fail, and B0-a's guarantee that a mocked
  // run meters would quietly stop being true. Zeroing it here means the writer
  // and the constraint cannot disagree.
  //
  // Enforced HERE rather than in each builder, for the reason directly above:
  // five builders exist today and a sixth will not remember.
  const priced: UsageEvent =
    event.unitsSource === 'mock'
      ? { ...event, unitCostUsd: 0, totalCostUsd: 0, requestId: null }
      : event;
  // The settle promise is registered BEFORE `setImmediate` schedules anything,
  // so there is no window in which a write is pending and the set is empty. A
  // drain that started between the two would otherwise return immediately and
  // report an all-clear over a queue it never saw.
  let markSettled!: () => void;
  const settled = new Promise<void>((resolve) => {
    markSettled = resolve;
  });
  inFlightUsageWrites.add(settled);
  void settled.then(() => inFlightUsageWrites.delete(settled));

  setImmediate(async () => {
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (prisma as any).apiUsageEvent.create({
        data: {
          userId: priced.userId ?? null,
          practiceId: priced.practiceId ?? null,
          provider: priced.provider,
          operation: priced.operation,
          audioSeconds: priced.audioSeconds ?? null,
          inputTokens: priced.inputTokens ?? null,
          outputTokens: priced.outputTokens ?? null,
          cacheReadInputTokens: priced.cacheReadInputTokens ?? 0,
          cacheCreationInputTokens: priced.cacheCreationInputTokens ?? 0,
          emailCount: priced.emailCount ?? null,
          unitCount: priced.unitCount,
          unitType: priced.unitType,
          unitCostUsd: priced.unitCostUsd,
          totalCostUsd: priced.totalCostUsd,
          visitId: priced.visitId ?? null,
          // No `?? randomUUID()`. See {@link UsageEvent.requestId} — a minted
          // id is indistinguishable from a real one afterwards, which is the
          // whole defect B1-b closes.
          requestId: priced.requestId ?? null,
          modelName: priced.modelName ?? null,
          metadata: priced.metadata ?? null,
          // No `?? 'vendor'`. The type makes this required; defaulting it here
          // would reintroduce the fail-open the column exists to prevent.
          unitsSource: priced.unitsSource,
        },
      });
    } catch (err) {
      console.warn(
        '[api-usage] failed to log:',
        err instanceof Error ? err.message : err
      );
    } finally {
      // ⚠️ `finally`, NOT the end of `try`. A write that threw is still a write
      // that is no longer in flight; leaving it registered would make
      // `drainApiUsage` hang forever the first time Postgres refused a row —
      // converting a best-effort meter into a pipeline halt, which is the exact
      // inversion the fire-and-forget shape exists to prevent.
      //
      // ⚠️ AND IT IS REDUNDANT TODAY — SAID PLAINLY, BECAUSE THE MUTATION SAID
      // SO. Moving this call to after the `try/catch` leaves the gate GREEN,
      // because the catch above is broad and `console.warn` does not throw. It
      // goes red only when the catch is removed as well. So `finally` is not
      // what makes the current code correct; it is what keeps it correct the
      // day somebody narrows that catch to a specific error type — a change
      // that would otherwise convert a swallowed warning into a permanently
      // hung pipeline, with nothing failing at the moment of the edit.
      markSettled();
    }
  });
}

// ---------------------------------------------------------------------------
// Builders — one per provider, return a fully-populated UsageEvent. Wrappers
// call `logApiUsage(buildXxx(...))` at the end of their happy/sad path.
// ---------------------------------------------------------------------------

interface BaseCtx {
  userId?: string | null;
  practiceId?: string | null;
  visitId?: string | null;
  /**
   * The vendor's own id, or `null`/absent when it gave none. See
   * {@link UsageEvent.requestId} — NEVER fabricated.
   *
   * `| null` so a caller holding a `string | null` from `readAnthropicRequestId`
   * / `readOpenAIRequestId` can pass it STRAIGHT THROUGH. The older `?? undefined`
   * dance at the call sites existed only to feed the builder's UUID fallback,
   * and that fallback is gone.
   */
  requestId?: string | null;
  metadata?: Record<string, unknown> | null;
  /**
   * ⚠️ REQUIRED on every builder's ctx — see {@link UnitsSource}.
   *
   * It lives on BaseCtx rather than on each builder's argument list so that a
   * NEW builder inherits the obligation instead of having to remember it. A
   * per-builder parameter is a hand-kept list, and hand-kept lists are wrong
   * eventually.
   */
  unitsSource: UnitsSource;
}

/**
 * ⚠️ B4 — `modelName` AND `operation` ARE REQUIRED PARAMETERS, NOT DEFAULTS.
 *
 * Both used to be literals in this function body: every Deepgram row said
 * `nova-3-medical` / `transcribe_realtime` whatever had actually been called.
 * `transcribe_realtime` was the worse of the two — **no streaming call site
 * exists on this stack**, so the label was a literal wearing an observation's
 * clothes (DISCOVERY §C.7, and the B3 seed comment says so in as many words).
 *
 * They are REQUIRED rather than defaulted for the reason ruling 67 gives about
 * provenance defaults: a default is what lets a future caller silently
 * re-assert a fact it never checked. With no default, a new call site cannot
 * compile without naming both.
 *
 * ⚠️ WHAT THIS DOES NOT FIX, STATED SO IT IS NOT MISTAKEN FOR FIXED:
 * `unitCostUsd` / `totalCostUsd` below still price EVERY Deepgram model at
 * `PRICING.deepgram_nova3_medical`. So a row can now name `nova-3` honestly and
 * still be priced at the medical rate. Wiring these to B3's `price_rates` — and
 * deciding what a `null` rate means at the meter — is B4/B6's, per ruling 80(c).
 * The label fix does not touch the money, and does not claim to.
 */
export function buildDeepgramUsage(
  ctx: BaseCtx,
  audioSeconds: number,
  modelName: string,
  operation: string
): UsageEvent {
  const minutes = audioSeconds / 60;
  return {
    ...ctx,
    requestId: ctx.requestId ?? null,
    provider: 'deepgram',
    operation,
    audioSeconds,
    unitCount: minutes,
    unitType: 'minutes',
    unitCostUsd: PRICING.deepgram_nova3_medical,
    totalCostUsd: minutes * PRICING.deepgram_nova3_medical,
    modelName,
  };
}

export function buildWhisperUsage(
  ctx: BaseCtx,
  audioSeconds: number,
  // ⚠️ B4's CLOSING STEP — `operation` IS THE CALLER'S PURPOSE, NOT A CONSTANT.
  // This used to be hardcoded `'transcribe_batch'`, which is the same defect
  // B4 step 1 removed from the Deepgram builder and the same one the item's own
  // wording names: *"real operation instead of the hardcoded
  // 'transcribe_realtime'"*. Whisper is the cross-provider fallback and its
  // caller's purpose is `tm_transcribe` — so a rollup grouped by `operation`
  // would have filed the fallback under a label no stage uses, and B4's
  // coverage gate could never have matched it to a stage.
  //
  // No historical cost: production holds ZERO rows with either label from this
  // builder, because the fallback is gated OFF pending a BAA
  // (`TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED=false`).
  operation: string
): UsageEvent {
  const minutes = audioSeconds / 60;
  return {
    ...ctx,
    requestId: ctx.requestId ?? null,
    provider: 'whisper',
    operation,
    audioSeconds,
    unitCount: minutes,
    unitType: 'minutes',
    unitCostUsd: PRICING.whisper,
    totalCostUsd: minutes * PRICING.whisper,
    modelName: 'whisper-1',
  };
}

export function buildAnthropicUsage(
  ctx: BaseCtx,
  inputTokens: number,
  outputTokens: number,
  modelName: string,
  operation = 'soap_generate',
  cacheReadInputTokens = 0,
  cacheCreationInputTokens = 0,
): UsageEvent {
  // Per-model pricing. Opus 4.7 lands in the L4/L5/L7c layers (audit
  // Finding 04.1) so the dispatch must recognise it explicitly — the
  // legacy isHaiku-vs-Sonnet branch would have priced Opus calls at
  // Sonnet's rate. The shared `claudeCostCents` helper in pricing.ts
  // owns the source-of-truth per-million rates; we mirror them here as
  // input/output rates only because UsageEvent records `unitCostUsd`
  // (the input-rate-per-token, used by the admin dashboard's coarse
  // "cents per token" lens) separately from `totalCostUsd`.
  const lower = modelName.toLowerCase();
  let inputRate: number;
  let outputRate: number;
  if (lower.includes('haiku')) {
    inputRate = PRICING.anthropic_haiku_input;
    outputRate = PRICING.anthropic_haiku_output;
  } else if (lower.includes('opus')) {
    inputRate = PRICING.anthropic_opus_input;
    outputRate = PRICING.anthropic_opus_output;
  } else {
    inputRate = PRICING.anthropic_sonnet_input;
    outputRate = PRICING.anthropic_sonnet_output;
  }
  // Authoritative per-call total comes from the pricing.ts dispatcher
  // (env-overridable + cache-aware). Falls back to the per-rate
  // computation for non-dispatchable models so the row still has a
  // sensible figure; the fallback also applies the cache multipliers
  // so a model that isn't in the dispatcher's switch still bills cache
  // tokens honestly.
  const dispatchedCents = claudeCostCents(
    modelName,
    inputTokens,
    outputTokens,
    cacheReadInputTokens,
    cacheCreationInputTokens,
  );
  const cacheReadUsd =
    (cacheReadInputTokens / 1_000_000) * inputRate * PRICING.anthropic_cache_read_multiplier;
  const cacheWriteUsd =
    (cacheCreationInputTokens / 1_000_000) * inputRate * PRICING.anthropic_cache_write_5min_multiplier;
  const totalCostUsd =
    dispatchedCents > 0
      ? dispatchedCents / 100
      : (inputTokens / 1_000_000) * inputRate +
        (outputTokens / 1_000_000) * outputRate +
        cacheReadUsd +
        cacheWriteUsd;
  return {
    ...ctx,
    requestId: ctx.requestId ?? null,
    provider: 'anthropic',
    operation,
    inputTokens,
    outputTokens,
    cacheReadInputTokens,
    cacheCreationInputTokens,
    // For Anthropic we record total tokens as `unitCount` and the input
    // rate as `unitCostUsd` for a coarse-but-honest single-figure
    // representation. The accurate per-call cost lives in `totalCostUsd`
    // (which already accounts for input + output at separate rates).
    unitCount: inputTokens + outputTokens,
    unitType: 'tokens_in',
    unitCostUsd: inputRate / 1_000_000,
    totalCostUsd,
    modelName,
  };
}

export function buildOpenAIEmbedUsage(
  ctx: BaseCtx,
  tokens: number,
  modelName: string,
  // ⚠️ B4's CLOSING STEP — AND THIS ONE WAS FOUND BY THE GATE, NOT BY READING.
  // Hardcoded `'embed'` while every caller's purpose is `tm_embed`. The first
  // full QA coverage run reported `unenumerated operation 'embed' metered
  // against this run's visits` — a stage that was metering correctly, under a
  // name no stage list could ever contain.
  //
  // ⚠️ AND IT EXPLAINS A NUMBER ALREADY IN THE LEDGER. B4 step 1 recorded
  // *"`api_usage_events`: zero openai rows, ever"* for `tm_embed`. True — and
  // it would have stayed true even after the credential is fixed, because the
  // rows would have arrived labelled `embed`. The zero was going to survive its
  // own cure.
  //
  // No historical cost: production holds ZERO rows from this builder under
  // either label (the prod OpenAI credential has been dead since 2026-07-02).
  operation: string
): UsageEvent {
  return {
    ...ctx,
    requestId: ctx.requestId ?? null,
    provider: 'openai',
    operation,
    inputTokens: tokens,
    unitCount: tokens,
    unitType: 'tokens_in',
    unitCostUsd: PRICING.openai_embedding / 1_000_000,
    totalCostUsd: (tokens / 1_000_000) * PRICING.openai_embedding,
    modelName,
  };
}

export function buildResendUsage(
  ctx: BaseCtx,
  emailCount = 1
): UsageEvent {
  return {
    ...ctx,
    requestId: ctx.requestId ?? null,
    provider: 'resend',
    operation: 'email_send',
    emailCount,
    unitCount: emailCount,
    unitType: 'emails',
    unitCostUsd: PRICING.resend_email,
    totalCostUsd: emailCount * PRICING.resend_email,
  };
}
