// ============================================================================
// GATE — B7 step 3a: THE PROMO DRAW ORDER
// ----------------------------------------------------------------------------
// The item: `commitVisitCharge` draws `promo` before `paid`, so that B7 step 3's
// $10 grant is money a practice can actually spend. Without it the grant moves
// every practice from `insufficient_balance` to `credit_not_spendable` and the
// total clinical outage is unchanged — see `billing-buckets.ts`'s header and
// RULINGS #96.
//
// ── WHAT THIS GATE CAN AND CANNOT PROVE ────────────────────────────────────
//
// `commitVisitCharge` calls `assertProdDatabase()` as its first statement (F4,
// ruling 90(c)), so no test anywhere may watch it write. B6 established the
// answer and it is the same one here: the DECISION is separated from the EFFECT
// and proven exhaustively; the EFFECT is asserted on its source.
//
// ⚠️ SO THE SOURCE ARMS BELOW ARE NOT LAZINESS, THEY ARE THE ONLY INSTRUMENT
// AVAILABLE — and they are written knowing this file has already shipped one
// source assertion that went VACUOUS when its anchor moved (`gate-b6`'s
// balanceAfter/seq arm sliced on `prisma.ledgerEntry.create`, the write moved to
// `tx.`, `indexOf` returned -1, and `slice(-1)` made both assertions pass
// against a one-character string). Every source arm here asserts its anchor
// BEFORE it asserts anything about the text.
//
// ⚠️ AND WHAT IS STILL OWED AFTER THIS GATE IS GREEN. The split has never
// executed against a real ledger, in any environment — the writer refuses off
// production, and `ledger_entries` holds 0 rows in both. What is proven here is
// the arithmetic, the ordering, and the wiring. RELAY's "B8 must be proven on
// QA" is not discharged by this file and is not claimed to be.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  DRAW_ORDER,
  LEDGER_BUCKETS,
  SPENDABLE_BUCKETS,
  splitCharge,
  type LedgerBucket,
} from '../billing-buckets';

const SRC = join(__dirname, '..');
const ROOT = join(SRC, '..', '..', '..');

const chargeSrc = () => readFileSync(join(SRC, 'billing-charge.ts'), 'utf8');
const migrationSrc = () =>
  readFileSync(
    join(ROOT, 'packages/db/prisma/migrations/20260811070000_b5_ledger_entries/migration.sql'),
    'utf8',
  );

const wallet = (paid: bigint, promo: bigint): Record<LedgerBucket, bigint> => ({ paid, promo });
const total = (draws: { amountMicroUsd: bigint }[]) =>
  draws.reduce((acc, d) => acc + d.amountMicroUsd, 0n);

// ---------------------------------------------------------------------------
// ARM 1 — CONSERVATION. The invariant everything else rests on.
// ---------------------------------------------------------------------------

describe('the draws always sum to exactly the charge', () => {
  // A grid rather than three hand-picked cases: the failure mode being guarded
  // against is a boundary — "covered exactly", "one micro-dollar short", "one
  // over" — and a hand-picked example set is where boundaries hide.
  const charges = [0n, 1n, 2n, 499_999n, 500_000n, 500_001n, 10_000_000n, 999_999_999n];
  const balances = [-7n, -1n, 0n, 1n, 499_999n, 500_000n, 500_001n, 10_000_000n];

  it('for every (charge, promo, paid) in the grid — 512 combinations', () => {
    let checked = 0;
    for (const charge of charges) {
      for (const promo of balances) {
        for (const paid of balances) {
          const draws = splitCharge(charge, wallet(paid, promo));
          expect(total(draws), `charge=${charge} promo=${promo} paid=${paid}`).toBe(charge);
          checked++;
        }
      }
    }
    // ⚠️ THE COUNT IS ASSERTED BECAUSE A LOOP THAT RUNS ZERO TIMES PASSES.
    // AGENTS.md: positive-control every zero — an empty grid and a correct
    // implementation produce identical output.
    expect(checked).toBe(charges.length * balances.length * balances.length);
    expect(checked).toBe(512);
  });

  it('and never returns more draws than there are buckets', () => {
    for (const charge of charges) {
      for (const promo of balances) {
        for (const paid of balances) {
          const draws = splitCharge(charge, wallet(paid, promo));
          expect(draws.length).toBeLessThanOrEqual(DRAW_ORDER.length);
          expect(draws.length).toBeGreaterThan(0);
        }
      }
    }
  });
});

// ---------------------------------------------------------------------------
// ARM 2 — THE ORDER ITSELF. Promo first, and it is the whole item.
// ---------------------------------------------------------------------------

