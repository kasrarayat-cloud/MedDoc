// ============================================================================
// GATE — FOUNDATION B8 step 1
// ----------------------------------------------------------------------------
// SPEC §2.4, verbatim: "Fail-closed insufficient-balance block. Insufficient
// balance blocks the work. Fail-closed here means: IF THE BALANCE CANNOT BE
// READ, BLOCK."
//
// That sentence contains two claims and they fail in different ways, so they are
// gated separately:
//
//   1. a zero (or negative) balance blocks               — arithmetic
//   2. an UNREADABLE balance blocks                      — error handling
//
// (2) is the one that rots. It is only reachable when something is already
// broken, so it is never exercised by ordinary use, and every plausible bug in
// it — a `catch` that returns 0, a `?? 0n`, an unhandled rejection swallowed
// upstream — produces code that passes (1) perfectly.
//
// ⚠️ WHAT WOULD MAKE THIS GATE FAIL, SAID BEFORE IT WAS MADE TO FAIL:
//
//   · `readPracticeBalance`'s catch returning a balance instead of `ok:false`
//   · dropping the SUM-vs-`balanceAfter` comparison, or resolving it by
//     picking one of the two numbers
//   · `decideAdmission` reading `totalMicroUsd` instead of `spendableMicroUsd`
//   · `>= 0n` where the code says `> 0n`
//   · `SPENDABLE_BUCKETS` drifting away from the bucket `commitVisitCharge`
//     actually writes
//
// Every one is mutation-proved below (M1–M6) — the mutation is applied to the
// SOURCE, the arm is observed RED, and the source is restored. AGENTS.md: a
// guard nobody has watched fail is a guard nobody has tested.
//
// ⚠️ AND WHAT THIS GATE CANNOT DO. It never watches a REAL ledger. The reader is
// driven through a stubbed `@meddoc/db`, so what is proven is that the reader
// refuses the shapes a broken database produces — not that this database
// produces them. The behavioural proof against a live ledger is B8 step 2's,
// on QA, which is where RELAY already requires B8 to be proven.
// ============================================================================

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  LEDGER_BUCKETS,
  SPENDABLE_BUCKETS,
  decideAdmission,
  readPracticeBalance,
  type BalanceRead,
} from '../billing-balance';

/** What the stubbed `$queryRawUnsafe` will do on the next call. */
let queryResult: { rows?: Record<string, string>[]; throws?: Error } = { rows: [] };

vi.mock('@meddoc/db', () => {
  const client = {
    $queryRawUnsafe: () => {
      if (queryResult.throws) return Promise.reject(queryResult.throws);
      return Promise.resolve(queryResult.rows ?? []);
    },
  };
  return { __esModule: true, default: client, prisma: client };
});

const SRC = join(__dirname, '..');

/**
 * Executable source only — prose must never satisfy a code assertion.
 * Byte-identical to `gate-mock-suite-stubs-the-db.test.ts:70`, which is where
 * this project keeps the canonical form.
 *
 * ⚠️ THIS IS NOT PRECAUTIONARY. It is load-bearing for arm 6, and it fired on
 * THIS commit's own file before the arm had ever run — see the trap arm below.
 */
const strip = (s: string) =>
  s
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .split('\n')
    .filter((l) => !l.trim().startsWith('//'))
    .join('\n');

const rawBalanceSrc = () => readFileSync(join(SRC, 'billing-balance.ts'), 'utf8');
const balanceSrc = () => strip(rawBalanceSrc());
const chargeSrc = () => strip(readFileSync(join(SRC, 'billing-charge.ts'), 'utf8'));

/** A bucket row as the query returns it — both statements of the balance. */
function bucketRow(bucket: string, micro: string, derived = micro) {
  return { bucket, sum_micro: micro, latest_balance: derived };
}

/** A successful read, for driving the pure half without the database. */
function read(paid: bigint, promo: bigint): BalanceRead {
  return {
    ok: true,
    byBucket: { paid, promo },
    spendableMicroUsd: paid,
    totalMicroUsd: paid + promo,
  };
}

beforeEach(() => {
  queryResult = { rows: [] };
});

// ---------------------------------------------------------------------------
// ARM 1 — the arithmetic. A zero balance blocks, and so does a negative one.
// ---------------------------------------------------------------------------

describe('a balance that cannot pay blocks the work', () => {
  it('a positive spendable balance ADMITS', () => {
    const d = decideAdmission(read(1n, 0n));
    expect(d.admit).toBe(true);
    expect(d.admit && d.spendableMicroUsd).toBe(1n);
  });

  it('EXACTLY ZERO blocks — `> 0n`, not `>= 0n`', () => {
    // The boundary, stated as its own case because off-by-one at zero is the
    // difference between "cannot pay" and "may start one more visit".
    const d = decideAdmission(read(0n, 0n));
    expect(d.admit).toBe(false);
    expect(!d.admit && d.reason).toBe('insufficient_balance');
  });

  it('a NEGATIVE balance blocks — the overrun ruling 89(e) permits the TABLE to record', () => {
    // Permitting the ROW is not permitting more WORK. B5 deliberately ships no
    // `balanceAfter >= 0` CHECK so a late `usage` row is representable; this is
    // the gate that stops the next visit starting anyway.
    const d = decideAdmission(read(-5_000_000n, 0n));
    expect(d.admit).toBe(false);
    expect(!d.admit && d.reason).toBe('insufficient_balance');
  });
});

