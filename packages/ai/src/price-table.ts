// ============================================================================
// FOUNDATION B3 — READING THE VERSIONED PRICE TABLE
// ----------------------------------------------------------------------------
// SPEC §2.2 wants a usage row to record "which price table priced it, so a
// later rate change never re-prices history". `price_rates` holds the rates,
// each for one period; this module is the only place that turns
// (vendor, model, unit, instant) into a number.
//
// ⚠️ NOTHING IS BILLED THROUGH HERE YET. B3 lands the table, its seed and this
// reader. The meter still prices from `pricing.ts` / `api-usage.ts`'s `PRICING`,
// and repointing it is B4/B6. Those two in-code surfaces are left alone on
// purpose (SPEC §4.5) — changing them now would silently re-base a year of
// historical `ai_calls` comparisons.
//
// ── THE ONE RULE THIS FILE EXISTS TO ENFORCE ───────────────────────────────
//
//     A MISSING RATE IS `null`. IT IS NEVER ZERO.
//
// `claudeCostCents` returns 0 for a model it does not recognise
// (`pricing.ts:131`), and `modelInputCentsPerM` does the same. DISCOVERY §D.3
// names the consequence: an unpriced model **silently bills nothing**. That is
// a fail-open, and it is the same family as a defaulted provenance column
// (ruling 67) and a minted request id (B1-b) — a value invented where the
// honest answer was "we do not know".
//
// So the return type is nullable and there is no `?? 0` anywhere below. A
// caller that wants a number must decide what to do when there isn't one.
// ============================================================================

import prisma from '@meddoc/db';

/** Vendors this table prices. Matches `price_rates_provider_vocabulary`. */
export type PriceProvider = 'anthropic' | 'deepgram' | 'openai';

/**
 * Whether the vendor charges this rate for a pre-recorded or a live call.
 * Matches `price_rates_delivery_mode_vocabulary`.
 *
 * `not_applicable` is a real value rather than NULL because this column is part
 * of the exclusion constraint's key, and `NULL = NULL` is UNKNOWN in SQL — two
 * rows carrying NULL here would not collide, and the overlap guard would pass
 * on exactly the rows it exists to catch.
 */
export type DeliveryMode = 'pre_recorded' | 'streaming' | 'not_applicable';

/**
 * What is being counted. Matches `price_rates_unit_quantity_matches_type`.
 *
 * ⚠️ `cache_write_5m` and `cache_write_1h` are SEPARATE because the vendor
 * charges 1.25× and 2×. `pricing.ts:claudeCostCents` collapses them into a
 * single 1.25×, which is right today only because the one caching call site
 * uses ephemeral 5m (DISCOVERY §C.8) — one config change from a 60%
 * under-charge.
 */
export type PriceUnitType =
  | 'tokens_input'
  | 'tokens_output'
  | 'cache_write_5m'
  | 'cache_write_1h'
  | 'cache_read';

/** Audio is priced per MINUTE and lives in its own union so the type system
 *  cannot let a token quantity be priced against an audio rate. */
export type AudioUnitType = 'audio_minutes';

export type AnyUnitType = PriceUnitType | AudioUnitType;

/** The legal denominator for each unit type — the TypeScript mirror of the
 *  CHECK constraint. Exported so the gate test can diff the two by hand
 *  instead of trusting that they were kept in step. */
export const UNIT_QUANTITY: Readonly<Record<AnyUnitType, bigint>> = {
  tokens_input: 1_000_000n,
  tokens_output: 1_000_000n,
  cache_write_5m: 1_000_000n,
  cache_write_1h: 1_000_000n,
  cache_read: 1_000_000n,
  audio_minutes: 1n,
};

/** Where a rate came from. SPEC §4.5 — a required property, not a comment. */
export type PriceProvenance = 'published' | 'invoice' | 'console';

/** The subset of a `price_rates` row this module needs. Kept structural so the
 *  pure selector can be exercised without a database. */
export interface PriceRateRow {
  /** ⚠️ REQUIRED SINCE B6, because the ledger row records WHICH rate priced it
   *  (SPEC §2.2 — "the row records which price table priced it, so a later rate
   *  change never re-prices history"). A snapshot that carried the rate's VALUE
   *  and not its identity could not be traced back to the period it came from,
   *  which is the half of the requirement that matters for B9. */
  id: string;
  provider: string;
  modelName: string;
  deliveryMode: string;
  unitType: string;
  rateMicroUsd: bigint;
  unitQuantity: bigint;
  effectiveFrom: Date;
  effectiveTo: Date | null;
  provenance: string;
  sourceUrl: string | null;
  sourceReadAt: Date | null;
}

/** An exact quantity, as a rational, so nothing here ever needs a float.
 *  Audio is the reason: Deepgram reports SECONDS and charges per MINUTE, and
 *  seconds ÷ 60 does not terminate ($0.0077/60 = $0.000128333…). Carrying the
 *  denominator instead of dividing early keeps the arithmetic exact until the
 *  single rounding step at the end. */
export interface Quantity {
  numerator: bigint;
  denominator: bigint;
}

/** N tokens. */
export function tokens(count: number | bigint): Quantity {
  return { numerator: BigInt(count), denominator: 1n };
}

/** N seconds of audio, expressed against a per-MINUTE rate. */
export function audioSeconds(seconds: number | bigint): Quantity {
  return { numerator: BigInt(seconds), denominator: 60n };
}

