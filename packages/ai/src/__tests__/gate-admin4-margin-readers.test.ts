// @vitest-environment node
// ============================================================================
// ADMIN-4 ROUND 6 — THE MARGIN READERS ARE DRIVEN, NOT INJECTED AROUND.
// ----------------------------------------------------------------------------
// ⚠️ FOUR FALSE GREENS ROUND 6 FOUND, EACH A ONE-LINE REGRESSION THAT LEFT THE
// WHOLE `packages/ai` SUITE GREEN (44 files, 823 tests) WHILE MOVING MONEY:
//
//   1. `marginAt`'s `where: { effectiveFrom: { lte: at } }` → `lte: new Date()`.
//      August usage billed at a September rate (5000 µ$ at 5/1, not 1500 at
//      3/2). Every `priceUsageRows` arm injected its own lookup, and the one
//      arm that reached `marginAt` stubbed `findMany` IGNORING `where`.
//   2. The failure-cost observer — the only consumer live in production —
//      hard-coding 3/2 at its call site. Its gate mocks `../billing-charge`
//      wholesale, so the observer's pricing call was never exercised.
//   3. `margin = margin ?? {3/2}` inside `chargeMicroUsd`. The arity arm reads
//      the SIGNATURE; a body fallback keeps it.
//   4. A float quantising the ratio at 1e-6. Every ratio any gate used (1/1,
//      3/2, 7/4, 9/5, 5/1) terminates at 1e-6, so it could not be told apart.
//
// ⚠️ THE STUB HONOURS WHAT IT IS ASKED — `where.effectiveFrom.lte`, `orderBy`
// in BOTH directions, `take` — and REFUSES a `where` it does not model, so a
// changed query cannot fall through to a canned answer. That is the whole
// lesson of item 1: a stub that ignores its arguments is a hole the shape of
// the argument.
// ============================================================================
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { ChargeableUsageRow } from '../billing-charge';

interface PlatformRow {
  id: string;
  marginNumerator: number;
  marginDenominator: number;
  effectiveFrom: Date;
  createdAt: Date;
}
let platformRows: PlatformRow[] = [];
const lteAsked: Date[] = [];
let usage: ChargeableUsageRow[] = [];

vi.mock('@meddoc/db/guard', () => ({ __esModule: true, assertProdDatabase: () => undefined }));

vi.mock('../billing-usage-source', () => ({
  __esModule: true,
  loadVisitChargeableUsage: async () => usage,
}));

vi.mock('@meddoc/db', () => {
  type Order = Array<Record<string, 'asc' | 'desc'>>;
  const client = {
    priceRate: {
      findMany: async ({ where }: { where: { unitType?: string } }) =>
        where.unitType && where.unitType !== 'tokens_input'
          ? []
          : [
              {
                id: 'rate_in',
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
              },
            ],
    },
    platformRate: {
      findMany: async (args: {
        where: Record<string, unknown>;
        orderBy?: Order;
        take?: number;
        select?: Record<string, boolean>;
      }) => {
        const keys = Object.keys(args.where ?? {});
        if (keys.length !== 1 || keys[0] !== 'effectiveFrom') {
          throw new Error(`stub: unmodelled platformRate where ${JSON.stringify(args.where)}`);
        }
        const lte = (args.where.effectiveFrom as { lte?: unknown }).lte;
        if (!(lte instanceof Date)) throw new Error('stub: effectiveFrom.lte is not a Date');
        lteAsked.push(lte);
        const order = args.orderBy ?? [];
        const rows = platformRows
          .filter((r) => r.effectiveFrom <= lte)
          .sort((a, b) => {
            for (const o of order) {
              const [k, dir] = Object.entries(o)[0]!;
              const av = (a as unknown as Record<string, Date>)[k]!.getTime();
              const bv = (b as unknown as Record<string, Date>)[k]!.getTime();
              if (av !== bv) return dir === 'desc' ? bv - av : av - bv;
            }
            return 0;
          })
          .slice(0, args.take ?? undefined);
        return rows.map(({ id, marginNumerator, marginDenominator }) => ({ id, marginNumerator, marginDenominator }));
      },
    },
  };
  return { __esModule: true, default: client, prisma: client };
});

