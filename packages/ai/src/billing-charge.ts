// ============================================================================
// FOUNDATION B6 — `charge = cost × 3 / 2`, AND THE PROD-ONLY LEDGER WRITER
// ----------------------------------------------------------------------------
// RELAY B6: "the writer refuses on the live QA stack, demonstrated, not
// asserted (F4) … Rounding rule stated and tested at the boundary."
// SPEC §2.4: "Prod-only billing writer — refuses in QA/mock. The writer asserts
// it is in production and refuses otherwise."
//
// ── THE FILE IS IN TWO HALVES, AND THE SPLIT IS LOAD-BEARING ───────────────
//
//   1. `priceUsageRows` — PURE. Priced components in, a decision out. No
//      database, no clock, no environment. Runs identically everywhere.
//   2. `commitVisitCharge` — the only thing that writes, and it refuses
//      anywhere but production.
//
// ⚠️ THE SPLIT EXISTS BECAUSE F4 MAKES THE WRITER UNOBSERVABLE ON QA.
// A writer that refuses off production can never be watched WRITING by any
// test we are allowed to run, and ruling 86(a) names what that costs: "a stage
// observed at zero everywhere is indistinguishable from a stage whose meter was
// deleted." If the arithmetic lived inside the prod-only function, the only
// provable statement about B6 would be "it refuses", and a `return null` at the
// top would satisfy that forever.
//
// So the decision is separated from the effect. The gate proves the DECISION
// exhaustively — every refusal reason, the rounding boundary, the sum-then-
// charge ordering — anywhere, and proves the EFFECT refuses by demonstration
// against the live QA database. Neither half can be green while empty.
//
// ── WHAT A `null` RATE MEANS — RULING 80(c), ANSWERED HERE ─────────────────
//
//     A VISIT WHOSE USAGE CANNOT BE **FULLY** PRICED IS NOT CHARGED AT ALL.
//
// Ruling 80(c) left this open in as many words: "The nullable return is a
// requirement on B4/B6: whoever wires the meter must decide what a refusal
// means and must not reach for a zero." Three answers were available:
//
//   · charge 0 for the unpriced part      — the fail-open `?? 0` that ruling
//                                           exists to forbid. An undercharge
//                                           that looks exactly like a cheap
//                                           visit.
//   · charge the priced part only         — WORSE than either, because it is
//                                           silent. The doctor gets a bill,
//                                           the bill looks right, and it is
//                                           short by however much the unpriced
//                                           stage cost. Nothing in the row
//                                           says a component was dropped.
//   · charge nothing, and say why         — chosen.
//
// The third is the only one where being wrong is VISIBLE. An unpriced visit
// produces no ledger row and a named reason, so the population of uncharged
// visits is queryable and B9 can reconcile it against the vendor invoice. The
// other two produce a row that is quietly wrong, on an APPEND-ONLY table where
// a wrong row can never be corrected in place — only offset by another row.
//
// ⚠️ AND THIS IS NOT A THEORETICAL BRANCH. It is the state of production today.
// `DEEPGRAM_MODEL=nova-3-medical` on the live worker, and `nova-3-medical` is
// the ONE model B3 deliberately refused to seed — SPEC §4.5 disqualifies its
// undated source, and `docs/foundation/B3-deepgram-rate-request.md` is the open
// vendor question. So EVERY production visit carrying audio is unpriceable
// right now, and this writer declines all of them by arithmetic rather than by
// a switch. The day the vendor answers, a row in `price_rates` starts the
// charging — deliberately, and with a rate somebody can cite.
// ============================================================================

import { assertProdDatabase } from '@meddoc/db/guard';
import prisma from '@meddoc/db';

import { readPracticeBalance } from './billing-balance';
import { DRAW_ORDER, splitCharge, type BucketDraw, type LedgerBucket } from './billing-buckets';
import {
  audioSeconds as audioQuantity,
  chargeMicroUsd,
  isUsableMargin,
  marginAt,
  type MarginRate,
  costMicroUsd,
  rateAt,
  tokens,
  type AnyUnitType,
  type DeliveryMode,
  type PriceProvider,
  type PriceRateRow,
  type Quantity,
} from './price-table';

// ---------------------------------------------------------------------------
// WHICH ROWS ARE BILLABLE AT ALL
// ---------------------------------------------------------------------------

/**
 * The per-run vendors. GATE 0.5 / SPEC §4.5: "only per-run vendors (Anthropic,
 * Deepgram) produce UsageEvents" that bill; Resend is NOT metered — its
 * subscription folds into margin and its rows become a cost line in B9's
 * reconciliation.
 *
 * ⚠️ `resend` IS ABSENT ON PURPOSE AND ITS ABSENCE IS ASSERTED BY THE GATE.
 * Production holds **219** Resend rows in `api_usage_events`, every one with a
 * NULL `userId`. A writer that charged "every vendor row" would bill all 219 to
 * whichever practice they resolved to — an over-charge for a line GATE 0.5 says
 * is not a billing input at all. An absence is invisible to a behavioural test
 * (ruling 84(a)), so the gate pins it on this constant by name.
 *
 * `openai` IS present: the embedding model is priced and the credential being
 * dead today is an operational fact, not a pricing rule.
 */