// ---------------------------------------------------------------------------
// ARM 2 — the claim that rots. An unreadable balance blocks.
// ---------------------------------------------------------------------------

describe('an UNREADABLE balance blocks — SPEC §2.4 fail-closed', () => {
  it('a thrown query yields `ok:false`, NOT a balance of zero', () => {
    // The distinction is the whole arm: `{ok:false}` and `{ok:true, 0n}` both
    // block today, so a behavioural test alone cannot tell them apart. They
    // differ the moment anything reads the number — a display, a report, B9.
    return readPracticeBalance('prac_1').then((r) => {
      queryResult = { throws: new Error('connection pool exhausted') };
      return readPracticeBalance('prac_1').then((thrown) => {
        expect(r.ok).toBe(true); // control: the same call succeeds with rows []
        expect(thrown.ok).toBe(false);
        expect(!thrown.ok && thrown.reason).toBe('query_failed');
      });
    });
  });

  it('an unreadable balance is REFUSED ADMISSION, and the reason survives', () => {
    const d = decideAdmission({
      ok: false,
      reason: 'query_failed',
      detail: 'connection pool exhausted',
    });
    expect(d.admit).toBe(false);
    expect(!d.admit && d.reason).toBe('balance_unreadable');
    // B9 has to reconcile refusals, so the cause must not collapse into a
    // boolean — the same reason B7's `decideTopup` names every refusal.
    expect(!d.admit && d.detail).toContain('pool exhausted');
  });

  it('NO ROWS is a balance of zero, and that is `ok:true` — a fact, not a failure', () => {
    return readPracticeBalance('prac_empty').then((r) => {
      expect(r.ok).toBe(true);
      expect(r.ok && r.spendableMicroUsd).toBe(0n);
      expect(r.ok && r.totalMicroUsd).toBe(0n);
    });
  });
});

// ---------------------------------------------------------------------------
// ARM 3 — the two statements of the balance must agree.
// ---------------------------------------------------------------------------

describe('SUM and the derive trigger must agree, or the balance is unknown', () => {
  it('agreeing rows read normally — the positive control for this arm', () => {
    queryResult = { rows: [bucketRow('paid', '7000000'), bucketRow('promo', '10000000')] };
    return readPracticeBalance('prac_1').then((r) => {
      expect(r.ok).toBe(true);
      expect(r.ok && r.byBucket.paid).toBe(7_000_000n);
      expect(r.ok && r.totalMicroUsd).toBe(17_000_000n);
    });
  });

  it('DISAGREEING rows refuse — ruling 89(c) produced exactly this shape', () => {
    // 89(c) mutation-proved a guard that accepted an UPDATE rewriting an amount
    // 5000000 → 999 while `balanceAfter` stayed 5000000. A reader that trusted
    // either number alone would report a balance with total confidence.
    queryResult = { rows: [bucketRow('paid', '999', '5000000')] };
    return readPracticeBalance('prac_1').then((r) => {
      expect(r.ok).toBe(false);
      expect(!r.ok && r.reason).toBe('derivation_disagrees');
    });
  });

  it('the refusal does NOT resolve to the smaller number', () => {
    // The tempting "safe" repair. A ledger disagreeing with itself has an
    // unknown balance, and the smaller of two numbers you do not trust is still
    // a number you do not trust.
    queryResult = { rows: [bucketRow('paid', '999', '5000000')] };
    return readPracticeBalance('prac_1').then((r) => {
      expect(r.ok).toBe(false);
      expect(decideAdmission(r).admit).toBe(false);
    });
  });

  it('a bucket outside the vocabulary refuses — the CHECK is not enforcing', () => {
    queryResult = { rows: [bucketRow('paid', '1'), bucketRow('gift', '9999')] };
    return readPracticeBalance('prac_1').then((r) => {
      expect(r.ok).toBe(false);
      expect(!r.ok && r.reason).toBe('derivation_disagrees');
    });
  });
});

// ---------------------------------------------------------------------------
// ARM 4 — admission judges the SPENDABLE balance, and says so when it hurts.
// ---------------------------------------------------------------------------

