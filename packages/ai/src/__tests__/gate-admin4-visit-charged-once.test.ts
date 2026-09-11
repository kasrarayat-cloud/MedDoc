// @vitest-environment node
// ============================================================================
// ADMIN-4 ROUND 6 — ONE USAGE CHARGE PER VISIT, PROVED BY DRIVING THE WRITER.
// ----------------------------------------------------------------------------
// ⚠️ THE DEFECT, MEASURED BY THE ROUND-6 PASS AGAINST THE REAL B5 DDL:
//
//   a visit costs 4500 µ$ at 3/2 → charge 6750, drawn entirely from `promo`
//     (the wallet holds promo 1,000,000 and paid 1,000,000)  key …:V:promo
//   other visits spend promo to 0
//   the doctor presses Try again on the still-READY visit; the worker has no
//     READY short-circuit, so it reaches the charge again
//   the split now draws `paid:6750`                           key …:V:paid
//   → a DIFFERENT key, accepted by the unique index. 13 500 µ$ for one visit.
//
// `visitChargeKey`'s own comment said "Partial double-charging is not
// reachable". It was reachable whenever the retry's bucket set did not overlap
// the first run's, and nothing in the schema refuses it per visit.
//
// ⚠️ THE STUB BELOW IS FAITHFUL WHERE FAITHFULNESS IS THE POINT, and each such
// place is asserted rather than assumed:
//   · `ledgerEntry.create` enforces the UNIQUE `idempotencyKey` exactly as
//     `ledger_entries_idempotencyKey_key` does — so the arm can show the index
//     alone admits the disjoint key (the finding's mechanism), and a same-key
//     replay is refused (the index still works);
//   · `seq`/`balanceAfter` are derived per (practice, bucket) like the trigger,
//     and the balance query is answered FROM THE LEDGER, so "other visits drained
//     promo" is a real ledger row, not a number poked into a stub;
//   · `platformRate.findMany` honours `where.effectiveFrom.lte`, `orderBy` and
//     `take` — round 6 also found that a stub ignoring `where` hid a wall-clock
//     read in `marginAt`.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type Bucket = 'paid' | 'promo';
interface LedgerRow {
  id: string;
  practiceId: string;
  bucket: Bucket;
  kind: string;
  amountMicroUsd: bigint;
  idempotencyKey: string | null;
  seq: number;
  balanceAfter: bigint;
}

const ledger: LedgerRow[] = [];
const calls: string[] = [];
let isolation = 'read committed';
let platformRateRows: Array<{
  id: string;
  marginNumerator: number;
  marginDenominator: number;
  effectiveFrom: Date;
  createdAt: Date;
}> = [];
let usageEvents: Array<Record<string, unknown>> = [];

/** The B5 insert, as the trigger and the unique index behave. */
function insertLedger(data: {
  practiceId: string;
  bucket: Bucket;
  kind: string;
  amountMicroUsd: bigint;
  idempotencyKey: string | null;
}): LedgerRow {
  if (data.idempotencyKey !== null && ledger.some((r) => r.idempotencyKey === data.idempotencyKey)) {
    throw new Error(
      'duplicate key value violates unique constraint "ledger_entries_idempotencyKey_key"',
    );
  }
  const prev = ledger.filter((r) => r.practiceId === data.practiceId && r.bucket === data.bucket).at(-1);
  const row: LedgerRow = {
    id: `led_${ledger.length + 1}`,
    ...data,
    seq: (prev?.seq ?? 0) + 1,
    balanceAfter: (prev?.balanceAfter ?? 0n) + data.amountMicroUsd,
  };
  ledger.push(row);
  return row;
}

vi.mock('@meddoc/db/guard', () => ({ __esModule: true, assertProdDatabase: () => undefined }));