export const BILLABLE_PROVIDERS: readonly PriceProvider[] = ['anthropic', 'deepgram', 'openai'];

/**
 * How a vendor delivers the thing it charges for — the third key dimension of a
 * `price_rates` lookup (ruling 80(a)). It is DERIVED here rather than stored on
 * the usage row, and derived from a recorded fact rather than a guess:
 *
 * · `deepgram` → `pre_recorded`. Ruling 81(a): "No streaming call site exists on
 *   this stack — every Deepgram call is pre-recorded." That is why the
 *   hard-coded `transcribe_realtime` label was a falsehood and not merely a
 *   coarse one. Note the price table holds BOTH modes for `nova-3`
 *   (7700 µ$/min streaming, 4800 µ$/min pre-recorded) — so this is not a
 *   cosmetic choice, it is a 1.6× difference in the bill.
 * · audio on `openai` (whisper) → `pre_recorded`, same reasoning.
 * · everything token-shaped → `not_applicable`, matching the 40 seeded
 *   Anthropic rates and the embedding rate.
 *
 * ⚠️ IF A STREAMING CALL SITE IS EVER ADDED, THIS FUNCTION IS WHERE IT BREAKS —
 * silently, by pricing it as pre-recorded and UNDER-charging by a third. There
 * is no way to detect it from the usage row, because the row records what was
 * counted and not how it arrived. The honest mitigation is that ruling 81(a)'s
 * claim is asserted at its source: the gate greps for a streaming Deepgram call
 * site and requires there still be none.
 */
export function deliveryModeFor(provider: PriceProvider, unitType: AnyUnitType): DeliveryMode {
  if (unitType === 'audio_minutes') return 'pre_recorded';
  return 'not_applicable';
}

/** One priceable component of one usage row: N of a unit, at one instant. */
export interface UsageComponent {
  unitType: AnyUnitType;
  quantity: Quantity;
}

/** The subset of an `api_usage_events` row this module reads. Structural, so
 *  the pure core can be exercised without a database. */
export interface ChargeableUsageRow {
  id: string;
  provider: string;
  modelName: string | null;
  unitsSource: string;
  createdAt: Date;
  audioSeconds: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  cacheReadInputTokens: number | null;
  cacheCreationInputTokens: number | null;
}

/**
 * Split one usage row into the components the price table can price.
 *
 * ⚠️ ZERO-QUANTITY COMPONENTS ARE DROPPED, AND THAT IS NOT AN OPTIMISATION.
 * A row with `outputTokens = 0` must not require an output rate to exist: it
 * consumed none, so an absent rate for it is not a gap in our knowledge. Keeping
 * the component would make the whole visit refuse for a rate that could not have
 * changed the answer — a refusal with no cause, which is the mirror of a charge
 * with no basis.
 *
 * ⚠️ `cacheCreationInputTokens` MAPS TO `cache_write_5m`, AND THAT IS AN
 * ASSUMPTION, NOT A MEASUREMENT. `api_usage_events` has ONE cache-creation
 * column and the vendor charges 1.25× for a 5-minute TTL and 2× for an hour.
 * DISCOVERY §C.8 records that the single caching call site uses ephemeral 5m,
 * so this is right today and is a 60% under-charge one config change later.
 * `price-table.ts` already carries the same warning against collapsing the two
 * rates; this is the place the collapse would actually happen.
 */
export function componentsOf(row: ChargeableUsageRow): UsageComponent[] {
  const out: UsageComponent[] = [];
  const push = (unitType: AnyUnitType, quantity: Quantity) => {
    if (quantity.numerator > 0n) out.push({ unitType, quantity });
  };
  if (row.audioSeconds != null) push('audio_minutes', audioQuantity(Math.round(row.audioSeconds)));
  if (row.inputTokens != null) push('tokens_input', tokens(row.inputTokens));
  if (row.outputTokens != null) push('tokens_output', tokens(row.outputTokens));
  if (row.cacheReadInputTokens != null) push('cache_read', tokens(row.cacheReadInputTokens));
  if (row.cacheCreationInputTokens != null)
    push('cache_write_5m', tokens(row.cacheCreationInputTokens));
  return out;
}

// ---------------------------------------------------------------------------
// THE DECISION
// ---------------------------------------------------------------------------

/** One component that WAS priced, with the rate that priced it. */
export interface PricedComponent {
  /** ⚠️ ADMIN-4 — the instant this component's usage row was created. The
   *  margin's read instant is DERIVED from the max of these, so the anchor
   *  cannot be moved above a skip: a row that was not priced has no `at` here.
   *  Round 2 moved round 1's free-standing tracking statement one line and
   *  every test stayed green. */
  at: Date;
  usageEventId: string;
  provider: string;
  modelName: string;
  unitType: AnyUnitType;
  deliveryMode: DeliveryMode;
  /** The `price_rates` row id — SPEC §2.2's versioned snapshot. */
  rateId: string;
  costMicroUsd: bigint;
}

