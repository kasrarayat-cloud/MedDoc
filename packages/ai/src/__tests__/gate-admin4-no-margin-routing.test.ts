// @vitest-environment node
// ============================================================================
// ADMIN-4 ROUND 5 — `no_margin_rate` ROUTES TO `failed`, PROVED BY DRIVING IT.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE ARM THAT GUARDED THIS ROUTING WAS A 400-
// CHARACTER SOURCE WINDOW, AND THE WINDOW CONTAINED SOMETHING ELSE THAT
// SATISFIED IT.
//
// `gate-admin4-platform-rate.test.ts` read `billing-pipeline.ts` as text, found
// `result.decision.reason === 'no_margin_rate'`, sliced 400 characters forward
// and asserted the slice contained `charged: 'failed'`. Measured on the real
// file: the branch's own return sits at offset +70 — and the function's CATCH
// BLOCK's `charged: 'failed'` sits at offset +289, i.e. 111 characters INSIDE
// the same window. So the assertion was satisfied by
// `} catch (err) { return { charged: 'failed', … } }` WHATEVER the branch
// returned. Reverting the branch to round 1's exact defect — `charged:
// 'declined'` — left the whole `packages/ai` suite green and the arm titled
// "`no_margin_rate` must NOT route like `nothing_billable`" reporting PASS on
// code where it routed EXACTLY like `nothing_billable`.
//
// ⚠️ THE CLASS IS "A WINDOW ASSERTION THAT SOMETHING ELSE IN THE WINDOW CAN
// SATISFY", and no widening or narrowing of the window closes it — the answer
// is to stop asking the text and ask the FUNCTION. The old arm's stated reason
// for being a grep was that "`chargeVisitUsage` is not drivable here (its
// collaborators hit the database)". It is drivable; this file drives it. What
// the note was really about is that `commitVisitCharge` calls
// `assertProdDatabase()` as its first statement, so BOTH `@meddoc/db` and
// `@meddoc/db/guard` have to be stubbed, and the b8 harness stubs only the
// first.
//
// ⚠️ AND THE FIRST VERSION OF THIS PROBE PASSED VACUOUSLY. With `priceRate`
// missing from the stub, `chargeVisitUsage` landed in its own catch block and
// returned `{ charged: 'failed', detail: "Cannot read properties of undefined
// (reading 'findMany')" }` — the right verdict for the wrong reason, and
// indistinguishable from a pass unless the DETAIL is read. Every arm here
// asserts the `detail`/`reason` and not merely the `charged` verdict, and arm 4
// is the negative control that proves the catch block is NOT what answered.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

/** Every call the stub received, so "it never got that far" is assertable. */
const dbCalls: string[] = [];

/** What `platformRate.findMany` returns next. `[]` is an unconfigured platform
 *  — the whole subject of ADMIN-4. */
let platformRateRows: Array<{ id: string; marginNumerator: number; marginDenominator: number }> = [];

/** What the balance query returns next. Empty = a zero wallet. */
let balanceRows: Array<{ bucket: string; sum_micro: string; latest_balance: string }> = [];

const USAGE_AT = new Date('2026-08-12T00:00:00Z');

vi.mock('@meddoc/db/guard', () => ({
  __esModule: true,
  // The real guard refuses off production. Stubbing it is what makes the write
  // path drivable at all — and it is the ONE thing the b8 harness does not stub,
  // which is why its two existing drives both land in the catch block.
  assertProdDatabase: () => undefined,
}));

vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: {
      findMany: async () => {
        dbCalls.push('apiUsageEvent.findMany');
        return [
          {
            id: 'evt_1',
            provider: 'anthropic',
            modelName: 'claude-sonnet-5',
            unitsSource: 'vendor',
            timestamp: USAGE_AT,
            audioSeconds: null,
            inputTokens: 1000,
            outputTokens: null,
            cacheReadInputTokens: null,
            cacheCreationInputTokens: null,
          },
        ];
      },
    },
    priceRate: {
      findMany: async () => {
        dbCalls.push('priceRate.findMany');
        return [
          {
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
          },
        ];
      },
    },
    platformRate: {
      findMany: async () => {
        dbCalls.push('platformRate.findMany');
        return platformRateRows;
      },
    },
    // ⚠️ ROUND 6 — THE STUB ANSWERS BY SQL, NOT BY POSITION. `commitVisitCharge`
    // now asserts READ COMMITTED before its locks, and a stub that returned the
    // balance rows to EVERY raw query would hand that assertion a balance row
    // (no `level`) — the right refusal for the wrong reason.
    $queryRawUnsafe: async (sql: string) => {
      dbCalls.push('$queryRawUnsafe');
      if (sql.includes('transaction_isolation')) return [{ level: 'read committed' }];
      if (sql.includes('"ledger_entries"')) return balanceRows;
      throw new Error(`stub: unexpected raw SQL: ${sql.slice(0, 80)}`);
    },
    $executeRawUnsafe: async () => {
      dbCalls.push('$executeRawUnsafe');
      return 1;
    },
    $transaction: async (fn: (tx: unknown) => Promise<unknown>) => {
      dbCalls.push('$transaction');
      return fn(client);
    },
    ledgerEntry: {
      // Round 6's already-charged check. Honours the `where` it is given rather
      // than answering blindly, so a changed query shape cannot pass silently.
      findMany: async ({ where }: { where: { idempotencyKey?: { in?: string[] } } }) => {
        dbCalls.push('ledgerEntry.findMany');
        const keys = where?.idempotencyKey?.in;
        if (!Array.isArray(keys)) throw new Error('stub: ledgerEntry.findMany without idempotencyKey.in');
        return ledgerWrites
          .map((d, i) => ({ id: `ledger_${i + 1}`, key: d.idempotencyKey as string }))
          .filter((r) => keys.includes(r.key))
          .map((r) => ({ id: r.id }));
      },
      create: async ({ data }: { data: Record<string, unknown> }) => {
        dbCalls.push('ledgerEntry.create');
        ledgerWrites.push(data);
        return { id: `ledger_${ledgerWrites.length}` };
      },
    },
  };
  return { __esModule: true, default: client, prisma: client };
});

/** Every `ledger_entries` row the stub was asked to write. */
const ledgerWrites: Array<Record<string, unknown>> = [];

import { chargeVisitUsage } from '../billing-pipeline';

const FLAG = 'BILLING_ENFORCED';

