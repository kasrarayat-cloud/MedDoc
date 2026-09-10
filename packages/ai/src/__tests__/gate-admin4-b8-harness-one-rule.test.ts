// ============================================================================
// ADMIN-4 ROUND 6 — THE B8 QA HARNESS PRICES WITH THE ONE RULE, COST INCLUDED.
// ----------------------------------------------------------------------------
// `apps/transcribe-md/scripts/qa/b8-failure-cost-on-qa.ts` computes the
// wouldChargeMicroUsd it expects the failure-cost observer to log, and the
// host asserter compares the two as EXACT STRINGS. Round 5 moved its margin
// onto the real pricer and wrote "Both are now taken from the real pricer. One
// rule, one reader." — but the COST half stayed a second, truncating formula.
//
// ⚠️ WHY THIS ARM IS A SOURCE READ, SAID PLAINLY. The harness is a QA-stack
// script whose module body runs `main()` against a live database; it cannot be
// imported and driven here. So this arm does two things and claims no more:
//   1. DRIVES the arithmetic, to show the two rules genuinely disagree at a
//      rate with a remainder — the reason the source must not hold its own;
//   2. reads the expectation function's EXECUTABLE text (comments stripped)
//      and requires the pricer to be the only rule in it.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { priceUsageRows } from '../billing-charge';
import type { PriceRateRow } from '../price-table';

const HARNESS = join(
  __dirname, '..', '..', '..', '..', 'apps', 'transcribe-md', 'scripts', 'qa', 'b8-failure-cost-on-qa.ts',
);

const stripTs = (src: string) =>
  src
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');

function expectationFn(): string {
  const src = stripTs(readFileSync(HARNESS, 'utf8'));
  const start = src.indexOf('async function expectedChargeForSeededRow(');
  expect(start, 'the reader cannot find the harness expectation — this arm measures nothing').toBeGreaterThan(-1);
  const end = src.indexOf('\n}\n', start);
  expect(end).toBeGreaterThan(start);
  return src.slice(start, end);
}

describe('ADMIN-4 round 6 — the b8 harness has ONE pricing rule', () => {
  it('⚠️ WHY: the truncating formula and the pricer DISAGREE at a rate with a remainder', async () => {
    const rate = (unitType: 'tokens_input' | 'tokens_output', rateMicroUsd: bigint): PriceRateRow => ({
      id: `r_${unitType}`, provider: 'anthropic', modelName: 'claude-sonnet-5', deliveryMode: 'not_applicable',
      unitType, rateMicroUsd, unitQuantity: 1_000_000n, effectiveFrom: new Date('2026-08-04T00:00:00Z'),
      effectiveTo: null, provenance: 'published', sourceUrl: 'https://example.test', sourceReadAt: new Date('2026-08-04T00:00:00Z'),
    });
    const d = await priceUsageRows(
      [{
        id: 'e', provider: 'anthropic', modelName: 'claude-sonnet-5', unitsSource: 'vendor',
        createdAt: new Date('2026-08-12T00:00:00Z'), audioSeconds: null, inputTokens: 1000, outputTokens: 500,
        cacheReadInputTokens: null, cacheCreationInputTokens: null,
      }],
      async ({ unitType }) => (unitType === 'tokens_input' ? rate('tokens_input', 2_000_500n) : rate('tokens_output', 10_000_000n)),
      async () => ({ id: 'pr_32', marginNumerator: 3, marginDenominator: 2 }),
    );
    expect(d.charge).toBe(true);
    if (!d.charge) return;
    // The old harness shape, verbatim arithmetic: truncating per component.
    const truncatingCost = (1000n * 2_000_500n) / 1_000_000n + (500n * 10_000_000n) / 1_000_000n;
    expect(truncatingCost).toBe(7000n);
    expect(d.costMicroUsd, 'the pricer rounds half-up per component').toBe(7001n);
    expect(d.chargeMicroUsd).toBe(10_502n);
  });

  it('⚠️ the expectation is `priceUsageRows` — no second cost or margin rule in the function', () => {
    const fn = expectationFn();
    expect(fn, 'the harness no longer asks the real pricer').toContain('priceUsageRows(');
    expect(fn, 'a second COST rule — dividing by unitQuantity in the harness').not.toMatch(/unitQuantity\s*[;)+\n]/);
    expect(fn, 'a second COST rule').not.toMatch(/\/\s*(input|output)\.unitQuantity/);
    expect(fn, 'a second MARGIN rule — the harness applies the margin itself').not.toContain('chargeMicroUsd(');
    expect(fn, 'a second MARGIN rule — the harness reads the margin itself').not.toContain('marginAt(');
  });
});