import { marginAt, chargeMicroUsd } from '../price-table';
import { priceUsageRows } from '../billing-charge';
import { observeFailedVisitUsage } from '../billing-failure';

const PR_OLD: PlatformRow = {
  id: 'pr_old', marginNumerator: 3, marginDenominator: 2,
  effectiveFrom: new Date('2026-08-01T00:00:00Z'), createdAt: new Date('2026-08-01T00:00:00Z'),
};
const PR_NEW: PlatformRow = {
  id: 'pr_new', marginNumerator: 5, marginDenominator: 1,
  effectiveFrom: new Date('2026-09-05T00:00:00Z'), createdAt: new Date('2026-09-05T00:00:00Z'),
};

function row(id: string, at: string, inputTokens: number): ChargeableUsageRow {
  return {
    id, provider: 'anthropic', modelName: 'claude-sonnet-5', unitsSource: 'vendor',
    createdAt: new Date(at), audioSeconds: null, inputTokens, outputTokens: null,
    cacheReadInputTokens: null, cacheCreationInputTokens: null,
  };
}

beforeEach(() => {
  platformRows = [PR_OLD, PR_NEW];
  lteAsked.length = 0;
  usage = [];
});

describe('ADMIN-4 round 6 (1) — `marginAt` reads at the instant it is GIVEN', () => {
  it('⚠️ the real `marginAt` answers for the instant, not for now', async () => {
    const aug = new Date('2026-08-12T00:00:00Z');
    const sep = new Date('2026-09-06T00:00:00Z');
    const jul = new Date('2026-07-01T00:00:00Z');
    expect((await marginAt(aug))?.id, 'August read a later rate — the instant was not used').toBe('pr_old');
    expect((await marginAt(sep))?.id).toBe('pr_new');
    expect(await marginAt(jul), 'before the first rate there is NO margin').toBeNull();
    // The query carried exactly the instants it was given — not a clock.
    expect(lteAsked.map((d) => d.toISOString())).toEqual([aug, sep, jul].map((d) => d.toISOString()));
  });

  it('⚠️ `priceUsageRows` with its DEFAULT lookups prices August usage at the August rate', async () => {
    // No injected margin lookup: this is the path production runs.
    const d = await priceUsageRows([row('evt_1', '2026-08-12T00:00:00Z', 1000)]);
    expect(d.charge).toBe(true);
    if (!d.charge) return;
    expect(d.chargeMicroUsd, 'a backlog was re-priced at the current rate').toBe(1500n);
    expect(d.stamp).toEqual({ multiplier: '3/2', platformRateId: 'pr_old' });
  });

  it('⚠️ NEGATIVE CONTROL — the fixture instants are nowhere near "now"', () => {
    // If the test machine's clock sat between 08-12 and 09-05 a wall-clock read
    // would pick pr_old too, and both arms above would be vacuous.
    expect(Date.now()).toBeGreaterThan(PR_NEW.effectiveFrom.getTime() + 60_000);
  });
});

describe('ADMIN-4 round 6 (2) — the failure-cost observer prices through the REAL pricer', () => {
  it('⚠️ an EMPTY platform_rates (prod today) -> `unpriceable/no_margin_rate`, never a default', async () => {
    platformRows = [];
    usage = [row('evt_f', '2026-08-12T00:00:00Z', 1000)];
    const out = await observeFailedVisitUsage({ visitId: 'v1', category: 'transient', errorName: null });
    expect(out, 'the observer invented a margin nobody configured').toMatchObject({
      observed: 'unpriceable',
      reason: 'no_margin_rate',
      pricedSoFarMicroUsd: 1000n,
    });
  });

  it('⚠️ NON-VACUITY — a configured 7/4 is the margin the observer reports', async () => {
    platformRows = [{ ...PR_OLD, id: 'pr_74', marginNumerator: 7, marginDenominator: 4 }];
    usage = [row('evt_f', '2026-08-12T00:00:00Z', 1000)];
    const out = await observeFailedVisitUsage({ visitId: 'v1', category: 'transient', errorName: null });
    expect(out).toMatchObject({ observed: 'priced', wouldChargeMicroUsd: 1750n, componentCount: 1 });
  });

  it('⚠️ and it inherits the straddle refusal — usage from before the first rate is not priced', async () => {
    // Both rows AFTER the vendor rate's 2026-08-04 start, so the only thing
    // missing for `pre` is the PLATFORM margin — the first version of this arm
    // dated them before it and measured `unpriced` (a vendor-rate gap) instead.
    platformRows = [{ ...PR_OLD, effectiveFrom: new Date('2026-08-10T00:00:00Z'), createdAt: new Date('2026-08-10T00:00:00Z') }];
    usage = [row('pre', '2026-08-09T23:59:59Z', 1000), row('post', '2026-08-10T00:00:01Z', 1)];
    const out = await observeFailedVisitUsage({ visitId: 'v1', category: 'transient', errorName: null });
    expect(out).toMatchObject({ observed: 'unpriceable', reason: 'no_margin_rate', pricedSoFarMicroUsd: 1001n });
  });
});

