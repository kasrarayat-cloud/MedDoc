// ============================================================================
// ADMIN-4 — THE PLATFORM MARGIN IS A ROW, AND ITS ABSENCE REFUSES.
// ----------------------------------------------------------------------------
// ⚠️ THIS GATE EXISTS BECAUSE THE DEFECT WAS ALREADY SHIPPED, THREE WEEKS
// BEFORE THE RULING THAT FORBIDS IT. `price-table.ts` computed
// `costMicro * 3n / 2n` and `billing-charge.ts` stamped the literal string
// `'3/2'` onto every ledger row; both landed 2026-08-11 in B6 (`cac9db7a`),
// and ruling #178 was written 2026-09-04 to foreclose exactly that — "a rate
// nobody can change without a deploy, and — worse — a rate with no audit row
// saying who changed it."
//
// ⚠️ AND IT WAS HARMLESS ONLY BY ACCIDENT OF CONFIGURATION. `BILLING_ENFORCED`
// appears nowhere in the production compose and the writer calls
// `assertProdDatabase()`. Neither is a decision anybody took about the margin.
// The nine-row recon also found a THIRD consumer that no flag covers — the
// failure-cost observer, `worker.ts:1658 -> billing-failure.ts -> priceUsageRows`
// — which is running in production now.
// ============================================================================
import { describe, expect, it, vi } from 'vitest';

import { marginStamp, priceUsageRows, type ChargeableUsageRow } from '../billing-charge';
import { chargeMicroUsd, divRoundHalfUp, type MarginRate, type PriceRateRow } from '../price-table';

function usageRow(over: Partial<ChargeableUsageRow> = {}): ChargeableUsageRow {
  return {
    id: 'evt_1',
    provider: 'anthropic',
    modelName: 'claude-sonnet-5',
    unitsSource: 'vendor',
    createdAt: new Date('2026-08-10T00:00:00Z'),
    audioSeconds: null,
    inputTokens: null,
    outputTokens: null,
    cacheReadInputTokens: null,
    cacheCreationInputTokens: null,
    ...over,
  };
}

const priceEverything = async (): Promise<PriceRateRow> => ({
  id: 'rate_1',
  provider: 'anthropic',
  modelName: 'claude-sonnet-5',
  deliveryMode: 'not_applicable',
  unitType: 'tokens_input',
  rateMicroUsd: 1n,
  unitQuantity: 1n,
  effectiveFrom: new Date('2026-08-04T00:00:00Z'),
  effectiveTo: null,
  provenance: 'published',
  sourceUrl: 'https://example.test/pricing',
  sourceReadAt: new Date('2026-08-04T00:00:00Z'),
});

const RATE = (n: number, d: number, id = 'pr_1'): MarginRate => ({
  id,
  marginNumerator: n,
  marginDenominator: d,
});

