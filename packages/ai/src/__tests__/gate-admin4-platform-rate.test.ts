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
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it, vi } from 'vitest';

import {
  buildUsagePricing,
  marginStamp,
  priceUsageRows,
  type ChargeableUsageRow,
} from '../billing-charge';
import {
  chargeMicroUsd,
  divRoundHalfUp,
  isUsableMargin,
  type MarginRate,
  type PriceRateRow,
} from '../price-table';

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

const MIGRATION_PATH = join(
  __dirname, '..', '..', '..', 'db', 'prisma', 'migrations',
  '20260909060000_admin4_platform_rate', 'migration.sql',
);
const migrationSql = readFileSync(MIGRATION_PATH, 'utf8');
const chargeSrcRaw = readFileSync(join(__dirname, '..', 'billing-charge.ts'), 'utf8');

/** Executable SQL only — prose must never satisfy a code assertion. The
 *  canonical form, byte-identical to `gate-b5-ledger-append-only.test.ts`. */
function stripSqlComments(sql: string): string {
  return sql
    .split('\n')
    .map((line) => {
      const i = line.indexOf('--');
      return i === -1 ? line : line.slice(0, i);
    })
    .join('\n');
}

/** Executable TypeScript only. The canonical form, byte-identical to
 *  `gate-b8-pipeline-seam.test.ts`. */
const stripTs = (src: string) =>
  src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');

const sqlOnly = stripSqlComments(migrationSql);
const chargeSrc = stripTs(chargeSrcRaw);