describe('ADMIN-4 round 6 (3) — `chargeMicroUsd` refuses a MISSING margin by name', () => {
  it('⚠️ null and undefined REFUSE, from the public barrel, and never bill 3/2', async () => {
    const ai = await import('../index');
    for (const missing of [null, undefined]) {
      expect(() => ai.chargeMicroUsd(1000n, missing as never), `a ${missing} margin billed`).toThrow(
        /no margin supplied/,
      );
    }
    // NON-VACUITY: a real margin still computes.
    expect(ai.chargeMicroUsd(1000n, { id: 'x', marginNumerator: 3, marginDenominator: 2 })).toBe(1500n);
  });
});

describe('ADMIN-4 round 6 (4) — integer arithmetic at ratios that do NOT terminate', () => {
  // An oracle written HERE, not borrowed from the subject: half-up of n/d as
  // (2n + d) / 2d, all bigint. Sharing `divRoundHalfUp` would re-derive the
  // thing under test.
  const exact = (c: bigint, n: bigint, d: bigint) => (2n * c * n + d) / (2n * d);
  const M = (n: number, d: number) => ({ id: `r${n}_${d}`, marginNumerator: n, marginDenominator: d });

  it('⚠️ 7/3 and 10/3 at round costs — a 1e-6 float quantisation is off by one here', () => {
    expect(chargeMicroUsd(3_000_000n, M(7, 3))).toBe(7_000_000n);
    expect(chargeMicroUsd(3_000_000n, M(10, 3))).toBe(10_000_000n);
    expect(chargeMicroUsd(3_000_000n, M(4, 3))).toBe(4_000_000n);
    expect(chargeMicroUsd(600_000_000n, M(5, 3))).toBe(1_000_000_000n);
  });

  it('⚠️ half-up at a non-terminating ratio, including an exact .5', () => {
    expect(chargeMicroUsd(1n, M(10, 3))).toBe(3n); // 3.333…
    expect(chargeMicroUsd(2n, M(10, 3))).toBe(7n); // 6.666…
    expect(chargeMicroUsd(1n, M(7, 3))).toBe(2n); // 2.333…
    expect(chargeMicroUsd(3n, M(7, 6))).toBe(4n); // 3.5 exactly → up
  });

  it('⚠️ a sweep against the independent oracle, at four non-terminating ratios and past 2^53', () => {
    const ratios: Array<[number, number]> = [[7, 3], [10, 3], [4, 3], [11, 7]];
    const costs: bigint[] = [];
    for (let c = 0n; c <= 3000n; c++) costs.push(c);
    costs.push(3_000_000n, 600_000_000n, 9_007_199_254_740_993n, 123_456_789_012_345_678n);
    for (const [n, d] of ratios) {
      for (const c of costs) {
        const got = chargeMicroUsd(c, M(n, d));
        if (got !== exact(c, BigInt(n), BigInt(d))) {
          throw new Error(`chargeMicroUsd(${c}, ${n}/${d}) = ${got}, exact half-up = ${exact(c, BigInt(n), BigInt(d))}`);
        }
      }
    }
  });
});