/** One component that could NOT be priced, and precisely why. */
export interface UnpricedComponent {
  usageEventId: string;
  provider: string;
  modelName: string | null;
  unitType: AnyUnitType;
  deliveryMode: DeliveryMode;
  reason: 'no_rate_for_key_at_instant' | 'no_model_name';
}

export type ChargeDecision =
  | {
      charge: true;
      costMicroUsd: bigint;
      chargeMicroUsd: bigint;
      /** ADMIN-4 — the rate that ACTUALLY applied, carried so the ledger stamps
       *  the row it used rather than a literal somebody hopes still matches. */
      margin: MarginRate;
      /** The ledger fields, built from `margin` at the moment it was applied.
       *  ⚠️ The write site SPREADS this and passes nothing — see `stamp:` in
       *  `priceUsageRows` for why an argument was the wrong shape. */
      stamp: { multiplier: string; platformRateId: string };
      priced: PricedComponent[];
    }
  | {
      charge: false;
      /**
       * `unpriced`         — at least one component has no rate. THE WHOLE
       *                      charge is declined; see the header.
       * `nothing_billable` — no billable component at all: a mocked run, a
       *                      Resend-only set, or genuinely zero units. Distinct
       *                      from `unpriced` because it is not a gap in our
       *                      knowledge, and B9 must not chase it.
       */
      /**
       * `no_margin_rate`   — ADMIN-4: the platform has NO configured margin at
       *                      this instant. ⚠️ REFUSES RATHER THAN DEFAULTING.
       *                      A default here would re-create exactly what #178
       *                      forbade — billing at a rate nobody set and no row
       *                      records.
       */
      reason: 'unpriced' | 'nothing_billable' | 'no_margin_rate';
      unpriced: UnpricedComponent[];
      /** What WOULD have been charged for the components that did price. Never
       *  written anywhere — it exists so an operator can see the size of what is
       *  being declined, and so the gate can prove the decline was not a zero. */
      pricedSoFarMicroUsd: bigint;
    };

/**
 * PRICE A SET OF USAGE ROWS AND DECIDE THE CHARGE. Pure apart from `lookup`,
 * which the caller supplies so the gate can drive it from a table literal.
 *
 * ⚠️ COSTS ARE SUMMED AND THE MULTIPLIER IS APPLIED **ONCE**, and the ordering
 * is the whole reason this takes a SET rather than being called per row.
 * `chargeMicroUsd` rounds half-up, so charging per component and summing biases
 * upward by up to half a micro-dollar PER COMPONENT — and a single visit has
 * dozens (17 Anthropic operations, each with up to four token components). That
 * is a systematic over-bill that grows with pipeline depth and would be
 * invisible in any single row. See the assertion in the gate.
 *
 * ⚠️ EACH ROW IS PRICED AT **ITS OWN** `createdAt`, never at read time. Pricing
 * a historical call with today's clock is exactly the re-pricing `price_rates`
 * exists to prevent, and `claude-sonnet-5` already carries two periods with a
 * handover on 2026-09-01 — so this is live, not hypothetical.
 */
/**
 * The margin fields written onto `ledger_entries.pricing`.
 *
 * ⚠️ EXTRACTED SO IT CAN BE ASSERTED. The refutation pass reverted the stamp to
 * the literal `'3/2'` beside a correctly-configured 7/4 rate and **835 of 835
 * tests stayed green**: nothing anywhere read the value written to the ledger.
 * `commitVisitCharge` calls `assertProdDatabase()` as its first statement, so
 * the write site cannot be driven from a test at all — which is exactly why
 * that seam was unguarded, and why the builder now lives outside it.
 *
 * ⚠️ THE ID TRAVELS WITH THE RATIO. A stamp you cannot resolve to a row is a
 * number with a story rather than a record — and a ratio without an id cannot
 * be checked against the rate that was in effect.
 */
export function marginStamp(margin: MarginRate): {
  multiplier: string;
  platformRateId: string;
} {
  return {
    multiplier: `${margin.marginNumerator}/${margin.marginDenominator}`,
    platformRateId: margin.id,
  };
}

/** The `charge: true` arm of {@link ChargeDecision}, on its own. */
export type ChargeableDecision = Extract<ChargeDecision, { charge: true }>;