describe('admission judges the buckets a DEBIT can reach', () => {
  it('promo-only is BLOCKED — admitting on the total would be the fail-open', () => {
    // $10 promo, $0 paid. Admitting here would let the work run and then debit
    // `paid` (B6 writes `bucket: 'paid'`), driving it negative while the $10
    // nobody can reach sits untouched. The block would have blocked nothing.
    const d = decideAdmission(read(0n, 10_000_000n));
    expect(d.admit).toBe(false);
  });

  it('and it is reported as `credit_not_spendable`, NOT `insufficient_balance`', () => {
    // The refusal that says "you have money I cannot spend" is a bug report.
    // The same refusal called "insufficient balance" is a lie that reconciles.
    const d = decideAdmission(read(0n, 10_000_000n));
    expect(!d.admit && d.reason).toBe('credit_not_spendable');
    expect(!d.admit && d.detail).toContain('10000000');
  });

  it('promo does NOT top up a short paid balance either', () => {
    const d = decideAdmission(read(-1n, 10_000_000n));
    expect(d.admit).toBe(false);
    expect(!d.admit && d.reason).toBe('credit_not_spendable');
  });

  it('the two refusals are distinguishable — a genuinely empty wallet is the other one', () => {
    expect(
      (() => {
        const d = decideAdmission(read(0n, 0n));
        return !d.admit && d.reason;
      })(),
    ).toBe('insufficient_balance');
  });
});

// ---------------------------------------------------------------------------
// ARM 5 — the cross-file agreement no type can see.
// ---------------------------------------------------------------------------

describe('SPENDABLE_BUCKETS mirrors what the debit actually writes', () => {
  it('`commitVisitCharge` writes exactly the buckets admission judges', () => {
    // ⚠️ THIS IS A SOURCE ASSERTION BECAUSE NOTHING ELSE CAN MAKE IT.
    // B6 writes `bucket: 'paid'` as a STRING LITERAL in another file. No type
    // checker relates it to this file's constant, so if a future step teaches
    // the writer to draw `promo` first and does not update SPENDABLE_BUCKETS,
    // admission silently starts judging money the debit no longer draws on —
    // and every behavioural test here stays green, because they are all driven
    // from this file's own constant.
    const written = [...chargeSrc().matchAll(/bucket:\s*'([a-z]+)'/g)].map((m) => m[1]);
    expect(written.length, 'no `bucket:` literal found in billing-charge.ts — the matcher is stale')
      .toBeGreaterThan(0);
    expect([...new Set(written)].sort()).toEqual([...SPENDABLE_BUCKETS].sort());
  });

  it('the vocabulary matches the database CHECK', () => {
    // `ledger_entries_bucket_vocabulary CHECK (bucket IN ('paid','promo'))`.
    // A bucket added to the database and not here would be summed into nothing.
    const schema = readFileSync(
      join(SRC, '../../db/prisma/migrations/20260811070000_b5_ledger_entries/migration.sql'),
      'utf8',
    );
    for (const b of LEDGER_BUCKETS) {
      expect(schema, `bucket "${b}" is not in the B5 migration`).toContain(`'${b}'`);
    }
    expect(LEDGER_BUCKETS.length).toBe(2);
  });
});

// ---------------------------------------------------------------------------
// ARM 6 — absences. Invisible to a behavioural test (ruling 84(a)).
// ---------------------------------------------------------------------------

describe('two deliberate absences, pinned because nothing else can see them', () => {
  it('the READER is NOT production-gated', () => {
    // B6's writer calls `assertProdDatabase()` as its first statement, and must.
    // A reader that did the same would make the block unprovable anywhere a
    // test is allowed to run — the exact cost B6's header records paying, and
    // there is no reason to pay it twice for a read.
    expect(balanceSrc()).not.toContain('assertProdDatabase');
  });

  it('no `?? 0` anywhere near the balance', () => {
    // The fail-open shape ruling 80(c) forbids by name, and the one a future
    // author reaches for when the types get inconvenient.
    expect(balanceSrc()).not.toMatch(/\?\?\s*0n?\b/);
  });

  it('⚠️ AND THE SCANNER STRIPS PROSE — the substring family, caught on this file', () => {
    // The arm above is an EMPTINESS TEST, and an emptiness test over a set
    // whose boundary was never established is this project's named recurring
    // defect. Here the boundary is exactly the difference between the file's
    // code and the file's comments — and `billing-balance.ts`'s header
    // DISCUSSES `?? 0` at length, precisely because it is explaining why the
    // habit is safe at this seam and fatal at the pricing one.
    //
    // So the raw file MUST match and the stripped file MUST NOT. Without the
    // strip, the arm above is red on correct code; without this control, the
    // strip could silently start returning "" and the arm above would be green
    // forever. AGENTS.md's fifth sighting of the family was a guard tripping on
    // its own explanatory comment; this is the sixth, caught before it shipped.
    expect(rawBalanceSrc(), 'the header no longer discusses `?? 0` — this control is stale').toMatch(
      /\?\?\s*0n?\b/,
    );
    expect(balanceSrc()).not.toMatch(/\?\?\s*0n?\b/);
    // …and the strip is not simply eating the file.
    expect(balanceSrc()).toContain('export function decideAdmission');
  });
});