beforeEach(() => {
  dbCalls.length = 0;
  ledgerWrites.length = 0;
  platformRateRows = [];
  balanceRows = [];
  vi.stubEnv(FLAG, 'true');
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('ADMIN-4 round 5 — the routing is DRIVEN, not grepped', () => {
  it('⚠️ NO CONFIGURED MARGIN -> `failed`, WITH the ADMIN-4 detail', async () => {
    // The defect this replaces: `charged: 'declined'` here is byte-identical
    // routing to a genuinely free visit. `worker.ts` logs `outcome:
    // charge.charged` and NOT `reason` for everything except `failed`, so a
    // platform with no configured margin would bill nothing forever and leave
    // one line indistinguishable from a mocked run.
    const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v1' });

    expect(out.charged, '`no_margin_rate` no longer routes to `failed`').toBe('failed');
    // ⚠️ THE DETAIL IS THE LOAD-BEARING ASSERTION, NOT THE VERDICT. The
    // function's own catch block ALSO returns `charged: 'failed'` — that is the
    // exact ambiguity the source-window arm could not see through, and a probe
    // that asserted only the verdict would inherit it verbatim.
    expect(out).toEqual({
      charged: 'failed',
      detail: 'no platform margin configured at the usage instant (ADMIN-4)',
    });
    // And it got there by READING the empty rate table, not by throwing on the
    // way. An exception before this point would produce the same verdict.
    expect(dbCalls).toContain('platformRate.findMany');
  });

  it('⚠️ NON-VACUITY — the SAME input with a margin configured WRITES', async () => {
    // Without this the arm above passes on any breakage that fails everything,
    // which is the failure mode a fail-closed change is most likely to
    // introduce — and it is also the positive control that the stub set is
    // complete enough to reach the ledger at all.
    platformRateRows = [{ id: 'pr_74', marginNumerator: 7, marginDenominator: 4 }];
    balanceRows = [{ bucket: 'paid', sum_micro: '5000', latest_balance: '5000' }];

    const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v1' });

    expect(out.charged, 'a configured margin still did not charge').toBe('written');
    if (out.charged !== 'written') return;
    // 1000 µ$ of cost at 7/4 — the ROW's rate, not a compiled-in 3/2.
    expect(out.chargeMicroUsd).toBe(1750n);
    expect(ledgerWrites).toHaveLength(1);
    expect(ledgerWrites[0]!.pricing).toMatchObject({
      multiplier: '7/4',
      platformRateId: 'pr_74',
      costMicroUsd: '1000',
      chargeMicroUsd: '1750',
    });
  });

  it('⚠️ `nothing_billable` STILL routes to `declined` — the two must not merge', async () => {
    // The distinction is the entire point: `declined` is a DECISION about a real
    // visit ("we looked, there is nothing to charge") and B9 must not chase it.
    // An arm that only checked `no_margin_rate -> failed` would stay green on a
    // change that routed EVERYTHING to `failed`, which destroys the same
    // distinction from the other side.
    platformRateRows = [{ id: 'pr_32', marginNumerator: 3, marginDenominator: 2 }];
    const { prisma } = (await import('@meddoc/db')) as unknown as {
      prisma: { apiUsageEvent: { findMany: () => Promise<unknown[]> } };
    };
    const restore = prisma.apiUsageEvent.findMany;
    prisma.apiUsageEvent.findMany = async () => [];
    try {
      const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v1' });
      expect(out).toEqual({ charged: 'declined', reason: 'nothing_billable' });
    } finally {
      prisma.apiUsageEvent.findMany = restore;
    }
  });

  it('⚠️ NEGATIVE CONTROL — a thrown collaborator ALSO yields `failed`, and the two are told apart by `detail`', async () => {
    // ⚠️ THIS ARM IS WHY ARM 1 ASSERTS THE DETAIL. The catch block's verdict is
    // `failed` too, so `charged === 'failed'` alone cannot distinguish "the
    // platform has no margin" from "the database exploded" — which is precisely
    // how the 400-character source window came to be satisfied by a catch block
    // 111 characters inside it.
    const { prisma } = (await import('@meddoc/db')) as unknown as {
      prisma: { platformRate: { findMany: () => Promise<unknown[]> } };
    };
    const restore = prisma.platformRate.findMany;
    prisma.platformRate.findMany = async () => {
      throw new Error('boom from the rate table');
    };
    try {
      const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v1' });
      expect(out.charged).toBe('failed');
      expect(out).toEqual({ charged: 'failed', detail: 'boom from the rate table' });
      // …and it is NOT the ADMIN-4 detail. If these two ever produce the same
      // object, arm 1 has stopped measuring anything.
      expect(out).not.toEqual({
        charged: 'failed',
        detail: 'no platform margin configured at the usage instant (ADMIN-4)',
      });
    } finally {
      prisma.platformRate.findMany = restore;
    }
  });

  it('⚠️ THE FLAG STILL GATES EVERYTHING — off means nothing is read', async () => {
    // The shipped default. Asserted as an ABSENCE of database calls, because a
    // seam that read and then discarded the answer would satisfy a
    // return-value assertion perfectly while doing money work on every visit.
    vi.stubEnv(FLAG, 'false');
    const out = await chargeVisitUsage({ practiceId: 'p1', visitId: 'v1' });
    expect(out).toEqual({ charged: 'skipped_not_enforced' });
    expect(dbCalls).toEqual([]);
  });
});