/**
 * THE LEDGER'S `pricing` JSON FOR ONE DRAW — pure, and EXPORTED SO IT CAN BE
 * DRIVEN.
 *
 * ⚠️ ROUND 5 — IT WAS AN OBJECT LITERAL AT AN UNDRIVABLE WRITE SITE, AND THE
 * ONLY GUARD ON IT WAS A SOURCE GREP THAT MEASURED THE WRONG THING.
 * `commitVisitCharge` calls `assertProdDatabase()` as its first statement, so
 * no test could ever observe what it wrote; the gate therefore sliced the
 * literal out of the file as TEXT and asserted, of that slice, that no
 * `multiplier:` or `platformRateId:` KEY appeared after `...decision.stamp`.
 *
 * Measured against round 4: adding a module-level
 * `const LEGACY = { multiplier: '3/2', platformRateId: 'legacy' }` and a second
 * SPREAD — `...LEGACY,` on the line after `...decision.stamp,` — writes
 * `multiplier: '3/2'` beside a charge computed at 7/4, stamping an id that
 * resolves to no row, and the whole suite stays GREEN. A later spread is a
 * second writer of the same field exactly as a later key is; the round-3 regex
 * was written for "any `multiplier:` key at all" and a spread carries no key.
 *
 * ⚠️ THE CLASS IS "A SECOND WRITER OF THIS FIELD", AND A GREP CAN ONLY EVER
 * ENUMERATE SPELLINGS OF ONE. So the object is built HERE, by a function that
 * returns it, and the gate ASSERTS THE RETURNED VALUE — a second writer in any
 * spelling changes what comes back, and the assertion is on the value rather
 * than on the text that produced it. The write site is left with no literal to
 * mutate: `pricing: buildUsagePricing({...})`.
 *
 * SPEC §2.2's versioned snapshot: WHICH rates priced this, and what the
 * pre-multiplier cost was. Stored so a later rate change can never re-price
 * history and so B9 can explain the number line by line.
 *
 * ⚠️ THE SNAPSHOT IS THE WHOLE VISIT'S, ON EVERY ROW, AND THAT IS DELIBERATE.
 * The components priced ONE charge; the split is a settlement decision taken
 * afterwards and is not a property of any rate. Apportioning the components
 * across buckets would invent a per-component bucket attribution the pricing
 * never made. So each row carries the full derivation plus `draw`, which says
 * what THIS row settled — and B9 sums `draw.amountMicroUsd` across a visit's
 * rows to get back to `chargeMicroUsd`, rather than summing `components` twice.
 * The `visitId` is what joins them.
 */
export function buildUsagePricing(args: {
  visitId: string;
  decision: ChargeableDecision;
  draw: BucketDraw;
  ofBuckets: number;
}): {
  visitId: string;
  costMicroUsd: string;
  chargeMicroUsd: string;
  multiplier: string;
  platformRateId: string;
  draw: { bucket: LedgerBucket; amountMicroUsd: string; ofBuckets: number };
  components: ReadonlyArray<Record<string, string | null>>;
} {
  const { visitId, decision, draw, ofBuckets } = args;
  return {
    visitId,
    costMicroUsd: decision.costMicroUsd.toString(),
    chargeMicroUsd: decision.chargeMicroUsd.toString(),
    // ⚠️ ADMIN-4 — THE RATE THAT APPLIED, NOT A LITERAL. This read `'3/2'` — a
    // hard-coded string beside a hard-coded computation, so the two could drift
    // apart and the ledger would still look right. The id is stamped with it: a
    // stamp you cannot resolve to a row is a number with a story, not a record.
    ...decision.stamp,
    draw: {
      bucket: draw.bucket,
      amountMicroUsd: draw.amountMicroUsd.toString(),
      ofBuckets,
    },
    components: decision.priced.map((p) => ({
      usageEventId: p.usageEventId,
      provider: p.provider,
      modelName: p.modelName,
      unitType: p.unitType,
      deliveryMode: p.deliveryMode,
      rateId: p.rateId,
      costMicroUsd: p.costMicroUsd.toString(),
    })),
  };
}

