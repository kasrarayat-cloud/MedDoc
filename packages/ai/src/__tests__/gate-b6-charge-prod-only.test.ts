// ============================================================================
// GATE — FOUNDATION B6
// ----------------------------------------------------------------------------
// RELAY B6's gate, verbatim:
//
//   "the writer REFUSES ON THE LIVE QA STACK, demonstrated, not asserted (F4).
//    STRIPE_SECRET_KEY is added to scripts/check-qa-mock-posture.sh KEYS in the
//    same commit, and the QA compose entry does not use ${STRIPE_SECRET_KEY:-…}.
//    Rounding rule stated and tested at the boundary."
//
// Six arms. The one that carries the item is arm 5 — the demonstrated refusal —
// and it is the only one that needs a live database, so it is the only one that
// can skip. It says so loudly when it does, because an arm that quietly
// vanishes is the "permitted zero read as a pass" defect ruling 86(a) closed.
//
// ⚠️ WHAT THIS GATE CANNOT DO, STATED SO NOBODY READS ITS GREEN TOO WIDELY:
// it can never watch `commitVisitCharge` actually WRITE a row, because F4's
// whole requirement is that the function refuses everywhere a test is allowed
// to run. That is why `priceUsageRows` is a separate, pure function and why
// most of the arms below point at it. The arithmetic is provable; the effect is
// only provable in the negative. Splitting them is what stops "it refuses" from
// being the only true statement about B6.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  BILLABLE_PROVIDERS,
  componentsOf,
  deliveryModeFor,
  priceUsageRows,
  visitChargeKey,
  type ChargeableUsageRow,
} from '../billing-charge';
import { chargeMicroUsd, divRoundHalfUp, type PriceRateRow } from '../price-table';

const ROOT = join(__dirname, '../../../..');

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

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

function rate(rateMicroUsd: bigint, unitQuantity: bigint, id = 'rate_1'): PriceRateRow {
  return {
    id,
    provider: 'anthropic',
    modelName: 'claude-sonnet-5',
    deliveryMode: 'not_applicable',
    unitType: 'tokens_input',
    rateMicroUsd,
    unitQuantity,
    effectiveFrom: new Date('2026-08-04T00:00:00Z'),
    effectiveTo: null,
    provenance: 'published',
    sourceUrl: 'https://example.test/pricing',
    sourceReadAt: new Date('2026-08-04T00:00:00Z'),
  };
}

/** A lookup that prices everything at 1 µ$ per unit — so a component's cost
 *  equals its unit count and the arithmetic under test is legible. */
const priceEverything = async () => rate(1n, 1n);
/** A lookup that prices nothing — ruling 80(c)'s `null`. */
const priceNothing = async () => null;

// ---------------------------------------------------------------------------
// 1. THE ROUNDING RULE, AT THE BOUNDARY — the gate's own words
// ---------------------------------------------------------------------------

describe('B6 (1) — charge = cost × 3 / 2, half-up, at the boundary', () => {
  it('rounds half-up on every odd cost, which is where the boundary lives', () => {
    // cost × 3 / 2 lands exactly on .5 for every ODD cost, so the odd values
    // ARE the boundary cases — there is no other input that can round.
    expect(chargeMicroUsd(0n)).toBe(0n); //  0   ->  0
    expect(chargeMicroUsd(1n)).toBe(2n); //  1.5 ->  2   (half-up, not 1)
    expect(chargeMicroUsd(2n)).toBe(3n); //  3   ->  3   (exact)
    expect(chargeMicroUsd(3n)).toBe(5n); //  4.5 ->  5   (half-up, not 4)
    expect(chargeMicroUsd(4n)).toBe(6n); //  6   ->  6   (exact)
    expect(chargeMicroUsd(5n)).toBe(8n); //  7.5 ->  8   (half-up, not 7)
  });

  it('is `× 3 / 2` and NOT `* 1.5`, above the float-safe integer range', () => {
    // ⚠️ THE ASSERTION THAT ACTUALLY DISTINGUISHES THE TWO IMPLEMENTATIONS.
    // Below 2^53 they agree on every input, so a test using small numbers would
    // pass against the float form and prove nothing about SPEC §4.4's rule.
    // At 2^53+1 micro-dollars the Number path loses the low bit.
    const big = 9_007_199_254_740_993n; // 2^53 + 1
    expect(chargeMicroUsd(big)).toBe(13_510_798_882_111_490n);
    // What `Math.round(cost * 1.5)` would have produced — a different number.
    expect(BigInt(Math.round(Number(big) * 1.5))).not.toBe(chargeMicroUsd(big));
  });

  it('inherits half-up from divRoundHalfUp rather than reimplementing it', () => {
    for (const cost of [0n, 1n, 7n, 999n, 1_000_001n]) {
      expect(chargeMicroUsd(cost)).toBe(divRoundHalfUp(cost * 3n, 2n));
    }
  });
});