describe('ADMIN-4 — a missing margin REFUSES, and never defaults', () => {
  it('⚠️ NO CONFIGURED MARGIN -> `no_margin_rate`, not 3/2', async () => {
    // THE WHOLE POINT. The old code could not express "I have no rate": the
    // rate was compiled in, so every call billed at 3/2 whether or not anybody
    // had ever chosen it. An empty `platform_rates` table must now decline.
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 1000 })],
      priceEverything,
      async () => null,
    );
    expect(decision.charge, 'a missing margin still charged — at what rate?').toBe(false);
    if (decision.charge) return;
    expect(decision.reason).toBe('no_margin_rate');
    // ⚠️ AND IT REPORTS THE SIZE OF WHAT IT DECLINED, so the refusal cannot be
    // mistaken for "there was nothing to bill".
    expect(decision.pricedSoFarMicroUsd, 'the decline reads as a zero').toBe(1000n);
  });

  it('⚠️ NON-VACUITY — the SAME input with a margin present DOES charge', async () => {
    // Without this the arm above passes on any breakage that declines
    // everything, which is the failure mode a fail-closed change is most likely
    // to introduce.
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 1000 })],
      priceEverything,
      async () => RATE(3, 2),
    );
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;
    expect(decision.chargeMicroUsd).toBe(1500n);
  });

  it('⚠️ THE MARGIN IS NOT COMPILED IN — a different rate gives a different charge', async () => {
    // If any 3/2 survived anywhere in the path, this reds: the same 1000 µ$ of
    // cost must follow the ROW, not a literal.
    const at7_4 = await priceUsageRows([usageRow({ inputTokens: 1000 })], priceEverything, async () =>
      RATE(7, 4),
    );
    expect(at7_4.charge).toBe(true);
    if (!at7_4.charge) return;
    expect(at7_4.chargeMicroUsd, 'the charge ignored the configured rate').toBe(1750n);
    expect(at7_4.chargeMicroUsd).not.toBe(1500n);
  });

  it('⚠️ THE DECISION CARRIES THE RATE THAT APPLIED — the ledger stamps a row, not a literal', async () => {
    // `billing-charge.ts` used to write `multiplier: '3/2'` beside a hard-coded
    // computation: two encodings of one number, free to drift, with the ledger
    // still looking right. The decision now carries the row it used.
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 1000 })],
      priceEverything,
      async () => RATE(7, 4, 'pr_seven_quarters'),
    );
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;
    expect(decision.margin.id).toBe('pr_seven_quarters');
    expect(`${decision.margin.marginNumerator}/${decision.margin.marginDenominator}`).toBe('7/4');
  });
});

describe('ADMIN-4 — the rate is read at the USAGE instant, never at wall clock', () => {
  it('⚠️ the margin lookup is called with the LATEST PRICED instant', async () => {
    // #178 rules the change forward-only. That is only TRUE if the read is
    // anchored to the usage: a margin read at `new Date()` would re-price a
    // backlog against whatever rate is current when the worker catches up.
    // ⚠️ THE THIRD ROW IS THE WHOLE ARM, AND ITS ABSENCE MADE THIS VACUOUS.
    // The first fixture was two rows that BOTH price, so "latest of ALL rows"
    // and "latest of PRICED rows" coincided — and the refutation pass hoisted
    // the anchor above the `unitsSource !== 'vendor'` filter, produced a 33%
    // over-charge driven by a MOCK row (which ruling 66 says must never
    // influence money), and this arm stayed GREEN.
    //
    // `c` is a MOCK row, later than both vendor rows and never priced. If the
    // anchor moves above the filters, the margin is read at ITS instant.
    const seen: Date[] = [];
    await priceUsageRows(
      [
        usageRow({ id: 'a', createdAt: new Date('2026-08-10T00:00:00Z'), inputTokens: 1 }),
        usageRow({ id: 'b', createdAt: new Date('2026-08-12T00:00:00Z'), inputTokens: 1 }),
        usageRow({
          id: 'c',
          unitsSource: 'mock',
          createdAt: new Date('2026-08-20T00:00:00Z'),
          inputTokens: 1,
        }),
      ],
      priceEverything,
      async (at) => {
        seen.push(at);
        return RATE(3, 2);
      },
    );
    expect(seen).toHaveLength(1);
    expect(
      seen[0]!.toISOString(),
      'the margin was read at the wrong instant — a NON-PRICED row moved the anchor',
    ).toBe('2026-08-12T00:00:00.000Z');
  });

  it('⚠️ NEGATIVE CONTROL — it is not simply passing "now"', () => {
    // The arm above would also pass if the code read `new Date()` on a machine
    // whose clock happened to be 2026-08-12. Assert the instant came from the
    // ROW by checking it is not close to now.
    const rowInstant = new Date('2026-08-12T00:00:00Z').getTime();
    expect(Math.abs(Date.now() - rowInstant), 'the fixture instant is now — the arm is vacuous').
      toBeGreaterThan(60_000);
  });
});