export async function priceUsageRows(
  rows: readonly ChargeableUsageRow[],
  lookup: (args: {
    provider: PriceProvider;
    modelName: string;
    unitType: AnyUnitType;
    deliveryMode: DeliveryMode;
    at: Date;
  }) => Promise<PriceRateRow | null> = rateAt,
  /** ADMIN-4 — the platform margin in effect. Injectable for the same reason
   *  `lookup` is: so a gate can drive the absent case without a database. */
  marginLookup: (at: Date) => Promise<MarginRate | null> = marginAt,
): Promise<ChargeDecision> {
  const priced: PricedComponent[] = [];
  const unpriced: UnpricedComponent[] = [];
  /**
   * ADMIN-4 — the instant the MARGIN is read at: the latest `createdAt` among
   * the rows that actually priced.
   *
   * ⚠️ NOT `new Date()`. The vendor rate is looked up at `row.createdAt` a few
   * lines below, and a margin read at wall-clock time would price the same
   * usage against a rate that was not in effect when it happened — so a rate
   * change would retroactively re-price a backlog the moment the worker caught
   * up. #178 rules the change forward-only, and anchoring to the usage rather
   * than to the RUN is what keeps a slow worker from re-pricing a backlog.
   *
   * ⚠️ LATEST rather than earliest, because a charge is one act: with several
   * instants in one visit the rate that applies is the one in effect when the
   * last billable component was produced, not the first.
   *
   * ═══════════════════════════════════════════════════════════════════════
   * ⚠️ ROUND 5 — THE TWO LOOKUPS DO **NOT** MIRROR EACH OTHER, AND AN EARLIER
   * VERSION OF THIS COMMENT SAID THEY DID.
   * ═══════════════════════════════════════════════════════════════════════
   *
   * It read: *"#178 rules the change forward-only, and that is only true if
   * BOTH lookups are anchored to the usage."* That sentence is FALSE, and
   * measurably so. The VENDOR rate is looked up PER COMPONENT at that
   * component's own instant; the MARGIN is looked up ONCE, at max(instants),
   * and multiplied into the SUM. Measured against this unmodified function:
   *
   *   row a  2026-08-10  800 µ$ cost      pr_old 3/2 from 2026-08-01
   *   row b  2026-08-12  200 µ$ cost      pr_new 5/1 from 2026-08-11T12:00
   *   -> chargeMicroUsd 5000, stamp {"multiplier":"5/1","platformRateId":"pr_new"}
   *
   * 80% of that cost was metered more than a day BEFORE pr_new took effect and
   * is billed at pr_new anyway. Per-component anchoring would give 2200.
   *
   * ⚠️ AND THAT IS THE RULED ANSWER, WHICH IS WHY THE CODE IS UNCHANGED AND THE
   * COMMENT IS. Ruling #178 fixes the anchor: *"every metered charge records
   * the multiplier IN EFFECT AT BILLING TIME on its own ledger line"*, effect
   * *"at the next metering cycle"*, direction *"forward only — PAST BILLS are
   * never rewritten"*. Billing time for that visit is >= 2026-08-12, after
   * pr_new took effect, so 5/1 on the whole charge is what #178 prescribes.
   * Reading at max(priced instant) is a self-imposed TIGHTENING of the ruled
   * anchor — it can never reach past the last usage instant, where a wall-clock
   * read could — not a violation of it. "Forward only" governs rewriting bills
   * that EXIST; `ledger_entries` is append-only and the charge is written once
   * per (visit, bucket).
   *
   * ⚠️ AND PER-COMPONENT ANCHORING IS UNREPRESENTABLE IN THE RULED STAMP, so
   * "just fix it" is not available. `ledger_entries.pricing` carries ONE
   * {multiplier, platformRateId} per line and `components` does not carry
   * per-component instants, so a blended charge would stamp a multiplier that
   * CANNOT REPRODUCE `chargeMicroUsd` from `costMicroUsd` — precisely the
   * "number with a story" the stamp exists to prevent — and splitting rows per
   * margin period collides with the per-(visit, bucket) idempotency key.
   *
   * Which anchor is right (max, min, per-component, or wall-clock billing time)
   * is a MONEY-POLICY call and therefore the owner's. It is surfaced rather than
   * decided here. What was a defect, and is fixed, is a comment asserting a
   * property the code does not have. The arm below pins the anchor as a chosen
   * behaviour so the next round meets a decision instead of an accident.
   */

  for (const row of rows) {
    // ⚠️ A MOCK ROW IS NEVER CHARGED. Ruling 66 put `unitsSource` in a COLUMN
    // so every rollup could exclude mock rows in a `WHERE`; this is that
    // exclusion at the money layer. Charging one would bill a doctor for a call
    // no vendor ever received.
    if (row.unitsSource !== 'vendor') continue;
    // GATE 0.5 — see BILLABLE_PROVIDERS.
    if (!BILLABLE_PROVIDERS.includes(row.provider as PriceProvider)) continue;
    const provider = row.provider as PriceProvider;

    for (const component of componentsOf(row)) {
      const deliveryMode = deliveryModeFor(provider, component.unitType);
      // A billable row with no model name cannot be priced and must not be
      // silently skipped — "we do not know what this was" is a gap, not a zero.
      if (!row.modelName) {
        unpriced.push({
          usageEventId: row.id,
          provider,
          modelName: null,
          unitType: component.unitType,
          deliveryMode,
          reason: 'no_model_name',
        });
        continue;
      }
      const rate = await lookup({
        provider,
        modelName: row.modelName,
        unitType: component.unitType,
        deliveryMode,
        at: row.createdAt,
      });
      if (rate === null) {
        unpriced.push({
          usageEventId: row.id,
          provider,
          modelName: row.modelName,
          unitType: component.unitType,
          deliveryMode,
          reason: 'no_rate_for_key_at_instant',
        });
        continue;
      }
      priced.push({
        // ⚠️ THE INSTANT RIDES THE PRICED COMPONENT — ROUND 2, CLASS FIX.
        // Round 1 tracked it in a separate `chargeInstant` statement inside the
        // loop, and round 2 moved that statement ONE LINE UP — above the
        // non-billable-provider skip rather than above the mock skip round 1
        // had covered — and every test stayed green. A statement that can be
        // moved is a statement somebody will move. Carried on the row that
        // actually PRICED, "latest priced instant" is true by construction and
        // there is nothing left to hoist.
        at: row.createdAt,
        usageEventId: row.id,
        provider,
        modelName: row.modelName,
        unitType: component.unitType,
        deliveryMode,
        rateId: rate.id,
        costMicroUsd: costMicroUsd(component.quantity, rate),
      });
    }
  }

  const pricedSoFar = priced.reduce((sum, p) => sum + p.costMicroUsd, 0n);

  if (unpriced.length > 0) {
    return { charge: false, reason: 'unpriced', unpriced, pricedSoFarMicroUsd: pricedSoFar };
  }
  if (priced.length === 0) {
    return {
      charge: false,
      reason: 'nothing_billable',
      unpriced: [],
      pricedSoFarMicroUsd: 0n,
    };
  }
  // ⚠️ ADMIN-4 — THE MARGIN IS READ, AND ITS ABSENCE REFUSES.
  //
  // Read at the LATEST priced instant rather than `new Date()`, so the rate
  // applied is the one that was in effect for the usage being charged and not
  // the one in effect when the job happened to run. #178 rules the change
  // forward-only; that is only true if the read is anchored to the usage.
  // ⚠️ VALIDATED AT THE POINT OF USE, NOT ONLY AT THE POINT OF READ.
  // `marginLookup` is injectable — that is the whole reason a gate can drive
  // this — so a lookup that is not `marginAt` would otherwise deliver an
  // out-of-bounds rate straight into the arithmetic. A `1/2` row bills HALF
  // cost and stamps an id that resolves cleanly.
  // Derived from the priced set itself — see the note on `at` above.
  const chargeInstant = priced.reduce((mx, p) => (p.at > mx ? p.at : mx), new Date(0));
  const found = await marginLookup(chargeInstant);
  const marginAtInstant = found && isUsableMargin(found) ? found : null;
  // ═════════════════════════════════════════════════════════════════════════
  // ⚠️ ROUND 5, ADJUDICATED: THIS REFUSAL LOOKS LIKE A DEFECT AND IS THE
  // SPECIFICATION. Recorded here so round 6 meets the answer, not the question.
  // ═════════════════════════════════════════════════════════════════════════
  //
  // THE FINDING, and it is correct on every measurement: usage that predates
  // the FIRST `platform_rates` row can never be charged. Verified on a real
  // PG 16.15 with the migration applied byte-for-byte — every route to make a
  // rate cover an earlier instant is refused BY NAME:
  //
  //   INSERT effectiveFrom = now()-1h              -> 'precedes insertion … never before'
  //   INSERT effectiveFrom AND createdAt backdated -> same (the trigger overwrites createdAt)
  //   UPDATE effectiveFrom                         -> 'platform_rates is append-only'
  //   DELETE and re-insert                         -> 'DELETE is refused'
  //
  // ⚠️ EVERY ONE OF THOSE REFUSALS IS A GUARD THIS BRANCH ADDED ON PURPOSE, in
  // round 1, because the adversarial pass had found the OPPOSITE behaviour to be
  // the defect: inserting `{effectiveFrom: last month, 5/1}` re-priced every
  // uncharged visit since then at a stamp that resolved cleanly. Ruling #178 is
  // explicit — "forward only, past bills are never rewritten" — and equally
  // explicit that "a missing multiplier REFUSES, never bills 0". So the finding
  // measured the successful closure of a prior finding.
  //
  // ⚠️ WHAT IS NOT LOST, and this is the half that makes the trade acceptable:
  // `loadVisitChargeableUsage` is a pure `findMany` and NOTHING in the tree
  // updates or deletes `api_usage_events`. Every uncharged visit therefore stays
  // permanently enumerable as "a usage event with no ledger row" — which
  // `commitVisitCharge`'s own `balance_unreadable` comment names as the designed
  // recovery, and which B9 exists to do. The exact micro-dollar figure is
  // recomputable from those immutable rows forever, and the documented offset is
  // an `adjustment` ledger row.
  //
  // ⚠️ WHAT IS OWED IS AN OPERATIONAL PRECONDITION, NOT A CODE CHANGE:
  // **write the first `platform_rates` row BEFORE `BILLING_ENFORCED` is turned
  // on.** Nothing gates rate writes on the flag, so the window is empty under
  // correct sequencing and is forced by nothing in the code. It is recorded in
  // the §2.5 declaration, where the person flipping the flag will meet it.
  if (!marginAtInstant) {
    return {
      charge: false,
      reason: 'no_margin_rate',
      unpriced: [],
      pricedSoFarMicroUsd: pricedSoFar,
    };
  }
  // ONE rounding step, on the TOTAL. See the warning above.
  return {
    charge: true,
    costMicroUsd: pricedSoFar,
    chargeMicroUsd: chargeMicroUsd(pricedSoFar, marginAtInstant),
    margin: marginAtInstant,
    // ⚠️ THE STAMP IS BUILT HERE, FROM THE RATE THAT WAS JUST APPLIED — ROUND 2.
    // Round 1 extracted `marginStamp()` so the write site could be asserted,
    // and round 2 substituted its ARGUMENT: `marginStamp({...3/2})` beside a
    // 7/4 charge passed every arm, because the arm greps for the TOKEN. The
    // repair closed the literal spelling and left the class. With the stamp on
    // the decision there is no argument at the write site to get wrong.
    stamp: marginStamp(marginAtInstant),
    priced,
  };
}