vi.mock('@meddoc/db', () => {
  const client = {
    apiUsageEvent: {
      findMany: async ({ where }: { where: { visitId: string } }) =>
        usageEvents.filter((e) => e.visitId === where.visitId),
    },
    priceRate: {
      findMany: async () => [
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
        where: { effectiveFrom: { lte: Date } };
        take: number;
      }) => {
        const lte = args.where.effectiveFrom.lte;
        return platformRateRows
          .filter((r) => r.effectiveFrom <= lte)
          .sort(
            (a, b) =>
              b.effectiveFrom.getTime() - a.effectiveFrom.getTime() ||
              b.createdAt.getTime() - a.createdAt.getTime(),
          )
          .slice(0, args.take)
          .map(({ id, marginNumerator, marginDenominator }) => ({ id, marginNumerator, marginDenominator }));
      },
    },
    $queryRawUnsafe: async (sql: string, ...values: unknown[]) => {
      if (sql.includes('transaction_isolation')) {
        calls.push('isolation');
        return [{ level: isolation }];
      }
      if (sql.includes('FROM "ledger_entries" e1')) {
        calls.push('balance-read');
        const practiceId = values[0] as string;
        const out: Array<{ bucket: string; sum_micro: string; latest_balance: string }> = [];
        for (const bucket of ['paid', 'promo'] as const) {
          const rows = ledger.filter((r) => r.practiceId === practiceId && r.bucket === bucket);
          if (rows.length === 0) continue;
          out.push({
            bucket,
            sum_micro: String(rows.reduce((s, r) => s + r.amountMicroUsd, 0n)),
            latest_balance: String(rows.at(-1)!.balanceAfter),
          });
        }
        return out;
      }
      throw new Error(`stub: unexpected raw SQL: ${sql.slice(0, 80)}`);
    },
    $executeRawUnsafe: async (sql: string, ...values: unknown[]) => {
      if (!sql.includes('pg_advisory_xact_lock')) throw new Error(`stub: unexpected exec: ${sql}`);
      calls.push(`lock:${values.join('|')}`);
      return 1;
    },
    $transaction: async (fn: (tx: unknown) => Promise<unknown>) => {
      // Rollback on throw, like the database — a refusal must leave nothing.
      const mark = ledger.length;
      try {
        return await fn(client);
      } catch (err) {
        ledger.length = mark;
        throw err;
      }
    },
    ledgerEntry: {
      findMany: async ({ where }: { where: { idempotencyKey?: { in?: string[] } } }) => {
        calls.push('ledgerEntry.findMany');
        const keys = where?.idempotencyKey?.in;
        if (!Array.isArray(keys)) throw new Error('stub: ledgerEntry.findMany without idempotencyKey.in');
        return ledger.filter((r) => r.idempotencyKey !== null && keys.includes(r.idempotencyKey)).map((r) => ({ id: r.id }));
      },
      create: async ({ data }: { data: Record<string, unknown> }) => {
        calls.push('ledgerEntry.create');
        const row = insertLedger({
          practiceId: data.practiceId as string,
          bucket: data.bucket as Bucket,
          kind: data.kind as string,
          amountMicroUsd: data.amountMicroUsd as bigint,
          idempotencyKey: (data.idempotencyKey as string | null) ?? null,
        });
        return { id: row.id };
      },
    },
  };
  return { __esModule: true, default: client, prisma: client };
});

import { LEDGER_BUCKETS, DRAW_ORDER } from '../billing-buckets';
import {
  commitVisitCharge,
  visitChargeKey,
  visitUsageKeys,
  VISIT_CHARGE_LOCK_NAMESPACE,
  type ChargeableUsageRow,
} from '../billing-charge';
import { chargeVisitUsage } from '../billing-pipeline';

const PR_32 = {
  id: 'pr_32',
  marginNumerator: 3,
  marginDenominator: 2,
  effectiveFrom: new Date('2026-08-01T00:00:00Z'),
  createdAt: new Date('2026-08-01T00:00:00Z'),
};

function usage(id: string, at: string, inputTokens: number): ChargeableUsageRow {
  return {
    id,
    provider: 'anthropic',
    modelName: 'claude-sonnet-5',
    unitsSource: 'vendor',
    createdAt: new Date(at),
    audioSeconds: null,
    inputTokens,
    outputTokens: null,
    cacheReadInputTokens: null,
    cacheCreationInputTokens: null,
  };
}

const grant = (practiceId: string, bucket: Bucket, amount: bigint, tag = '') =>
  insertLedger({ practiceId, bucket, kind: bucket === 'promo' ? 'grant' : 'topup', amountMicroUsd: amount, idempotencyKey: `seed:${practiceId}:${bucket}${tag}` });

/** Everything this visit was debited, by the keys the writer uses. */
const debitedFor = (visitId: string) =>
  -ledger
    .filter((r) => r.kind === 'usage' && r.idempotencyKey?.startsWith(`usage:visit:${visitId}:`))
    .reduce((s, r) => s + r.amountMicroUsd, 0n);
const usageRowsFor = (visitId: string) =>
  ledger.filter((r) => r.kind === 'usage' && r.idempotencyKey?.startsWith(`usage:visit:${visitId}:`));

const ROWS_V = [usage('evt_v1', '2026-08-12T00:00:00Z', 4500)];