describe('ADMIN-4 — the arithmetic stays INTEGER at any configured rate', () => {
  it('⚠️ above the float-safe range, at a rate that is not 3/2', () => {
    // `price-table.ts` explains why this matters: 1.5 is exactly representable
    // in binary64, but `cost * 1.5` is a Number, so any cost above 2^53 µ$
    // silently loses precision. Making the margin configurable must not quietly
    // reintroduce a float — so the check is repeated at a NEW rate.
    const big = 9_007_199_254_740_993n; // 2^53 + 1
    expect(chargeMicroUsd(big, RATE(7, 4))).toBe(divRoundHalfUp(big * 7n, 4n));
    expect(BigInt(Math.round(Number(big) * 1.75))).not.toBe(chargeMicroUsd(big, RATE(7, 4)));
  });

  it('⚠️ half-up is inherited, not reimplemented, at an arbitrary rate', () => {
    for (let c = 0n; c < 40n; c++) {
      expect(chargeMicroUsd(c, RATE(7, 4))).toBe(divRoundHalfUp(c * 7n, 4n));
    }
  });
});

describe('ADMIN-4 — the constant is GONE from the source', () => {
  it('⚠️ `chargeMicroUsd` no longer compiles a margin in', async () => {
    // A source read, deliberately: the behavioural arms above would all pass on
    // a function that took the rate AND ignored it in one branch. This asserts
    // the literal itself is gone.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, '..', 'price-table.ts'), 'utf8');
    const body = src.slice(src.indexOf('export function chargeMicroUsd'));
    const fn = body.slice(0, body.indexOf('\n}'));
    expect(fn, 'the 3/2 is still compiled into chargeMicroUsd').not.toMatch(/\b3n\b/);
    expect(fn, 'the margin is not taken from the argument').toContain('margin.marginNumerator');
  });

  it('⚠️ POSITIVE CONTROL — the reader finds the function it claims to read', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, '..', 'price-table.ts'), 'utf8');
    expect(src).toContain('export function chargeMicroUsd');
    expect(src, 'divRoundHalfUp is no longer the rounding used').toContain('divRoundHalfUp');
  });
});

describe('ADMIN-4 — the bounds are enforced on the READ, not only by the database', () => {
  // ⚠️ THE FIRST VERSION OF THIS GUARD CHECKED `<= 0` ONLY, AND ITS COMMENT
  // CLAIMED TO PROTECT THE READ. A `1/2` row passed it and the platform billed
  // HALF its own cost; `100/1` billed a hundred times. Both stamp an id that
  // resolves, so the §2.5 declaration's own failure criterion never fires.
  //
  // The bounds lived ONLY in a Postgres CHECK that Prisma cannot model — the
  // class `scripts/check-ledger-append-only.sh` already documents: "prisma
  // migrate dev … silently omits them … every test green."
  it.each([
    ['below 1.0 — the platform bills less than cost', 1, 2],
    ['above 5.0 — #178\'s ceiling', 51, 10],
    ['wildly above', 100, 1],
    ['zero denominator', 3, 0],
    ['negative numerator', -3, 2],
  ])('⚠️ REFUSES a rate %s', async (_name, n, d) => {
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 1000 })],
      priceEverything,
      async () => RATE(n, d),
    );
    expect(decision.charge, `a ${n}/${d} rate was accepted and billed`).toBe(false);
  });

  it('⚠️ NON-VACUITY — the edges of the allowed range are ACCEPTED', async () => {
    // Or the arm above passes on a guard that refuses everything, which is the
    // failure a bounds check is most likely to introduce.
    for (const [n, d, expected] of [
      [1, 1, 1000n],
      [5, 1, 5000n],
    ] as const) {
      const decision = await priceUsageRows(
        [usageRow({ inputTokens: 1000 })],
        priceEverything,
        async () => RATE(n, d),
      );
      expect(decision.charge, `${n}/${d} is inside the bounds and was refused`).toBe(true);
      if (decision.charge) expect(decision.chargeMicroUsd).toBe(expected);
    }
  });
});