// ---------------------------------------------------------------------------
// THE EFFECT — the only thing here that writes, and it refuses off production
// ---------------------------------------------------------------------------

/** The idempotency key for a visit's usage charge IN ONE BUCKET. GLOBALLY
 *  unique in the database (`ledger_entries.idempotencyKey`), so a second
 *  attempt is refused by the unique index rather than by a check-then-write
 *  race.
 *
 *  ⚠️ IT IS KEYED PER (VISIT, BUCKET) SINCE B7 step 3a, AND IT HAD TO BE. A
 *  charge can now split across two buckets, so a visit produces up to two rows;
 *  one key for both would make the SECOND insert collide with the first and the
 *  whole transaction roll back — a visit that could pay would record nothing.
 *  The bucket is part of the identity of the row, so it is part of the key.
 *
 *  ⚠️ AND THE SPLIT IS STILL IDEMPOTENT AS A WHOLE, which is the property that
 *  matters: a retry re-derives the same draws from the same balances only if
 *  nothing landed, and if anything landed the balance has moved and the first
 *  colliding key aborts the retry. Partial double-charging is not reachable
 *  because both rows are written in ONE transaction — see the writer.
 *
 *  ⚠️ IDEMPOTENCY MATTERS MORE HERE THAN ANYWHERE. On a mutable table a double
 *  charge is an UPDATE away from fixed. On this one it can only be offset by an
 *  `adjustment` row, so the duplicate and its correction both live in the
 *  ledger forever. */