beforeEach(() => {
  ledger.length = 0;
  calls.length = 0;
  isolation = 'read committed';
  platformRateRows = [PR_32];
  usageEvents = [];
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('ADMIN-4 round 6 — the stub is faithful where it has to be (controls first)', () => {
  it('the unique index ALONE admits the disjoint-bucket key — the finding’s mechanism', () => {
    // If this arm ever fails, the stub stopped modelling B5 and every arm below
    // is measuring a different database.
    insertLedger({ practiceId: 'p1', bucket: 'promo', kind: 'usage', amountMicroUsd: -6750n, idempotencyKey: visitChargeKey('V', 'promo') });
    expect(() =>
      insertLedger({ practiceId: 'p1', bucket: 'promo', kind: 'usage', amountMicroUsd: -6750n, idempotencyKey: visitChargeKey('V', 'promo') }),
    ).toThrow(/ledger_entries_idempotencyKey_key/);
    expect(() =>
      insertLedger({ practiceId: 'p1', bucket: 'paid', kind: 'usage', amountMicroUsd: -6750n, idempotencyKey: visitChargeKey('V', 'paid') }),
    ).not.toThrow();
    expect(debitedFor('V'), 'the index alone lets one visit be debited twice').toBe(13_500n);
  });

  it('the key set the check reads is EVERY key the writer can emit — derived, not listed', () => {
    const keys = visitUsageKeys('V').sort();
    expect(keys).toEqual(LEDGER_BUCKETS.map((b) => visitChargeKey('V', b)).sort());
    for (const b of DRAW_ORDER) expect(keys).toContain(visitChargeKey('V', b));
    // …and it is exact — a neighbouring id is not swept in.
    expect(visitUsageKeys('V')).not.toContain(visitChargeKey('V:x', 'paid'));
  });
});

describe('ADMIN-4 round 6 — a retry of a charged visit is refused, whatever the wallet now holds', () => {
  it('⚠️ THE FINDING — promo first, promo drained, retry would draw paid: REFUSED, 6750 total', async () => {
    grant('p1', 'promo', 1_000_000n);
    grant('p1', 'paid', 1_000_000n);

    const first = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(first.written, 'the first charge did not write — every arm below would be vacuous').toBe(true);
    if (!first.written) return;
    expect(first.chargeMicroUsd).toBe(6750n);
    expect(first.draws).toEqual([{ bucket: 'promo', amountMicroUsd: 6750n }]);

    // Other visits spend promo to 0 — a real ledger row, so the balance moves.
    insertLedger({ practiceId: 'p1', bucket: 'promo', kind: 'usage', amountMicroUsd: -993_250n, idempotencyKey: visitChargeKey('OTHER', 'promo') });

    const retry = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(retry, 'a retry of a charged visit wrote again').toEqual({
      written: false,
      reason: 'already_charged',
      ledgerEntryIds: first.ledgerEntryIds,
    });
    expect(usageRowsFor('V')).toHaveLength(1);
    expect(debitedFor('V'), 'one visit, debited twice').toBe(6750n);
  });

  it('⚠️ THE REVERSE ORDER — paid first, then a promo grant lands, retry would draw promo: REFUSED', async () => {
    grant('p1', 'paid', 1_000_000n);
    const first = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(first.written).toBe(true);
    if (!first.written) return;
    expect(first.draws).toEqual([{ bucket: 'paid', amountMicroUsd: 6750n }]);

    grant('p1', 'promo', 10_000_000n);
    const retry = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(retry).toMatchObject({ written: false, reason: 'already_charged' });
    expect(debitedFor('V')).toBe(6750n);
  });

  it('⚠️ A SPLIT FIRST CHARGE — both buckets used, retry refused on either key', async () => {
    grant('p1', 'promo', 1000n);
    grant('p1', 'paid', 1_000_000n);
    const first = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(first.written).toBe(true);
    if (!first.written) return;
    expect(first.draws.map((d) => d.bucket)).toEqual(['promo', 'paid']);
    const retry = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(retry).toMatchObject({ written: false, reason: 'already_charged' });
    expect(debitedFor('V')).toBe(6750n);
  });

  it('⚠️ A DIFFERENT practiceId on the retry (#287) does not reopen it — the check is per VISIT', async () => {
    grant('p1', 'promo', 1_000_000n);
    grant('p2', 'paid', 1_000_000n);
    const first = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(first.written).toBe(true);
    const retry = await commitVisitCharge({ practiceId: 'p2', visitId: 'V', rows: ROWS_V });
    expect(retry).toMatchObject({ written: false, reason: 'already_charged' });
    expect(debitedFor('V')).toBe(6750n);
  });

  it('⚠️ NEVER RE-PRICED — a new margin and new usage after the charge change nothing', async () => {
    grant('p1', 'promo', 1_000_000n);
    grant('p1', 'paid', 1_000_000n);
    const first = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    expect(first.written).toBe(true);

    // A rate change, then the retry re-runs a layer and writes new usage after it.
    platformRateRows = [
      PR_32,
      { id: 'pr_51', marginNumerator: 5, marginDenominator: 1, effectiveFrom: new Date('2026-09-01T00:00:00Z'), createdAt: new Date('2026-09-01T00:00:00Z') },
    ];
    const rowsAfter = [...ROWS_V, usage('evt_v2', '2026-09-02T00:00:00Z', 10)];
    const retry = await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: rowsAfter });
    expect(retry).toMatchObject({ written: false, reason: 'already_charged' });
    expect(debitedFor('V'), 'the already-charged usage was billed again at the new margin').toBe(6750n);
  });

  it('⚠️ NON-VACUITY — a DIFFERENT visit in the same wallet state is still charged', async () => {
    // Without this every arm above passes on a writer that refuses everything.
    grant('p1', 'promo', 1_000_000n);
    grant('p1', 'paid', 1_000_000n);
    await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });
    const other = await commitVisitCharge({ practiceId: 'p1', visitId: 'W', rows: [usage('evt_w1', '2026-08-12T00:00:00Z', 1000)] });
    expect(other.written).toBe(true);
    if (!other.written) return;
    expect(other.chargeMicroUsd).toBe(1500n);
    expect(debitedFor('W')).toBe(1500n);
  });
});

