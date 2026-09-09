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

import { priceUsageRows, type ChargeableUsageRow } from '../billing-charge';
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
    const seen: Date[] = [];
    await priceUsageRows(
      [
        usageRow({ id: 'a', createdAt: new Date('2026-08-10T00:00:00Z'), inputTokens: 1 }),
        usageRow({ id: 'b', createdAt: new Date('2026-08-12T00:00:00Z'), inputTokens: 1 }),
      ],
      priceEverything,
      async (at) => {
        seen.push(at);
        return RATE(3, 2);
      },
    );
    expect(seen).toHaveLength(1);
    expect(seen[0]!.toISOString(), 'the margin was read at the wrong instant').toBe(
      '2026-08-12T00:00:00.000Z',
    );
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