describe('ADMIN-4 round 5 — the strippers are positive-controlled BEFORE anything trusts them', () => {
  // ⚠️ EVERY `not.toContain` BELOW IS VACUOUS IF A STRIPPER RETURNS ''. A broken
  // stripper and a clean file produce identical output, so the instrument is
  // measured first — AGENTS.md, "positive-control every zero".
  it('the SQL stripper removes prose and keeps SQL', () => {
    expect(sqlOnly).toContain('CREATE TABLE "platform_rates"');
    expect(sqlOnly.length).toBeGreaterThan(1500);
    // A phrase that exists ONLY in the header prose must be gone…
    expect(migrationSql).toContain('THE MARGIN IS AN EXACT RATIO IN INTEGERS');
    expect(sqlOnly).not.toContain('THE MARGIN IS AN EXACT RATIO IN INTEGERS');
    // …and a line whose SQL precedes a trailing comment keeps its SQL.
    expect(sqlOnly).toContain('CREATE TRIGGER "platform_rates_no_truncate"');
  });

  it('the TS stripper removes prose and keeps code', () => {
    expect(chargeSrc).toContain('export async function priceUsageRows(');
    expect(chargeSrc.length).toBeGreaterThan(2000);
    expect(chargeSrcRaw).toContain('THE EFFECT — the only thing here that writes');
    expect(chargeSrc).not.toContain('THE EFFECT — the only thing here that writes');
  });
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
    const decision = await priceUsageRows(
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
        // Each instant answers with its OWN id, so the stamp names the instant
        // whose margin was APPLIED — not merely one that was asked.
        return RATE(3, 2, `pr@${at.toISOString()}`);
      },
    );
    // ⚠️ ROUND 6 — "CALLED ONCE" IS NO LONGER THE PROPERTY. The lookup is now
    // also asked at every other PRICED instant (the coverage check: no rate may
    // reach usage metered while none existed). The property is that the
    // APPLIED margin is the one at the LATEST PRICED instant, and that a row
    // which never priced is never asked about at all.
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;
    expect(
      decision.stamp.platformRateId,
      'the margin was read at the wrong instant — a NON-PRICED row moved the anchor',
    ).toBe('pr@2026-08-12T00:00:00.000Z');
    expect(seen.map((d) => d.toISOString()), 'a NON-PRICED row was looked up').not.toContain(
      '2026-08-20T00:00:00.000Z',
    );
    expect(new Set(seen.map((d) => d.toISOString()))).toEqual(
      new Set(['2026-08-12T00:00:00.000Z', '2026-08-10T00:00:00.000Z']),
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
    // ⚠️ SCOPED TO THE FUNCTION — ROUND 5. This greped the WHOLE file, where
    // `divRoundHalfUp` is DEFINED (:204) and separately used by `costMicroUsd`
    // (:221). It therefore could never fail for the reason its own message
    // states, even if `chargeMicroUsd` stopped using it entirely — a control
    // whose pattern is guaranteed to be present measures nothing.
    const body = src.slice(src.indexOf('export function chargeMicroUsd'));
    const fn = body.slice(0, body.indexOf('\n}'));
    expect(fn, 'divRoundHalfUp is no longer the rounding used').toContain('divRoundHalfUp');
  });

  it('⚠️ ROUND 5 — THE SECOND ARGUMENT IS REQUIRED, AND ITS ARITY SAYS SO', async () => {
    // ⚠️ THE ARM ABOVE CLAIMS TO ASSERT "the literal itself is gone" AND IS
    // BLIND TO THE DEFAULT-PARAMETER SPELLING, WHICH IS THE PR's OWN PROOF-TABLE
    // ROW. Measured: changing the signature to
    //     chargeMicroUsd(costMicro: bigint, margin: MarginRate = { id: 'compiled-in',
    //                    marginNumerator: 3, marginDenominator: 2 })
    // leaves `/\b3n\b/` unmatched — `marginNumerator: 3` is a plain Number, not a
    // bigint literal — leaves `margin.marginNumerator` present in the unchanged
    // body, type-checks, and makes `ai.chargeMicroUsd(1000n)` return 1500n from
    // the PUBLIC BARREL: ruling #178's exact defect, restored in one line, with
    // the whole suite green.
    //
    // ⚠️ AND NO BEHAVIOURAL ARM CAN SEE IT, DEDUCTIVELY: the pristine signature
    // REQUIRES two arguments, so no tsc-clean call site can omit one, so no
    // call-based arm can ever exercise the default. The property is a property
    // of the SIGNATURE, and `Function.prototype.length` is the one runtime
    // instrument that reads it: a default parameter drops it from 2 to 1.
    const { chargeMicroUsd: fn } = await import('../price-table');
    expect(fn.length, 'chargeMicroUsd grew a default — the rate can be omitted again').toBe(2);

    // POSITIVE CONTROL ON THE INSTRUMENT ITSELF, so a change to how `.length`
    // behaves cannot make the assertion above vacuously true. These two are
    // written here rather than derived from the subject, deliberately.
    const twoRequired = (_a: number, _b: number) => 0;
    const oneDefaulted = (_a: number, _b = 1) => 0;
    expect(twoRequired.length).toBe(2);
    expect(oneDefaulted.length, '`.length` no longer counts defaults — this arm is inert').toBe(1);

    // …and the source says the same thing, so a rename cannot quietly satisfy
    // the arity check with a different second parameter.
    const src = readFileSync(join(__dirname, '..', 'price-table.ts'), 'utf8');
    expect(
      src,
      'the chargeMicroUsd signature no longer takes a REQUIRED MarginRate',
    ).toMatch(/export function chargeMicroUsd\(costMicro: bigint, margin: MarginRate\): bigint/);
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

  it('⚠️ SUPERSEDED BY ROUND 2 — this asserted the INSTANCE, and round 2 broke it', () => {
    // This arm asserted the write site contained `...marginStamp(`. Round 2
    // showed why that is the wrong assertion: substituting the ARGUMENT —
    // `marginStamp({...3/2})` beside a 7/4 charge — satisfies it exactly, and
    // 783 of 783 tests stayed green while the ledger recorded a stamp that
    // contradicted the rate that priced it.
    //
    // ⚠️ KEPT AS A NAMED SUPERSESSION RATHER THAN DELETED, because the next
    // reader deserves to know that greping for the fix's SPELLING is the shape
    // that failed here. The real assertion is in the round-2 block: the write
    // site spreads `decision.stamp` and has no argument to get wrong.
    const src = readFileSync(join(__dirname, '..', 'billing-charge.ts'), 'utf8');
    expect(src).toContain('stamp: marginStamp(marginAtInstant)');
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

describe('ADMIN-4 round 2 — the repairs closed INSTANCES; these close the CLASSES', () => {
  it('⚠️ SUPERSEDED BY ROUND 5 — three rounds of regex could not close "a second writer"', () => {
    // ROUND 2's FINDING: round 1 extracted `marginStamp()` so the write site
    // could be asserted, and the arm greped for the TOKEN `...marginStamp(`.
    // Substituting the ARGUMENT — `marginStamp({...3/2})` beside a 7/4 charge —
    // satisfied it, and 783 of 783 stayed green.
    // ROUND 3 then required "any `multiplier:` KEY at all, not a quoted
    // literal", because `multiplier: ['3','2'].join('/')` after the spread had
    // walked past the quote-anchored version.
    // ⚠️ ROUND 5's FINDING: A LATER **SPREAD** IS A SECOND WRITER TOO, AND
    // CARRIES NO KEY. Measured on round 4: a module-level
    // `const LEGACY = { multiplier: '3/2', platformRateId: 'legacy' }` plus
    // `...LEGACY,` on the line after `...decision.stamp,` writes '3/2' beside a
    // charge computed at 7/4, stamps an id resolving to no row, and all four
    // assertions above pass — because there is no `multiplier:` token in the
    // block at all. `tsc --strict` emits nothing for spread-after-spread either.
    //
    // ⚠️ A GREP CAN ONLY EVER ENUMERATE SPELLINGS OF ONE WRITER. So the object
    // is no longer a literal at an undrivable write site: `buildUsagePricing`
    // returns it, the arms below DRIVE it, and the assertion is on the VALUE.
    // Kept as a named supersession rather than deleted, because the next reader
    // deserves to know that three rounds of tightening a regex is the shape
    // that failed here.
    expect(chargeSrc, 'the pricing snapshot is a literal again — a second writer can be added')
      .toMatch(/\bpricing: buildUsagePricing\(\{/);
  });

  it('⚠️ ROUND 5 — THE LEDGER SNAPSHOT IS DRIVEN, AND ITS STAMP IS THE RATE THAT PRICED', async () => {
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 1000 })],
      priceEverything,
      async () => RATE(7, 4, 'pr_74'),
    );
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;

    const pricing = buildUsagePricing({
      visitId: 'v1',
      decision,
      draw: { bucket: 'paid', amountMicroUsd: 1750n },
      ofBuckets: 1,
    });

    // THE ASSERTION THE THREE REGEXES WERE TRYING TO MAKE. A second writer of
    // either field — a later key, a later spread, a wrapper, a rename — changes
    // what comes back here, whatever it is spelled like.
    expect(pricing.multiplier, 'the ledger stamp is not the rate that priced').toBe('7/4');
    expect(pricing.platformRateId).toBe('pr_74');
    // The stamp must AGREE with the arithmetic beside it: 1000 µ$ at 7/4.
    expect(pricing.costMicroUsd).toBe('1000');
    expect(pricing.chargeMicroUsd).toBe('1750');
    expect(BigInt(pricing.costMicroUsd) * 7n / 4n).toBe(BigInt(pricing.chargeMicroUsd));
  });

  it('⚠️ ROUND 5 NON-VACUITY — a DIFFERENT rate produces a different stamp', async () => {
    // Or the arm above passes on a builder that returns a constant. Two rates,
    // two stamps, and neither is the historical literal.
    for (const [n, d, id, charge] of [
      [3, 2, 'pr_32', '1500'],
      [9, 5, 'pr_95', '1800'],
    ] as const) {
      const decision = await priceUsageRows(
        [usageRow({ inputTokens: 1000 })],
        priceEverything,
        async () => RATE(n, d, id),
      );
      if (!decision.charge) throw new Error(`${n}/${d} was refused — the fixture is wrong`);
      const pricing = buildUsagePricing({
        visitId: 'v1',
        decision,
        draw: { bucket: 'promo', amountMicroUsd: BigInt(charge) },
        ofBuckets: 1,
      });
      expect(pricing.multiplier).toBe(`${n}/${d}`);
      expect(pricing.platformRateId).toBe(id);
      expect(pricing.chargeMicroUsd).toBe(charge);
    }
  });

  it('⚠️ ROUND 5 — AND THE CALL SITE CANNOT WRAP IT, EITHER', () => {
    // The behavioural arms above catch a second writer INSIDE the builder. They
    // cannot see `pricing: { ...buildUsagePricing(…), ...LEGACY }` at the call
    // site, because that never calls the builder's own object into evidence.
    // So the one remaining source assertion is that `pricing:` is the CALL and
    // nothing else — no object literal to add a key or a spread to — and that
    // neither field is written anywhere in the whole write function.
    const commit = chargeSrc.slice(chargeSrc.indexOf('export async function commitVisitCharge'));
    expect(commit.length, 'commitVisitCharge was not found — this arm is vacuous').toBeGreaterThan(500);
    expect(commit, 'the pricing snapshot is wrapped in a literal again').toMatch(
      /\bpricing: buildUsagePricing\(\{/,
    );
    expect(commit, 'the write site writes `multiplier` itself').not.toMatch(/\bmultiplier\s*:/);
    expect(commit, 'the write site writes `platformRateId` itself').not.toMatch(
      /\bplatformRateId\s*:/,
    );
    expect(commit, 'the write site calls marginStamp again — an argument to get wrong').not.toContain(
      'marginStamp(',
    );
    // …and the builder itself has exactly ONE spread. A second one is the
    // round-5 defect wherever it is placed.
    const builder = chargeSrc.slice(
      chargeSrc.indexOf('export function buildUsagePricing'),
      chargeSrc.indexOf('export async function priceUsageRows'),
    );
    expect(builder.length, 'buildUsagePricing was not found — this arm is vacuous').toBeGreaterThan(200);
    expect(builder.match(/\.\.\./g) ?? [], 'a second spread in the pricing builder').toHaveLength(1);
    expect(builder).toContain('...decision.stamp');
  });

  it('⚠️ AND THE STAMP ON THE DECISION IS THE RATE THAT PRICED', async () => {
    const d = await priceUsageRows(
      [usageRow({ inputTokens: 1000 })],
      priceEverything,
      async () => RATE(7, 4, 'pr_74'),
    );
    expect(d.charge).toBe(true);
    if (!d.charge) return;
    expect(d.stamp).toEqual({ multiplier: '7/4', platformRateId: 'pr_74' });
    expect(d.chargeMicroUsd).toBe(1750n);
  });

  it('⚠️ THE INSTANT IS DERIVED FROM THE PRICED SET — no statement left to hoist', async () => {
    // ROUND 2 moved round 1's free-standing anchor ONE LINE UP — above the
    // non-billable-provider skip instead of above the mock skip round 1 had
    // covered — and everything stayed green. The sibling skip was uncovered.
    //
    // Now the instant rides the PRICED component, so a row that never priced
    // has no instant to contribute, whatever the loop order becomes.
    const seen: Date[] = [];
    const decision = await priceUsageRows(
      [
        usageRow({ id: 'a', createdAt: new Date('2026-08-10T00:00:00Z'), inputTokens: 1 }),
        usageRow({ id: 'b', createdAt: new Date('2026-08-12T00:00:00Z'), inputTokens: 1 }),
        // skipped by unitsSource
        usageRow({ id: 'c', unitsSource: 'mock', createdAt: new Date('2026-08-20T00:00:00Z'), inputTokens: 1 }),
        // skipped by provider — THE SIBLING ROUND 1's FIX DID NOT COVER
        usageRow({ id: 'd', provider: 'resend', createdAt: new Date('2026-08-25T00:00:00Z'), inputTokens: 1 }),
      ],
      priceEverything,
      async (at) => {
        seen.push(at);
        return RATE(3, 2, `pr@${at.toISOString()}`);
      },
    );
    // ROUND 6: see the arm above — the APPLIED instant is asserted through the
    // stamp, and the two skipped rows' instants must never have been asked.
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;
    expect(
      decision.stamp.platformRateId,
      'a row that never priced moved the margin anchor',
    ).toBe('pr@2026-08-12T00:00:00.000Z');
    const asked = seen.map((d) => d.toISOString());
    expect(asked, 'the MOCK row was looked up').not.toContain('2026-08-20T00:00:00.000Z');
    expect(asked, 'the non-billable-provider row was looked up').not.toContain('2026-08-25T00:00:00.000Z');
  });

  it('⚠️ THE GUARD SHIPS WITH THE ARITHMETIC — the barrel withheld it', async () => {
    // ROUND 2: `@meddoc/ai` exported `chargeMicroUsd` and `MarginRate` and NOT
    // `isUsableMargin`, so an app-side caller could compute
    // `chargeMicroUsd(1000n, {1,2}) === 500n` — the platform billing HALF its
    // own cost, the exact case round 1 said it had closed. A public surface
    // that ships an operation without its precondition has enforced nothing.
    const ai = await import('../index');
    expect(Object.keys(ai), '`isUsableMargin` is not on the public surface').toContain(
      'isUsableMargin',
    );
    expect(ai.isUsableMargin({ id: 'x', marginNumerator: 1, marginDenominator: 2 })).toBe(false);
    expect(ai.isUsableMargin({ id: 'x', marginNumerator: 3, marginDenominator: 2 })).toBe(true);
  });

  it('⚠️ FORWARD-ONLY IS SERVER-AUTHORITATIVE AND APPEND-ONLY — the CHECK alone trusted the writer', () => {
    // ROUND 2: `platform_rates_forward_only` compares two columns the WRITER
    // supplies. Prisma generates `createdAt?` for a `@default(now())` field, so
    // `{effectiveFrom: last month, createdAt: last month, 5/1}` satisfies it and
    // prices every uncharged visit since at 5x. An UPDATE re-prices
    // retroactively without touching either column at all.
    const sql = readFileSync(
      join(__dirname, '..', '..', '..', 'db', 'prisma', 'migrations',
        '20260909060000_admin4_platform_rate', 'migration.sql'),
      'utf8',
    );
    // ⚠️ `clock_timestamp()` — round 3. `now()` is transaction-START time, so a
    // writer that works then inserts stores a rate effective earlier than it
    // was written, by the transaction's duration (measured: 3.011s).
    // ROUND 6: `pg_catalog.`-qualified — an unqualified name lost to a caller's
    // `public.clock_timestamp()` and back-dated a rate (see the derivation arm).
    expect(sql, 'createdAt is not server-stamped').toContain(
      'NEW."createdAt" := pg_catalog.clock_timestamp()',
    );
    expect(sql, 'now() is transaction-start time — the retroactive window returns').not.toContain(
      'NEW."createdAt" := now()',
    );
    expect(sql, 'no append-only trigger').toContain('platform_rates_no_update');
    expect(sql, 'no delete refusal').toContain('platform_rates_no_delete');
    // ⚠️ AND THE DETACH IS CARVED OUT, or this trigger holds user deletion
    // hostage: `changedByUserId` is ON DELETE SET NULL, which fires an UPDATE.
    expect(sql, 'the ON DELETE SET NULL detach is not permitted').toContain(
      "OLD.\"changedByUserId\" IS NOT NULL",
    );
  });
});

describe('ADMIN-4 round 5 — TWO ADJUDICATED BEHAVIOURS, PINNED so round 6 meets a decision', () => {
  // ⚠️ BOTH OF THESE WERE RAISED AS DEFECTS AND BOTH ARE THE RULED PROPERTY.
  // They are pinned here rather than argued again, because an unrecorded
  // decision decays: the next pass re-derives the same question and an
  // unanswered question becomes "probably fine" through repetition alone.
  // Changing either is a MONEY-POLICY call under #178 and belongs to the owner.

  it('⚠️ ADJUDICATED — the margin is read ONCE, at the LATEST priced instant, and applies to the WHOLE charge', async () => {
    // RAISED AS: "the single margin read at the MAX priced instant applies a
    // rate change RETROACTIVELY to every earlier component of the same visit."
    // The mechanism is real and reproduced below. It is #178's own anchor:
    // "every metered charge records the multiplier IN EFFECT AT BILLING TIME on
    // its own ledger line", effect "at the next metering cycle", direction
    // "forward only — PAST BILLS are never rewritten". Reading at the latest
    // USAGE instant is strictly tighter than billing time, never looser.
    //
    // Per-component anchoring is prescribed nowhere and is unrepresentable in
    // the ruled stamp: ledger_entries.pricing carries ONE {multiplier,
    // platformRateId} per line, so a blended charge would stamp a multiplier
    // that cannot reproduce chargeMicroUsd from costMicroUsd.
    const rateOld = RATE(3, 2, 'pr_old');
    const rateNew = RATE(5, 1, 'pr_new');
    const NEW_FROM = new Date('2026-08-11T12:00:00Z');
    const seen: Date[] = [];

    const decision = await priceUsageRows(
      [
        // 800 µ$ metered on 2026-08-10 — a day and a half BEFORE pr_new exists
        usageRow({ id: 'a', createdAt: new Date('2026-08-10T00:00:00Z'), inputTokens: 800 }),
        usageRow({ id: 'b', createdAt: new Date('2026-08-12T00:00:00Z'), inputTokens: 200 }),
      ],
      priceEverything,
      async (at) => {
        seen.push(at);
        return at >= NEW_FROM ? rateNew : rateOld;
      },
    );

    // The APPLIED read is at the latest priced instant — the pinned choice, and
    // the stamp below proves it applied. ⚠️ ROUND 6 added a COVERAGE ask at
    // every other priced instant ("was ANY margin in effect?"); pr_old answers
    // it here, so the adjudicated charge is unchanged.
    expect(seen[0]!.toISOString()).toBe('2026-08-12T00:00:00.000Z');
    expect(seen.map((d) => d.toISOString()).sort()).toEqual([
      '2026-08-10T00:00:00.000Z',
      '2026-08-12T00:00:00.000Z',
    ]);
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;
    expect(decision.costMicroUsd).toBe(1000n);
    // 1000 µ$ × 5/1, NOT 800×3/2 + 200×5/1 = 2200. Written down deliberately.
    expect(
      decision.chargeMicroUsd,
      'the anchor moved — that is a MONEY-POLICY change under #178, not a refactor',
    ).toBe(5000n);
    expect(decision.stamp).toEqual({ multiplier: '5/1', platformRateId: 'pr_new' });
    // AND THE PROPERTY THE STAMP EXISTS FOR: the recorded multiplier reproduces
    // the charge from the cost. A blended per-component rate could not.
    expect(decision.costMicroUsd * 5n / 1n).toBe(decision.chargeMicroUsd);
  });

  it('⚠️ ADJUDICATED — a rate set AFTER the usage does not reach it, EVEN BESIDE later usage (round 6: the straddle)', async () => {
    // RAISED AS: "the pre-rate usage backlog is PERMANENTLY unbillable."
    // True, and it is the specification. #178: "forward only, past bills are
    // never rewritten" and "a missing multiplier REFUSES, never bills 0".
    // Every backdating route is refused BY NAME in the database — by guards
    // ROUND 1 OF THIS BRANCH ADDED, because the opposite behaviour (a backdated
    // row re-pricing every uncharged visit at a stamp that resolves cleanly) was
    // the defect that pass found.
    //
    // ⚠️ AND THE REFUSAL REPORTS WHAT IT DECLINED, so it can never read as
    // "there was nothing to bill" — that is the half that keeps the uncharged
    // set findable by B9 as "a usage event with no ledger row".
    const RATE_FROM = new Date('2026-08-01T00:00:00Z');
    const before = await priceUsageRows(
      [usageRow({ createdAt: new Date('2026-07-31T23:59:59Z'), inputTokens: 1000 })],
      priceEverything,
      async (at) => (at >= RATE_FROM ? RATE(3, 2, 'pr_first') : null),
    );
    expect(before.charge).toBe(false);
    if (before.charge) return;
    expect(before.reason).toBe('no_margin_rate');
    expect(before.pricedSoFarMicroUsd, 'the refusal reads as a zero').toBe(1000n);

    // NON-VACUITY: the SAME code charges the instant the usage falls inside the
    // rate's period. Without this the arm passes on a pricer that refuses
    // everything — and the finding would then be right.
    const after = await priceUsageRows(
      [usageRow({ createdAt: new Date('2026-08-01T00:00:01Z'), inputTokens: 1000 })],
      priceEverything,
      async (at) => (at >= RATE_FROM ? RATE(3, 2, 'pr_first') : null),
    );
    expect(after.charge).toBe(true);
    if (!after.charge) return;
    expect(after.chargeMicroUsd).toBe(1500n);

    // ⚠️ ROUND 6 — THE STRADDLE, AND THE TITLE ABOVE WAS FALSE WITHOUT IT. As
    // round 5 shipped, the refusal fired only when EVERY priced row predated the
    // first rate: add 1 µ$ metered after it and the whole visit charged 1502 µ$
    // at pr_first — 1 µ$ of new usage moved the charge from 0 to 1502.
    const firstRate = async (at: Date) => (at >= RATE_FROM ? RATE(3, 2, 'pr_first') : null);
    const pre = usageRow({ id: 'pre', createdAt: new Date('2026-07-31T23:59:59Z'), inputTokens: 1000 });
    const post = usageRow({ id: 'post', createdAt: new Date('2026-08-01T00:00:01Z'), inputTokens: 1 });
    for (const rows of [[pre, post], [post, pre]]) {
      // Both input orders — the refusal must not depend on which row is read first.
      const straddle = await priceUsageRows(rows, priceEverything, firstRate);
      expect(straddle, 'one post-rate row carried pre-rate usage over at the first rate').toEqual({
        charge: false,
        reason: 'no_margin_rate',
        unpriced: [],
        pricedSoFarMicroUsd: 1001n,
      });
    }

    // The RETRY-BACKLOG shape the round-6 pass gave: 90,000 µ$ metered
    // 2026-08-10 with no rate, the first rate (5/1) written 2026-09-15, and
    // 10,000 µ$ from a 2026-09-16 retry. It charged 500,000 µ$ at 5x.
    const FIVE_FROM = new Date('2026-09-15T00:00:00Z');
    const backlog = await priceUsageRows(
      [
        usageRow({ id: 'old', createdAt: new Date('2026-08-10T00:00:00Z'), inputTokens: 90_000 }),
        usageRow({ id: 'retry', createdAt: new Date('2026-09-16T00:00:00Z'), inputTokens: 10_000 }),
      ],
      priceEverything,
      async (at) => (at >= FIVE_FROM ? RATE(5, 1, 'pr_first5') : null),
    );
    expect(backlog, 'five weeks of pre-rate usage was billed at the first rate').toEqual({
      charge: false,
      reason: 'no_margin_rate',
      unpriced: [],
      pricedSoFarMicroUsd: 100_000n,
    });
  });
});

describe('ADMIN-4 round 5 — the SQL invariants the migration claims, asserted on the SQL', () => {
  // ⚠️ WHAT THIS BLOCK DOES AND DOES NOT CLAIM. CI has no Postgres, so a source
  // read is the only half that can run here — the same split
  // `gate-b5-ledger-append-only.test.ts` makes, and for the same reason: a
  // trigger is invisible to Prisma, so a regenerated migration omits it and
  // `prisma migrate diff` reports no drift. The BEHAVIOURAL half is
  // `scripts/check-platform-rates-invariants.sh`, which attempts every input
  // below against a real database inside `BEGIN … ROLLBACK`.
  //
  // Every assertion here runs against `sqlOnly`, never the raw file: this
  // migration's prose says "integer out of range", "btrim" and "5 *" because it
  // EXPLAINS why they were wrong, and prose is the one place the words you are
  // grepping for are guaranteed to appear.

  it('⚠️ THE PREVIOUS PAIR IS DERIVED, NOT ACCEPTED — the caller has no opinion', () => {
    // ROUND 5's FINDING: `previousNumerator`/`previousDenominator` were CALLER
    // CLAIMS. Measured on PG 16.15 against round 4, four inserts in order —
    // R1 3/2, R2 4/1 claiming previous 5/1, R3 2/1 with no pair, R4 3/1
    // claiming previous 1/1 — were ALL ACCEPTED. R2 permanently recorded that
    // the platform margin went 5.0 -> 4.0 when it went 1.5 -> 4.0; R3 was the
    // SECOND change and byte-indistinguishable from a first row, contradicting
    // `schema.prisma`'s "NULL on the seed row only". UPDATE, DELETE and
    // TRUNCATE are all refused, so the false history was UNCORRECTABLE.
    //
    // ⚠️ AND NO WRITER DISCIPLINE COULD HAVE FIXED IT. Two HONEST writers, each
    // reading the current rate and recording it, falsify each other — measured:
    // without the lock, a concurrent B recorded previous 3/2 while its actual
    // predecessor was A = 4/1. The prior art this migration says it copies takes
    // `pg_advisory_xact_lock` for exactly this reason.
    expect(sqlOnly, 'the derivation is not serialized — two honest writers falsify each other')
      .toContain("PERFORM pg_advisory_xact_lock(hashtext('platform_rates'), 0);");
    expect(sqlOnly, 'the previous pair is not derived — it is still a caller claim').toContain(
      'INTO NEW."previousNumerator", NEW."previousDenominator"',
    );
    // ⚠️ ANCHORED TO `createdAt`, NOT `effectiveFrom`, AND THAT IS WHAT MAKES IT
    // PERMANENT: forward-only guarantees every later row has
    // `effectiveFrom >= its own createdAt > this row's createdAt`, so no future
    // insert can fall inside this predicate. Anchored to `effectiveFrom` a row
    // scheduled ahead could be retroactively falsified by one inserted later
    // and effective sooner — in a table that cannot be corrected.
    expect(sqlOnly, 'the derivation is anchored to effectiveFrom — a later row can falsify it')
      .toContain('WHERE p."effectiveFrom" <= NEW."createdAt"');
    // The CHECKs are kept as belt and braces, and must not be dropped on the
    // grounds that the trigger now makes them unfalsifiable — the trigger is the
    // thing `prisma migrate dev` cannot see.
    expect(sqlOnly).toContain('platform_rates_previous_pair');
    expect(sqlOnly).toContain('platform_rates_previous_bounds');
  });

  it('⚠️ ROUND 6 — the derivation refuses above READ COMMITTED, LOCKS BEFORE IT STAMPS, and resolves no name through the caller', () => {
    // Three defects round 6 measured on PG 16, each a permanent false history:
    //  (a) REPEATABLE READ / SERIALIZABLE read a pre-lock snapshot → previous 3/2
    //      recorded where 2/1 was in effect, no 40001 raised;
    //  (b) createdAt stamped BEFORE the lock → 80 of 4800 rows false at the
    //      DEFAULT isolation with 16 honest writers; 0 with the lock first;
    //  (c) unqualified names → a TEMP `platform_rates` supplied the previous
    //      pair, and a `public.clock_timestamp()` back-dated a rate.
    // ⚠️ THIS IS THE SOURCE HALF ONLY. It reads this file, which is immutable
    // once applied; a later `CREATE OR REPLACE` is invisible here. The
    // behavioural half is `scripts/check-platform-rates-invariants.sh
    // --attempt` (ISOLATION, SHADOW and ORDER arms, plus the structural read of
    // the LIVE function body and proconfig).
    const fnStart = sqlOnly.indexOf('CREATE OR REPLACE FUNCTION platform_rates_stamp_created()');
    const fnEnd = sqlOnly.indexOf('$fn$ LANGUAGE plpgsql', fnStart);
    expect(fnStart, 'the reader cannot find the derivation function').toBeGreaterThan(-1);
    expect(fnEnd).toBeGreaterThan(fnStart);
    const body = sqlOnly.slice(fnStart, fnEnd);
    const iso = body.indexOf("current_setting('transaction_isolation') <> 'read committed'");
    const lock = body.indexOf("PERFORM pg_advisory_xact_lock(hashtext('platform_rates'), 0);");
    const stamp = body.indexOf('NEW."createdAt" := pg_catalog.clock_timestamp();');
    const derive = body.indexOf('INTO NEW."previousNumerator", NEW."previousDenominator"');
    expect(iso, '(a) no refusal above READ COMMITTED').toBeGreaterThan(-1);
    expect(lock, '(a) the lock is taken before the isolation is checked').toBeGreaterThan(iso);
    expect(stamp, '(b) createdAt is stamped BEFORE the lock — stamp order and lock order can disagree')
      .toBeGreaterThan(lock);
    expect(derive).toBeGreaterThan(stamp);
    expect(body, '(c) the table resolves through the caller’s search_path').toContain(
      'FROM "public"."platform_rates" p',
    );
    expect(body, 'the derivation order is not marginAt’s order').toContain(
      'ORDER BY p."effectiveFrom" DESC, p."createdAt" DESC',
    );
    // (c) EVERY function in the file is pinned — counted, not listed.
    const fns = (sqlOnly.match(/CREATE OR REPLACE FUNCTION/g) ?? []).length;
    const pinned = (
      sqlOnly.match(/\$fn\$ LANGUAGE plpgsql\s+SET search_path = pg_catalog, public, pg_temp;/g) ?? []
    ).length;
    expect(fns, 'the reader found no functions — this arm is measuring nothing').toBeGreaterThan(0);
    expect(pinned, '(c) a function resolves names through the caller’s search_path').toBe(fns);
    expect(sqlOnly, 'the $verify$ block does not assert the pins').toContain('n_pinned <> 3');
  });

  it('⚠️ THE BOUNDS CROSS-MULTIPLY IS `bigint` ON BOTH PAIRS — int4 overflowed', () => {
    // ROUND 5's FINDING: `5 * "marginDenominator"` is int4*int4, and `int4mul`
    // RAISES rather than widening. Measured on PG 16.15: 1500000000/1000000000
    // (exactly 1.5), 2000000000/500000000 (exactly 4.0), 2147483647/2147483647
    // and 429496730/429496730 (exactly 1.0) each aborted with
    // `ERROR: integer out of range` — SQLSTATE 22003 raised in `int4mul`, naming
    // NEITHER the constraint nor the column — while the exported TypeScript
    // mirror `isUsableMargin` returned `true` for every one of them.
    //
    // It was a false-REJECTION band only, provably: if `5*d` overflows then
    // `5d > int4max >= n`, so any such row would have satisfied the ceiling
    // anyway. But #178's bound was encoded twice in two places free to drift,
    // which is the defect ADMIN-4 exists to remove one layer up.
    expect(sqlOnly, 'the ceiling is int4 arithmetic again — it overflows on legal input')
      .not.toMatch(/\b5 \* "(margin|previous)Denominator"/);
    expect(sqlOnly).toContain('5::bigint * "marginDenominator"');
    expect(sqlOnly).toContain('5::bigint * "previousDenominator"');
  });

  it('⚠️ ROUND 6 — THE ACTOR MUST CONTAIN A LETTER OR DIGIT, by Unicode category through ICU — not an enumerated blank set', () => {
    // ROUND 5 enumerated a trim set and asserted its NAMED codepoints here —
    // an arm that could only ever test the codepoints the constraint already
    // listed. Round 6 measured 21 invisible or control code points ACCEPTED
    // as the only actor (chr(1), chr(27), chr(127), U+200E, U+00AD, U+2061,
    // U+E0020, …). The class is closed by INVERTING the rule: at least one
    // L*/Nd code point, classified by ICU (the Unicode Character Database),
    // not by the server's libc locale — under "C", `[[:alnum:]]` refuses é,
    // И and 王.
    //
    // ⚠️ SOURCE HALF ONLY. The behavioural half is the script's ACTOR sweep,
    // whose must-refuse set is DERIVED from Unicode general category by an
    // oracle that shares nothing with this spelling.
    const at = sqlOnly.indexOf('ADD CONSTRAINT "platform_rates_actor_present"');
    expect(at, 'the reader cannot find the actor constraint').toBeGreaterThan(-1);
    const check = sqlOnly.slice(at, sqlOnly.indexOf(');', at));
    expect(check, 'the actor rule is not "contains a letter or digit"').toContain("~ '[[:alnum:]]'");
    expect(check, 'the class is read through the server locale, not ICU — "C" refuses non-ASCII names')
      .toContain('COLLATE "und-x-icu"');
    expect(check, 'an enumerated trim set is back — it can only ever close instances').not.toMatch(/btrim/);
    expect(check, 'codepoints are being enumerated again').not.toMatch(/U&'/);
  });

  it('⚠️ THE TWO ENCODINGS OF #178’s BOUNDS ANSWER THE SAME LIST', () => {
    // ⚠️ THE CASES ARE READ FROM A FILE, NOT WRITTEN HERE, and the SQL half of
    // this gate (`scripts/check-platform-rates-invariants.sh`) reads the SAME
    // file. Widening a hand-written list closes instances; deriving BOTH sides
    // from one list closes the class — a case added there is answered by both
    // encodings or by neither, and the two can no longer drift silently.
    const cases = JSON.parse(
      readFileSync(join(__dirname, '..', '..', '..', '..', 'scripts', 'fixtures',
        'platform-rate-bounds-cases.json'), 'utf8'),
    ).cases as Array<{ id: string; n: number; d: number; usable: boolean }>;

    // POSITIVE CONTROL ON THE LIST ITSELF: an all-true or all-false list would
    // make this arm pass on a predicate that answered everything one way.
    expect(cases.length).toBeGreaterThan(10);
    expect(cases.filter((c) => c.usable).length).toBeGreaterThan(0);
    expect(cases.filter((c) => !c.usable).length).toBeGreaterThan(0);

    for (const c of cases) {
      expect(
        isUsableMargin({ id: c.id, marginNumerator: c.n, marginDenominator: c.d }),
        `${c.id}: isUsableMargin disagrees with the shared bounds list on ${c.n}/${c.d}`,
      ).toBe(c.usable);
    }
  });
});

describe('ADMIN-4 round 3 — the operation refuses, it does not merely document', () => {
  it('⚠️ `chargeMicroUsd` REFUSES an out-of-bounds margin from the public barrel', async () => {
    const ai = await import('../index');
    expect(() => ai.chargeMicroUsd(1000n, { id: 'x', marginNumerator: 1, marginDenominator: 2 })).toThrow(
      /out-of-bounds margin 1\/2/,
    );
    expect(() => ai.chargeMicroUsd(1000n, { id: 'x', marginNumerator: 100, marginDenominator: 1 })).toThrow();
    // NON-VACUITY: an in-bounds rate still computes.
    expect(ai.chargeMicroUsd(1000n, { id: 'x', marginNumerator: 3, marginDenominator: 2 })).toBe(1500n);
  });

  it('⚠️ TRUNCATE IS REFUSED — row triggers do not see it, and the prior art says so', () => {
    const sql = readFileSync(
      join(__dirname, '..', '..', '..', 'db', 'prisma', 'migrations',
        '20260909060000_admin4_platform_rate', 'migration.sql'),
      'utf8',
    );
    expect(sql, 'no TRUNCATE arm — measured: it emptied the table 2 rows to 0').toContain(
      'BEFORE TRUNCATE ON "platform_rates"',
    );
    expect(sql, 'no self-verify — `prisma migrate dev` cannot see triggers').toContain('$verify$');
    expect(sql, 'the verify block does not count the TRUNCATE arm').toContain('n_trig <> 4');
    // ⚠️ ROUND 4 — `regclass`, not `relname`. Without a namespace filter the
    // verify block counts same-named relations in OTHER schemas: measured, a
    // decoy `archive.platform_rates` made it count 4 while `public` had 3, and
    // it CERTIFIED a table that had lost its TRUNCATE arm.
    expect(sql, 'the verify block asks by name, not by regclass').toContain(
      "tgrelid = '\"platform_rates\"'::regclass",
    );
    // ⚠️ AND "EFFECTIVE IMMEDIATELY" MUST BE EXPRESSIBLE. Round 3's
    // clock_timestamp() stamp made every honest spelling of "now" refusable by
    // MICROSECONDS — measured on PG 16.13, `effectiveFrom = now()` refused by 9µs
    // — so the writer #178 calls for could not have set a rate at all. NULL is
    // the one spelling that cannot lose that race.
    expect(sql, 'NULL effectiveFrom does not mean "immediately"').toContain(
      'NEW."effectiveFrom" := NEW."createdAt"',
    );
    expect(sql, 'the actor may still be blank').toContain('platform_rates_actor_present');
    expect(sql, 'the PREVIOUS pair is unbounded').toContain('platform_rates_previous_bounds');
    expect(sql, 'createdAt uses transaction-start time, not statement time').toContain(
      'clock_timestamp()',
    );
  });
});