describe('promo is drawn before paid', () => {
  it('a charge promo can cover entirely touches `paid` not at all', () => {
    const draws = splitCharge(400_000n, wallet(9_000_000n, 10_000_000n));
    expect(draws).toEqual([{ bucket: 'promo', amountMicroUsd: 400_000n }]);
  });

  it('a charge promo can only part-cover splits, promo first', () => {
    // $0.30 of promo against a $0.50 charge: 300000 from promo, 200000 from paid.
    const draws = splitCharge(500_000n, wallet(9_000_000n, 300_000n));
    expect(draws).toEqual([
      { bucket: 'promo', amountMicroUsd: 300_000n },
      { bucket: 'paid', amountMicroUsd: 200_000n },
    ]);
  });

  it('the draws appear in DRAW_ORDER, never in some other order', () => {
    const draws = splitCharge(500_000n, wallet(9_000_000n, 300_000n));
    const order = draws.map((d) => d.bucket);
    // Compared against the CONSTANT, not against a written-out ['promo','paid'],
    // so reordering the constant reddens this rather than quietly agreeing.
    expect(order).toEqual(DRAW_ORDER.filter((b) => order.includes(b)));
  });

  it('a bucket is never drawn beyond what it holds — except the last', () => {
    for (const bucket of DRAW_ORDER.slice(0, -1)) {
      const held = 250_000n;
      const draws = splitCharge(10_000_000n, wallet(held, held));
      const drawn = draws.find((d) => d.bucket === bucket);
      expect(drawn?.amountMicroUsd ?? 0n).toBeLessThanOrEqual(held);
    }
  });
});

// ---------------------------------------------------------------------------
// ARM 3 — THE OVERRUN. Where money we were not holding gets recorded.
// ---------------------------------------------------------------------------

describe('an overrun lands on the LAST bucket, never on promo', () => {
  // Ruling 89(e) makes a negative balance legal: admission is checked once,
  // before the work, while `usage` rows land after the vendors report. So a
  // visit CAN cost more than the wallet held, and that has to go somewhere.

  it('a charge exceeding both buckets overruns `paid`, not `promo`', () => {
    const draws = splitCharge(10_000_000n, wallet(1_000_000n, 2_000_000n));
    expect(draws).toEqual([
      { bucket: 'promo', amountMicroUsd: 2_000_000n },
      { bucket: 'paid', amountMicroUsd: 8_000_000n },
    ]);
    // `paid` held 1_000_000 and was drawn 8_000_000 — the overrun, on the bucket
    // whose going negative states a TRUE thing (the practice owes us). On promo
    // it would claim we granted more promo than we granted.
    expect(draws.at(-1)!.bucket).toBe(DRAW_ORDER.at(-1));
  });

  it('promo is never drawn past its balance, at any charge', () => {
    for (const charge of [1n, 500_000n, 10_000_000n, 999_999_999n]) {
      const draws = splitCharge(charge, wallet(0n, 1_000_000n));
      const promo = draws.find((d) => d.bucket === 'promo');
      expect(promo?.amountMicroUsd ?? 0n).toBeLessThanOrEqual(1_000_000n);
    }
  });

  it('an ALREADY-NEGATIVE promo contributes nothing and does not subtract', () => {
    // The `max(available, 0)` clause. An overdrawn promo must not make the
    // function try to repay it out of the current charge — that would inflate
    // the visit's total, and conservation would still hold while the number was
    // wrong.
    const draws = splitCharge(500_000n, wallet(9_000_000n, -3_000_000n));
    expect(draws).toEqual([{ bucket: 'paid', amountMicroUsd: 500_000n }]);
    expect(total(draws)).toBe(500_000n);
  });
});

// ---------------------------------------------------------------------------
// ARM 4 — THE INERTNESS PROOF. Why this cannot move a number today.
// ---------------------------------------------------------------------------

describe('with an empty ledger the split degenerates to exactly what B6 wrote', () => {
  it('all buckets zero → ONE draw, on `paid`, for the whole charge', () => {
    // ⚠️ THIS IS THE ARM THAT LICENSES THE DEPLOY. `ledger_entries` holds 0 rows
    // in BOTH environments, so every practice's wallet is {paid: 0, promo: 0}.
    // In that state this change produces byte-for-byte the row B6 produced: one
    // `usage` row on `paid` for the full charge. The behaviour therefore cannot
    // differ anywhere until the grant lands.
    const draws = splitCharge(487_500n, wallet(0n, 0n));
    expect(draws).toEqual([{ bucket: 'paid', amountMicroUsd: 487_500n }]);
  });

  it('a zero charge still writes exactly one row, as it did before', () => {
    // A fully-priced visit that happens to cost nothing recorded itself before
    // this change and must keep doing so — vanishing would make an uncharged
    // visit indistinguishable from an unrecorded one, which is B9's problem.
    const draws = splitCharge(0n, wallet(0n, 0n));
    expect(draws).toEqual([{ bucket: 'paid', amountMicroUsd: 0n }]);
  });
});

// ---------------------------------------------------------------------------
// ARM 5 — THE ONE CONSTANT. What replaced the hand-kept mirror.
// ---------------------------------------------------------------------------