// ---------------------------------------------------------------------------
// 2. SUM THE COSTS, MULTIPLY ONCE — the over-bill nobody would see
// ---------------------------------------------------------------------------

describe('B6 (2) — one rounding step on the total, never one per component', () => {
  it('charges the summed cost, not the sum of per-component charges', async () => {
    // Two components of 1 µ$ each. Sum-then-charge: charge(2) = 3.
    // Charge-then-sum:  charge(1) + charge(1) = 2 + 2 = 4.
    // The second over-bills by 33% on this input and biases upward on every
    // input, growing with the number of pipeline stages.
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 1, outputTokens: 1 })],
      priceEverything,
    );
    expect(decision.charge).toBe(true);
    if (!decision.charge) return;
    expect(decision.costMicroUsd).toBe(2n);
    expect(decision.chargeMicroUsd).toBe(3n);
    expect(decision.chargeMicroUsd).not.toBe(chargeMicroUsd(1n) + chargeMicroUsd(1n));
  });

  it('the two orderings genuinely differ (positive control)', () => {
    // Without this, the assertion above could be satisfied by an input where
    // both orderings agree — which is most inputs.
    expect(chargeMicroUsd(1n) + chargeMicroUsd(1n)).toBe(4n);
    expect(chargeMicroUsd(2n)).toBe(3n);
  });
});

// ---------------------------------------------------------------------------
// 3. WHAT A `null` RATE MEANS — ruling 80(c), answered
// ---------------------------------------------------------------------------

describe('B6 (3) — an unpriceable component declines the WHOLE charge', () => {
  it('refuses rather than charging zero for the unpriced part', async () => {
    const decision = await priceUsageRows([usageRow({ inputTokens: 1000 })], priceNothing);
    expect(decision.charge).toBe(false);
    if (decision.charge) return;
    expect(decision.reason).toBe('unpriced');
    expect(decision.unpriced).toHaveLength(1);
    expect(decision.unpriced[0]!.reason).toBe('no_rate_for_key_at_instant');
  });

  it('refuses the whole visit when only SOME components price', async () => {
    // ⚠️ THE ARM THAT MATTERS MOST. A partial charge is the failure that is
    // invisible: the doctor gets a bill, the bill looks plausible, and it is
    // short by whatever the unpriced stage cost. Nothing on the row says a
    // component was dropped.
    const lookup = async (a: { unitType: string }) =>
      a.unitType === 'tokens_input' ? rate(1n, 1n) : null;
    const decision = await priceUsageRows(
      [usageRow({ inputTokens: 100, outputTokens: 50 })],
      lookup as never,
    );
    expect(decision.charge).toBe(false);
    if (decision.charge) return;
    expect(decision.reason).toBe('unpriced');
    // And the declined amount is REPORTED, not silently zero — so an operator
    // can see the size of what is being withheld.
    expect(decision.pricedSoFarMicroUsd).toBe(100n);
  });

  it('distinguishes "nothing billable" from "unpriced"', async () => {
    // A mocked run is not a gap in our knowledge and B9 must not chase it.
    const decision = await priceUsageRows(
      [usageRow({ unitsSource: 'mock', inputTokens: 1000 })],
      priceEverything,
    );
    expect(decision.charge).toBe(false);
    if (decision.charge) return;
    expect(decision.reason).toBe('nothing_billable');
    expect(decision.unpriced).toHaveLength(0);
  });

  it('a billable row with no model name is a GAP, not a skip', async () => {
    const decision = await priceUsageRows(
      [usageRow({ modelName: null, inputTokens: 10 })],
      priceEverything,
    );
    expect(decision.charge).toBe(false);
    if (decision.charge) return;
    expect(decision.unpriced[0]!.reason).toBe('no_model_name');
  });

  it('prices each row at ITS OWN createdAt, never at read time', async () => {
    const seen: Date[] = [];
    const lookup = async (a: { at: Date }) => {
      seen.push(a.at);
      return rate(1n, 1n);
    };
    const at = new Date('2026-08-05T12:00:00Z');
    await priceUsageRows([usageRow({ createdAt: at, inputTokens: 1 })], lookup as never);
    expect(seen).toEqual([at]);
  });
});