/**
 * WHICH RATE APPLIED AT THIS INSTANT — the whole point of the table.
 *
 * A period is `[effectiveFrom, effectiveTo)`: start inclusive, end exclusive,
 * matching the `'[)'` bound on `price_rates_no_overlap`. So a rate change at
 * midnight is a clean handover — no instant belongs to both rows, and none to
 * neither.
 *
 * ⚠️ THE DATABASE GUARANTEES AT MOST ONE MATCH. `price_rates_no_overlap` makes
 * two rates in effect at once unrepresentable, which is why this returns a
 * single row rather than "the newest match". A `ORDER BY effectiveFrom DESC
 * LIMIT 1` implementation would look identical on today's data and would
 * silently re-price history the moment a rate changed — that counterfactual is
 * what B3's gate distinguishes this from.
 */
export function selectRate(rows: readonly PriceRateRow[], at: Date): PriceRateRow | null {
  const t = at.getTime();
  const matches = rows.filter(
    (r) =>
      r.effectiveFrom.getTime() <= t && (r.effectiveTo === null || r.effectiveTo.getTime() > t),
  );
  if (matches.length === 0) return null;
  if (matches.length > 1) {
    // Unreachable while the exclusion constraint holds. If it is ever reached,
    // the constraint has been dropped and the honest answer is "we do not know
    // which rate applied" — not a guess dressed as an answer.
    throw new Error(
      `price-table: ${matches.length} overlapping rates for ` +
        `${matches[0]!.provider}/${matches[0]!.modelName}/${matches[0]!.unitType} at ` +
        `${at.toISOString()} — price_rates_no_overlap is not enforcing.`,
    );
  }
  return matches[0]!;
}

export interface RateLookup {
  provider: PriceProvider;
  modelName: string;
  unitType: AnyUnitType;
  deliveryMode: DeliveryMode;
  /** The instant the call was made — NOT `new Date()` at read time. Pricing a
   *  historical call with today's clock is exactly the re-pricing this table
   *  exists to prevent. */
  at: Date;
}

/**
 * The rate in effect for one key at one instant, or `null` if the table does
 * not price it.
 *
 * `null` is returned for two genuinely different situations and the caller
 * usually wants to treat them the same way (refuse), but they are worth
 * distinguishing in a log:
 *   - the model is not priced at all — e.g. `nova-3-medical`, which is PARKED
 *     until the vendor answers `docs/foundation/B3-deepgram-rate-request.md`;
 *   - the model is priced, but not for that instant — every seeded rate starts
 *     at its 2026-08-04 read-date, because that is the day we know it held.
 */
export async function rateAt(lookup: RateLookup): Promise<PriceRateRow | null> {
  const rows = (await prisma.priceRate.findMany({
    where: {
      provider: lookup.provider,
      modelName: lookup.modelName,
      unitType: lookup.unitType,
      deliveryMode: lookup.deliveryMode,
      effectiveFrom: { lte: lookup.at },
      OR: [{ effectiveTo: null }, { effectiveTo: { gt: lookup.at } }],
    },
  })) as unknown as PriceRateRow[];
  return selectRate(rows, lookup.at);
}

/**
 * Integer division rounding HALF-UP. Both arguments must be non-negative.
 *
 * GATE 0.4: integer micro-dollars ledger-wide, half-up at the micro-dollar, and
 * cent rounding at DISPLAY only. `Math.round(x * 1.5)` on a cents float is the
 * shape that ruling exists to forbid, so there is no `Number` in this path.
 */
export function divRoundHalfUp(numerator: bigint, denominator: bigint): bigint {
  if (denominator <= 0n) throw new Error('price-table: denominator must be positive');
  if (numerator < 0n) throw new Error('price-table: negative quantities are not priceable');
  return (2n * numerator + denominator) / (2n * denominator);
}

/**
 * COST IN MICRO-DOLLARS for a quantity at a rate.
 *
 *     cost_micro = round_half_up( qty.num × rate / (qty.den × rate.unitQuantity) )
 *
 * One rounding step, at the very end, on exact integer arithmetic — so 231
 * summed calls drift by nothing. The 98-of-1085 `ai_calls` rows that store
 * `costUsdCents = 0` are what the cent unit costs; this is the unit that
 * replaces it.
 */
export function costMicroUsd(quantity: Quantity, rate: PriceRateRow): bigint {
  return divRoundHalfUp(
    quantity.numerator * rate.rateMicroUsd,
    quantity.denominator * rate.unitQuantity,
  );
}

/**
 * B6 — WHAT WE CHARGE FOR A COST. SPEC §2.2 / GATE 0.4:
 *
 *     charge_micro = round_half_up( cost_micro × 3 / 2 )
 *
 * ⚠️ `× 3 / 2`, IN THAT ORDER, IN INTEGER ARITHMETIC — **never `* 1.5`**.
 * SPEC §4.4 names the float form as the thing this rule exists to forbid, and
 * the reason is not pedantry: `1.5` is exactly representable in binary64, but
 * `cost * 1.5` is a Number, so any cost above 2^53 micro-dollars silently loses
 * precision and every intermediate stays a float from then on. The micro-dollar
 * unit exists so the ledger never holds a value that was once a float.
 *
 * ⚠️ AND IT ROUNDS ONCE, AT THE END, ON THE TOTAL — never per component.
 * `chargeMicroUsd(a) + chargeMicroUsd(b)` is NOT `chargeMicroUsd(a + b)`:
 * with a=1 and b=1 the first gives 2+2=4 and the second gives 3. Summing
 * per-component charges introduces a half-micro-dollar bias per component, and
 * it biases UPWARD — i.e. it over-bills, growing with the number of pipeline
 * stages. {@link priceUsageRows} therefore sums COSTS and charges once, and the
 * gate asserts that specific inequality so nobody "simplifies" it back.
 *
 * Half-up at the micro-dollar is inherited from {@link divRoundHalfUp}. Cent
 * rounding is a DISPLAY concern and appears nowhere in this path.
 */
export function chargeMicroUsd(costMicro: bigint): bigint {
  return divRoundHalfUp(costMicro * 3n, 2n);
}