describe('DRAW_ORDER is the single fact both sides read', () => {
  it('SPENDABLE_BUCKETS is the same set — derived, not asserted-equal', () => {
    expect([...SPENDABLE_BUCKETS].sort()).toEqual([...DRAW_ORDER].sort());
  });

  it('DRAW_ORDER covers the whole database vocabulary', () => {
    // If a bucket existed that the writer could not draw, admission would refuse
    // it as `credit_not_spendable` — the state B7 step 3a exists to leave.
    expect([...DRAW_ORDER].sort()).toEqual([...LEDGER_BUCKETS].sort());
  });

  it('every drawable bucket is in the database CHECK', () => {
    const sql = migrationSrc();
    for (const b of DRAW_ORDER) {
      expect(sql, `bucket "${b}" is not in ledger_entries_bucket_vocabulary`).toContain(`'${b}'`);
    }
  });
});

// ---------------------------------------------------------------------------
// ARM 6 — THE WIRING. Source assertions, each with its anchor asserted first.
// ---------------------------------------------------------------------------

describe('the writer is wired the way the split requires', () => {
  it('the write happens inside a transaction', () => {
    // Both rows of a split must land together or not at all. A partial split is
    // a visit charged for half of itself, on a table that cannot delete either
    // row.
    const src = chargeSrc();
    expect(src).toContain('prisma.$transaction(async (tx)');
    expect(src).toContain('tx.ledgerEntry.create');
  });

  it('the balance is read INSIDE the transaction, under the locks', () => {
    const src = chargeSrc();
    const txAt = src.indexOf('prisma.$transaction(async (tx)');
    expect(txAt, 'the $transaction anchor is gone — this arm measures nothing').toBeGreaterThan(-1);
    const lockAt = src.indexOf('pg_advisory_xact_lock', txAt);
    const readAt = src.indexOf('readPracticeBalance(args.practiceId, tx)', txAt);
    const writeAt = src.indexOf('tx.ledgerEntry.create', txAt);
    expect(lockAt, 'no advisory lock inside the transaction').toBeGreaterThan(-1);
    expect(readAt, 'the balance is not read from the transaction client').toBeGreaterThan(-1);
    expect(writeAt, 'no write inside the transaction').toBeGreaterThan(-1);
    // ⚠️ ORDER IS THE WHOLE POINT: lock, THEN read, THEN write. Reading before
    // locking is the race this change would otherwise introduce — two visits
    // both seeing $10 of promo and both drawing it.
    expect(lockAt).toBeLessThan(readAt);
    expect(readAt).toBeLessThan(writeAt);
  });

  it('the locks are taken by iterating DRAW_ORDER — so the order cannot drift', () => {
    const src = chargeSrc();
    expect(src).toContain('for (const bucket of DRAW_ORDER)');
  });

  it('the lock KEY matches ledger_entries_derive() exactly', () => {
    // ⚠️ A DIFFERENT KEY TAKES A DIFFERENT LOCK AND SERIALISES NOTHING, while
    // looking exactly like correct code. The trigger uses
    //   hashtext('ledger_entries'), hashtext(NEW."practiceId" || ':' || NEW."bucket")
    // and this writer must hash the same two things in the same shape.
    const sql = migrationSrc();
    expect(sql).toContain("pg_advisory_xact_lock(");
    expect(sql).toContain("hashtext('ledger_entries')");
    expect(sql).toContain(`hashtext(NEW."practiceId" || ':' || NEW."bucket")`);

    const src = chargeSrc();
    expect(src).toContain("hashtext('ledger_entries')");
    // The TS side builds the same `<practiceId>:<bucket>` string and hashes it.
    expect(src).toContain('`${args.practiceId}:${bucket}`');
  });

  it('an unreadable balance writes NOTHING and says so', () => {
    // The fallback that was rejected: "put it all on `paid`". That spends the
    // doctor's money while promo we granted them sits unused, and on an
    // append-only table it is fixable only by an `adjustment` somebody has to
    // notice is owed. Refusing loses OUR revenue instead — loudly, and B9's job
    // is finding a usage event with no ledger row.
    const src = chargeSrc();
    expect(src).toContain("reason: 'balance_unreadable'");
    const readAt = src.indexOf('readPracticeBalance(args.practiceId, tx)');
    expect(readAt).toBeGreaterThan(-1);
    const guard = src.slice(readAt, src.indexOf('splitCharge(', readAt));
    expect(guard, 'no `!read.ok` guard between the read and the split').toContain('!read.ok');
  });

  it('the writer names no bucket literal at all', () => {
    const literals = [...chargeSrc().matchAll(/^\s*bucket:\s*'([a-z]+)'/gm)].map((m) => m[1]);
    expect(literals).toEqual([]);
    expect(chargeSrc()).toContain('bucket: draw.bucket');
  });
});