// ---------------------------------------------------------------------------
// 4. THE WATCHED SET — what is billable, and what is deliberately not
// ---------------------------------------------------------------------------

describe('B6 (4) — GATE 0.5: Resend is not a billing input', () => {
  it('excludes resend from BILLABLE_PROVIDERS by name', () => {
    // An absence is invisible to a behavioural test (ruling 84(a)), so it is
    // pinned on the constant. Production holds 219 Resend rows; a writer that
    // billed "every vendor row" would charge all of them.
    expect(BILLABLE_PROVIDERS).not.toContain('resend');
    expect([...BILLABLE_PROVIDERS].sort()).toEqual(['anthropic', 'deepgram', 'openai']);
  });

  it('charges nothing for a resend row even when a rate exists', async () => {
    const decision = await priceUsageRows(
      [usageRow({ provider: 'resend', modelName: 'resend', inputTokens: 5 })],
      priceEverything,
    );
    expect(decision.charge).toBe(false);
    if (decision.charge) return;
    expect(decision.reason).toBe('nothing_billable');
  });

  it('drops zero-quantity components instead of demanding a rate for them', () => {
    const parts = componentsOf(usageRow({ inputTokens: 10, outputTokens: 0 }));
    expect(parts.map((p) => p.unitType)).toEqual(['tokens_input']);
  });

  it('derives deliveryMode: audio is pre_recorded, tokens are not_applicable', () => {
    // Ruling 81(a): no streaming Deepgram call site exists on this stack. The
    // price table holds BOTH modes for nova-3 at 7700 and 4800 µ$/min, so this
    // is a 1.6× difference in the bill, not a label.
    expect(deliveryModeFor('deepgram', 'audio_minutes')).toBe('pre_recorded');
    expect(deliveryModeFor('openai', 'audio_minutes')).toBe('pre_recorded');
    expect(deliveryModeFor('anthropic', 'tokens_input')).toBe('not_applicable');
  });

  it('ruling 81(a) still holds at its source — no streaming Deepgram call site', () => {
    // deliveryModeFor derives from a recorded FACT, so the fact is re-checked
    // rather than trusted. If a live/streaming call site is ever added, audio
    // silently prices as pre_recorded and under-charges by a third.
    const src = readFileSync(join(ROOT, 'packages/ai/src/deepgram-batch.ts'), 'utf8');
    expect(src).not.toMatch(/\blive\s*\(|listen\.live|transcribeLive/);
  });
});

// ---------------------------------------------------------------------------
// 5. THE PROD-ONLY REFUSAL — F4, DEMONSTRATED
// ---------------------------------------------------------------------------

describe('B6 (5) — the writer refuses anywhere but production', () => {
  it('the guard is NOT the negation of assertNonProdDatabase', async () => {
    // ⚠️ THE FAIL-OPEN THIS ARM EXISTS TO FORBID. `!checkNonProdDb(x).ok` reads
    // like the mirror and permits FOUR situations that are not production:
    // unset, unparseable, an unmarked name, and the prod host. A billing writer
    // that charges whenever it cannot tell where it is pointing is the shape
    // this programme has already closed three times.
    const { checkNonProdDb, checkProdDb } = await import('@meddoc/db/guard');
    for (const name of ['staging', 'meddoc_shadow', 'postgres', '']) {
      expect(checkNonProdDb(name).ok).toBe(false); // not confirmed non-prod
      expect(checkProdDb(name).ok).toBe(false); // and NOT therefore prod
    }
    // The two are complements on nothing. Only `meddoc` confirms production;
    // only a marker name confirms non-production.
    expect(checkProdDb('meddoc').ok).toBe(true);
    expect(checkNonProdDb('meddoc').ok).toBe(false);
    expect(checkProdDb('meddoc_qa_test').ok).toBe(false);
    expect(checkNonProdDb('meddoc_qa_test').ok).toBe(true);
  });

  it('refuses the QA database name by demonstration, with the reason', async () => {
    const { assertProdDatabase } = await import('@meddoc/db/guard');
    expect(() =>
      assertProdDatabase('postgresql://u:p@meddoc-qa-postgres-1:5432/meddoc_qa_test'),
    ).toThrow(/qa\/test\/e2e\/ci marker/);
  });

  it('refuses an unset and an unparseable DATABASE_URL', async () => {
    const { assertProdDatabase } = await import('@meddoc/db/guard');
    expect(() => assertProdDatabase(undefined)).toThrow(/DATABASE_URL is not set/);
    expect(() => assertProdDatabase('not-a-url')).toThrow(/not a parseable/);
  });

  it('accepts ONLY the production database name', async () => {
    const { assertProdDatabase } = await import('@meddoc/db/guard');
    expect(assertProdDatabase('postgresql://u:p@postgres:5432/meddoc').database).toBe('meddoc');
  });

  it('assertProdDatabase() is the FIRST statement of commitVisitCharge', () => {
    // A refusal placed after the pricing would still refuse, but it would have
    // already read the database on the way there. Asserted on the source
    // because there is no way to observe statement order behaviourally from
    // outside a function that always throws.
    const src = readFileSync(join(ROOT, 'packages/ai/src/billing-charge.ts'), 'utf8');
    const body = src.slice(src.indexOf('export async function commitVisitCharge'));
    const firstStatement = body.slice(body.indexOf('{') + 1).trim().split('\n')[0]!.trim();
    expect(firstStatement).toBe('assertProdDatabase();');
  });
});

// ---------------------------------------------------------------------------
// 6. THE LEDGER ROW'S SHAPE — what the writer sends, and what it must not
// ---------------------------------------------------------------------------

describe('B6 (6) — the row the writer builds', () => {
  const src = readFileSync(join(ROOT, 'packages/ai/src/billing-charge.ts'), 'utf8');

  it('writes a NEGATIVE amount, matching ledger_entries_kind_sign', () => {
    expect(src).toContain('amountMicroUsd: -decision.chargeMicroUsd');
    expect(src).toContain("kind: 'usage'");
  });

  it('does NOT send balanceAfter or seq — ruling 89(d) says they are ignored', () => {
    // A caller-supplied value is not validated, it is silently discarded. So
    // sending one is a way to believe something false about the row.
    const create = src.slice(src.indexOf('prisma.ledgerEntry.create'));
    expect(create).not.toMatch(/\bbalanceAfter\s*:/);
    expect(create).not.toMatch(/\bseq\s*:/);
  });

  it('carries the price snapshot SPEC §2.2 requires, by rate id', () => {
    expect(src).toContain('rateId: p.rateId');
    expect(src).toContain('pricing:');
  });

  it('keys idempotency on the visit, so a retry cannot double-charge', () => {
    expect(visitChargeKey('abc')).toBe('usage:visit:abc');
    expect(src).toContain('idempotencyKey: visitChargeKey(args.visitId)');
  });

  it('the money never becomes a Number anywhere in this module', () => {
    // GATE 0.4: no float touches the ledger. `Math.round` on a cents float is
    // the shape SPEC §4.4 forbids by name.
    expect(src).not.toMatch(/Math\.round\([^)]*(cost|charge|micro)/i);
    expect(src).not.toMatch(/\*\s*1\.5/);
    expect(src).not.toMatch(/Number\((cost|charge)/);
  });
});

// ---------------------------------------------------------------------------
// 7. STRIPE_SECRET_KEY joined the posture check, in this commit
// ---------------------------------------------------------------------------

describe('B6 (7) — the second of F4s two conditions', () => {
  it('STRIPE_SECRET_KEY is in check-qa-mock-posture.sh KEYS', () => {
    const sh = readFileSync(join(ROOT, 'scripts/check-qa-mock-posture.sh'), 'utf8');
    const keysLine = sh.split('\n').find((l) => l.startsWith('KEYS='))!;
    expect(keysLine).toContain('STRIPE_SECRET_KEY');
  });

  it('no compose file introduces a ${STRIPE_SECRET_KEY:-…} default', () => {
    // The `:-` form inherits the PRODUCTION value from the shared .env — the
    // exact mechanism that put 298 real Anthropic calls through the "isolated"
    // QA stack. Checked now, while the answer is trivially zero, so that B7
    // adding the variable has to argue with this line.
    for (const f of ['docker-compose.yml', 'docker-compose.qa.yml']) {
      const text = readFileSync(join(ROOT, f), 'utf8');
      expect(text).not.toMatch(/\$\{STRIPE_SECRET_KEY:-/);
    }
  });
});