describe('ADMIN-4 — the LEDGER STAMP is asserted, at the seam that writes it', () => {
  it('⚠️ the stamp carries the ratio AND the row id', () => {
    // The refutation pass reverted this to the literal `'3/2'` beside a
    // configured 7/4 rate and 835 of 835 tests stayed green — nothing read what
    // reached the ledger. `commitVisitCharge` calls `assertProdDatabase()`
    // first, so the write site cannot be driven; the builder is extracted for
    // exactly that reason.
    expect(marginStamp(RATE(7, 4, 'pr_seven_quarters'))).toEqual({
      multiplier: '7/4',
      platformRateId: 'pr_seven_quarters',
    });
  });

  it('⚠️ it is DERIVED — a literal cannot survive here', () => {
    expect(marginStamp(RATE(3, 2, 'pr_a')).multiplier).toBe('3/2');
    expect(marginStamp(RATE(9, 5, 'pr_b')).multiplier).toBe('9/5');
    expect(marginStamp(RATE(9, 5, 'pr_b')).multiplier).not.toBe('3/2');
  });

  it('⚠️ AND THE WRITE SITE USES IT — not a second copy', async () => {
    // A pure builder proves nothing if the ledger still spells the fields out.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, '..', 'billing-charge.ts'), 'utf8');
    const pricing = src.slice(src.indexOf('          pricing: {'));
    const block = pricing.slice(0, pricing.indexOf('\n          },'));
    expect(block, 'the ledger builds the stamp itself').toContain('...marginStamp(');
    expect(block, 'a literal multiplier survived at the write site').not.toMatch(/multiplier:\s*[`'"]/);
  });
});

describe('ADMIN-4 — a missing rate is a FAILURE, not a free visit', () => {
  it('⚠️ `no_margin_rate` must NOT route like `nothing_billable`', async () => {
    // ⚠️ THE FIRST VERSION LET IT FALL THROUGH TO `declined`, WHICH IS
    // BYTE-IDENTICAL ROUTING TO A GENUINELY FREE VISIT. The worker logs
    // `outcome: charge.charged` and NOT `reason`, so a platform with no
    // configured margin would bill nothing forever and the only artifact would
    // be a line indistinguishable from a mocked run.
    //
    // `declined` is a DECISION about a real visit: we looked, and there is
    // nothing to charge. "I do not know the rate" is not that decision — it is
    // the class `balance_unreadable` already occupies, and the code says so.
    //
    // Read from SOURCE: `chargeVisitUsage` is not drivable here (its collaborators
    // hit the database), and the routing is a two-line branch whose absence is
    // the entire defect.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, '..', 'billing-pipeline.ts'), 'utf8');

    const iNoMargin = src.indexOf("result.decision.reason === 'no_margin_rate'");
    expect(iNoMargin, '`no_margin_rate` is not routed at all').toBeGreaterThan(-1);

    // it must resolve to `failed`, and BEFORE the generic `declined` return
    const after = src.slice(iNoMargin, iNoMargin + 400);
    expect(after, '`no_margin_rate` does not route to `failed`').toContain("charged: 'failed'");
    const iDeclined = src.indexOf("return { charged: 'declined'");
    expect(iDeclined, 'the generic declined return vanished — this arm is now vacuous').toBeGreaterThan(-1);
    expect(
      iNoMargin,
      '`no_margin_rate` is routed AFTER the generic decline, so it never reaches its branch',
    ).toBeLessThan(iDeclined);
  });

  it('⚠️ POSITIVE CONTROL — `balance_unreadable` still routes to `failed` too', async () => {
    // The precedent this reasons from must still be there; if somebody
    // "simplifies" it to `declined`, the argument above is gone and the arm
    // should not keep passing on a file that no longer makes it.
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const src = readFileSync(join(__dirname, '..', 'billing-pipeline.ts'), 'utf8');
    const i = src.indexOf("result.reason === 'balance_unreadable'");
    expect(i).toBeGreaterThan(-1);
    expect(src.slice(i, i + 200)).toContain("charged: 'failed'");
  });
});