export function visitChargeKey(visitId: string, bucket: LedgerBucket): string {
  return `usage:visit:${visitId}:${bucket}`;
}

export interface CommitVisitChargeArgs {
  practiceId: string;
  visitId: string;
  rows: readonly ChargeableUsageRow[];
}

/** The refusal arm of {@link ChargeDecision}, on its own.
 *
 *  ⚠️ THIS EXISTS TO CLOSE A DEFECT B8 step 2 FOUND AND WORKED AROUND. Its
 *  caller had to narrow rather than cast because `CommitResult`'s `written:
 *  false` arm typed `decision` as the WHOLE union, "including the `charge: true`
 *  branch that cannot occur there — B6 under-specifies the pair". It no longer
 *  can: the type now says what was always true. */
export type DeclinedChargeDecision = Extract<ChargeDecision, { charge: false }>;

/**
 * ⚠️ `written: false` NOW CARRIES A `reason`, AND THE TWO REFUSALS ARE
 * GENUINELY DIFFERENT EVENTS. `not_chargeable` is a PRICING answer — B9 must
 * not chase it, the arithmetic declined. `balance_unreadable` is an
 * INFRASTRUCTURE fault: the visit was chargeable, we could not read the wallet
 * to decide which bucket to draw from, and revenue was lost. Collapsing them
 * into one arm would hide an outage inside a pricing statistic.
 */
export type CommitResult =
  | {
      written: true;
      /** One id per bucket drawn — up to `DRAW_ORDER.length`, never zero. */
      ledgerEntryIds: readonly string[];
      draws: readonly BucketDraw[];
      chargeMicroUsd: bigint;
    }
  | { written: false; reason: 'not_chargeable'; decision: DeclinedChargeDecision }
  | { written: false; reason: 'balance_unreadable'; detail: string };

/**
 * APPEND ONE `usage` ROW FOR A VISIT — PRODUCTION ONLY.
 *
 * ⚠️ `assertProdDatabase()` IS THE FIRST STATEMENT, DELIBERATELY. It runs
 * before the pricing, before the read, before anything that could have a side
 * effect — so the refusal cannot be reached by a path that has already done
 * half the work. Same placement discipline B7's webhook signature check gets.
 *
 * ⚠️ THE AMOUNT IS NEGATIVE. `ledger_entries_kind_sign` CHECKs `usage <= 0`:
 * the balance is a running sum, so a debit is a negative amount rather than a
 * positive number with a direction flag. Passing the charge unnegated would be
 * refused by the database, which is the intended backstop — but it is negated
 * here so the refusal is never reached.
 *
 * ⚠️ `balanceAfter` AND `seq` ARE NOT PASSED, AND MUST NOT BE. Ruling 89(d):
 * the derive trigger computes them and IGNORES a caller-supplied value. Sending
 * one would not be validated, it would be silently discarded — so sending one is
 * a way to believe something false about the row you just wrote.
 */