describe('ADMIN-4 round 6 — WHERE the decision is taken', () => {
  it('⚠️ the check runs INSIDE the transaction, after EVERY lock and before the balance read', async () => {
    grant('p1', 'paid', 1_000_000n);
    await commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V });

    const lockIdx = calls.map((c, i) => (c.startsWith('lock:') ? i : -1)).filter((i) => i >= 0);
    const checkIdx = calls.indexOf('ledgerEntry.findMany');
    const readIdx = calls.indexOf('balance-read');
    expect(lockIdx.length, 'expected the visit lock plus one lock per bucket').toBe(1 + DRAW_ORDER.length);
    // The FIRST lock is the per-visit one, keyed on the visit alone.
    expect(calls[lockIdx[0]!]).toBe(`lock:${VISIT_CHARGE_LOCK_NAMESPACE}|V`);
    expect(checkIdx, 'the already-charged check was not asked').toBeGreaterThan(-1);
    expect(checkIdx, 'the check ran before a lock was held — it is a race').toBeGreaterThan(Math.max(...lockIdx));
    expect(checkIdx, 'the wallet was read before the visit was checked').toBeLessThan(readIdx);
    // And isolation is asserted before any of it.
    expect(calls.indexOf('isolation')).toBeLessThan(lockIdx[0]!);
  });

  it('⚠️ ABOVE READ COMMITTED it refuses BEFORE taking a lock, and writes nothing', async () => {
    grant('p1', 'paid', 1_000_000n);
    isolation = 'repeatable read';
    await expect(commitVisitCharge({ practiceId: 'p1', visitId: 'V', rows: ROWS_V })).rejects.toThrow(
      /isolation level "repeatable read"/,
    );
    expect(calls.some((c) => c.startsWith('lock:'))).toBe(false);
    expect(usageRowsFor('V')).toHaveLength(0);
  });
});

describe('ADMIN-4 round 6 — the pipeline reports it as what it is', () => {
  it('⚠️ `chargeVisitUsage` on a retried visit -> `already_charged`, not `written`, `failed` or `declined`', async () => {
    vi.stubEnv('BILLING_ENFORCED', 'true');
    grant('p1', 'promo', 1_000_000n);
    grant('p1', 'paid', 1_000_000n);
    usageEvents = [
      {
        id: 'evt_v1', visitId: 'V', provider: 'anthropic', modelName: 'claude-sonnet-5', unitsSource: 'vendor',
        timestamp: new Date('2026-08-12T00:00:00Z'), audioSeconds: null, inputTokens: 4500, outputTokens: null,
        cacheReadInputTokens: null, cacheCreationInputTokens: null,
      },
    ];
    const first = await chargeVisitUsage({ practiceId: 'p1', visitId: 'V' });
    expect(first).toMatchObject({ charged: 'written', chargeMicroUsd: 6750n });
    insertLedger({ practiceId: 'p1', bucket: 'promo', kind: 'usage', amountMicroUsd: -993_250n, idempotencyKey: visitChargeKey('OTHER', 'promo') });

    const retry = await chargeVisitUsage({ practiceId: 'p1', visitId: 'V' });
    expect(retry.charged).toBe('already_charged');
    expect(retry).toEqual({ charged: 'already_charged', ledgerEntryIds: usageRowsFor('V').map((r) => r.id) });
    expect(debitedFor('V')).toBe(6750n);
  });
});
