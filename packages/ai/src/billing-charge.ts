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

import {
  audioSeconds as audioQuantity,
  chargeMicroUsd,
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
      reason: 'unpriced' | 'nothing_billable';
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
export async function priceUsageRows(
  rows: readonly ChargeableUsageRow[],
  lookup: (args: {
    provider: PriceProvider;
    modelName: string;
    unitType: AnyUnitType;
    deliveryMode: DeliveryMode;
    at: Date;
  }) => Promise<PriceRateRow | null> = rateAt,
): Promise<ChargeDecision> {
  const priced: PricedComponent[] = [];
  const unpriced: UnpricedComponent[] = [];

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
  // ONE rounding step, on the TOTAL. See the warning above.
  return {
    charge: true,
    costMicroUsd: pricedSoFar,
    chargeMicroUsd: chargeMicroUsd(pricedSoFar),
    priced,
  };
}

// ---------------------------------------------------------------------------
// THE EFFECT — the only thing here that writes, and it refuses off production
// ---------------------------------------------------------------------------

/** The idempotency key for a visit's usage charge. GLOBALLY unique in the
 *  database (`ledger_entries.idempotencyKey`), so a second attempt is refused
 *  by the unique index rather than by a check-then-write race.
 *
 *  ⚠️ IDEMPOTENCY MATTERS MORE HERE THAN ANYWHERE. On a mutable table a double
 *  charge is an UPDATE away from fixed. On this one it can only be offset by an
 *  `adjustment` row, so the duplicate and its correction both live in the
 *  ledger forever. */
export function visitChargeKey(visitId: string): string {
  return `usage:visit:${visitId}`;
}

export interface CommitVisitChargeArgs {
  practiceId: string;
  visitId: string;
  rows: readonly ChargeableUsageRow[];
}

export type CommitResult =
  | { written: true; ledgerEntryId: string; chargeMicroUsd: bigint }
  | { written: false; decision: ChargeDecision };

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
  if (!decision.charge) return { written: false, decision };

  const created = await prisma.ledgerEntry.create({
    data: {
      practiceId: args.practiceId,
      // ⚠️ DERIVED BY THE TRIGGER TOO — `NEW."practiceIdSnapshot" :=
      // NEW."practiceId"`, unconditionally — so whatever is sent here is
      // discarded, exactly like `balanceAfter` and `seq`. It is sent anyway
      // because Prisma's generated type REQUIRES it: B5 gave those two an
      // `@default(0)` precisely "so a Prisma caller need not send a value it is
      // not allowed to choose", and the third derived column did not get the
      // same treatment. A seam defect, recorded in the ledger rather than
      // patched from inside B6.
      //
      // It is safe HERE because both fields read the SAME variable in the same
      // statement, so the pair cannot drift — AGENTS.md's "prefer deriving the
      // value over threading a parameter", satisfied by having exactly one
      // source. A caller that passed a different id would have it silently
      // replaced, NOT rejected: the trigger overwrites before
      // `ledger_entries_snapshot_agrees` is evaluated, so that CHECK can never
      // see a disagreeing caller value.
      practiceIdSnapshot: args.practiceId,
      // SPEC §2.4 — two buckets. Usage always draws on `paid`; the `promo`
      // bucket is granted and drawn separately, and B7 owns that split.
      bucket: 'paid',
      kind: 'usage',
      amountMicroUsd: -decision.chargeMicroUsd,
      idempotencyKey: visitChargeKey(args.visitId),
      // SPEC §2.2's versioned snapshot: WHICH rates priced this, and what the
      // pre-multiplier cost was. Stored so a later rate change can never
      // re-price history and so B9 can explain the number line by line.
      pricing: {
        visitId: args.visitId,
        costMicroUsd: decision.costMicroUsd.toString(),
        chargeMicroUsd: decision.chargeMicroUsd.toString(),
        multiplier: '3/2',
        components: decision.priced.map((p) => ({
          usageEventId: p.usageEventId,
          provider: p.provider,
          modelName: p.modelName,
          unitType: p.unitType,
          deliveryMode: p.deliveryMode,
          rateId: p.rateId,
          costMicroUsd: p.costMicroUsd.toString(),
        })),
      },
    },
    select: { id: true },
  });

  return {
    written: true,
    ledgerEntryId: created.id,
    chargeMicroUsd: decision.chargeMicroUsd,
  };
}