export async function commitVisitCharge(args: CommitVisitChargeArgs): Promise<CommitResult> {
  assertProdDatabase();

  const decision = await priceUsageRows(args.rows);
  if (!decision.charge) return { written: false, reason: 'not_chargeable', decision };

  return prisma.$transaction(async (tx): Promise<CommitResult> => {
    // ── THE LOCKS. Taken here, in DRAW_ORDER, before the balance is read. ────
    //
    // ⚠️ WITHOUT THIS THE SPLIT IS A READ-THEN-WRITE RACE, and the derive
    // trigger does NOT close it. That trigger takes the same advisory lock, but
    // it takes it per ROW at INSERT time — long after this function has already
    // decided how much promo was available. Two concurrent visits for one
    // practice would both read $10 promo and both draw $10, and the ledger
    // would record $20 of a $10 grant.
    //
    // ⚠️ THE KEY SHAPE IS COPIED FROM `ledger_entries_derive()` ON PURPOSE —
    // `hashtext('ledger_entries'), hashtext(practiceId || ':' || bucket)`. A
    // DIFFERENT key would take a different lock and serialise nothing while
    // looking exactly like this code does. Advisory locks are re-entrant within
    // a transaction, so the trigger re-taking it below is free.
    //
    // ⚠️ AND THE ORDER IS WHY THERE IS NO DEADLOCK. Every writer that touches
    // more than one bucket takes them in DRAW_ORDER; a grant takes `promo`
    // alone and a top-up takes `paid` alone. No cycle exists, and a future
    // multi-bucket writer inherits the property by iterating the same constant.
    for (const bucket of DRAW_ORDER) {
      await tx.$executeRawUnsafe(
        `SELECT pg_advisory_xact_lock(hashtext('ledger_entries'), hashtext($1))`,
        `${args.practiceId}:${bucket}`,
      );
    }

    // ── THE BALANCE. Same reader as admission, inside this transaction. ──────
    //
    // ⚠️ AND IF IT CANNOT BE READ, NOTHING IS WRITTEN. The alternative —
    // falling back to "put it all on `paid`" — is the tempting one and it is
    // wrong in the direction that costs the DOCTOR: it spends their money while
    // promo we granted them sits unused, and on an append-only table that is
    // fixable only by an `adjustment` row somebody has to notice is owed.
    // Refusing loses OUR revenue instead, loudly and queryably, and B9's whole
    // job is finding a usage event with no ledger row. Between an error that
    // costs us money and one that costs a doctor money, we take ours.
    const read = await readPracticeBalance(args.practiceId, tx);
    if (!read.ok) {
      return {
        written: false,
        reason: 'balance_unreadable',
        detail: `cannot split a charge without a balance (${read.reason}): ${read.detail}`,
      };
    }

    const draws = splitCharge(decision.chargeMicroUsd, read.byBucket);
    const ledgerEntryIds: string[] = [];

    for (const draw of draws) {
      const created = await tx.ledgerEntry.create({
        data: {
          practiceId: args.practiceId,
          // ⚠️ DERIVED BY THE TRIGGER TOO — `NEW."practiceIdSnapshot" :=
          // NEW."practiceId"`, unconditionally — so whatever is sent here is
          // discarded, exactly like `balanceAfter` and `seq`. It is sent anyway
          // because Prisma's generated type REQUIRES it: B5 gave those two an
          // `@default(0)` precisely "so a Prisma caller need not send a value it
          // is not allowed to choose", and the third derived column did not get
          // the same treatment. A seam defect, recorded in the ledger rather
          // than patched from inside B6.
          //
          // It is safe HERE because both fields read the SAME variable in the
          // same statement, so the pair cannot drift — AGENTS.md's "prefer
          // deriving the value over threading a parameter", satisfied by having
          // exactly one source. A caller that passed a different id would have
          // it silently replaced, NOT rejected: the trigger overwrites before
          // `ledger_entries_snapshot_agrees` is evaluated, so that CHECK can
          // never see a disagreeing caller value.
          practiceIdSnapshot: args.practiceId,
          // SPEC §2.4 — two buckets, drawn in `DRAW_ORDER`. NOT a literal: the
          // one place the order is written down is `billing-buckets.ts`, and
          // `SPENDABLE_BUCKETS` is derived from the same constant, so admission
          // and the debit cannot disagree about which money is reachable.
          bucket: draw.bucket,
          kind: 'usage',
          // ⚠️ NEGATED HERE, PER DRAW. `splitCharge` returns POSITIVE
          // magnitudes; `ledger_entries_kind_sign` CHECKs `usage <= 0`. The sign
          // belongs next to the row that carries it, and the CHECK is the
          // backstop for the day this line is edited.
          amountMicroUsd: -draw.amountMicroUsd,
          idempotencyKey: visitChargeKey(args.visitId, draw.bucket),
          // ⚠️ NO OBJECT LITERAL HERE — ROUND 5. The snapshot is built by
          // `buildUsagePricing`, a pure exported function the gate DRIVES, so
          // the assertion is on the value that reaches the ledger rather than
          // on the text of a literal at a write site no test can execute. A
          // second writer of `multiplier` — a later key OR a later spread —
          // changes the returned object and reds a behavioural arm; the grep it
          // replaces could only ever enumerate spellings. See the function.
          pricing: buildUsagePricing({
            visitId: args.visitId,
            decision,
            draw,
            ofBuckets: draws.length,
          }),
        },
        select: { id: true },
      });
      ledgerEntryIds.push(created.id);
    }

    return {
      written: true,
      ledgerEntryIds,
      draws,
      chargeMicroUsd: decision.chargeMicroUsd,
    };
  });
}
