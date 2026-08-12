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
  DRAW_ORDER,
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

/**
 * A successful read, for driving the pure half without the database.
 *
 * ⚠️ `spendableMicroUsd` IS DERIVED FROM `SPENDABLE_BUCKETS`, NOT HARDCODED.
 * It used to say `spendableMicroUsd: paid`. That was true when `paid` was the
 * only spendable bucket, and it silently became a LIE when B7 step 3a made
 * `promo` spendable: this helper kept manufacturing a `BalanceRead` that
 * `readPracticeBalance` can no longer produce, so every arm below went on
 * asserting the OLD behaviour against an impossible input — green, and
 * measuring nothing about the shipped reader.
 *
 * A fixture that states a derived field by hand is a second implementation of
 * the thing under test, and it does not get updated when the first one changes.
 */
function read(paid: bigint, promo: bigint): BalanceRead {
  const byBucket = { paid, promo };
  let spendableMicroUsd = 0n;
  for (const b of SPENDABLE_BUCKETS) spendableMicroUsd += byBucket[b];
  return {
    ok: true,
    byBucket,
    spendableMicroUsd,
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
  it('promo-only is now ADMITTED — B7 step 3a made the debit able to draw it', () => {
    // ⚠️ THIS ARM IS THE INVERSE OF WHAT IT ASSERTED UNTIL B7 step 3a, AND THE
    // INVERSION IS THE POINT OF THE ITEM. It used to read "promo-only is
    // BLOCKED", and that was correct while `commitVisitCharge` hard-coded
    // `bucket: 'paid'`: admitting would have let the work run and then debited
    // an empty `paid`, driving it negative while the $10 sat untouched.
    //
    // The debit now iterates `DRAW_ORDER` and draws `promo` FIRST, so the same
    // wallet is genuinely spendable. Had this arm not been flipped deliberately,
    // B7 step 3's $10 grant would have funded nobody — every practice refused
    // `credit_not_spendable` instead of `insufficient_balance`, with the total
    // clinical outage unchanged.
    const d = decideAdmission(read(0n, 10_000_000n));
    expect(d.admit).toBe(true);
    expect(d.admit && d.spendableMicroUsd).toBe(10_000_000n);
  });

  it('promo DOES top up a short paid balance — the two are one spendable sum', () => {
    // An overdrawn `paid` (ruling 89(e) makes that a legal state) plus promo
    // that covers it is a practice which can pay for the next visit.
    const d = decideAdmission(read(-1n, 10_000_000n));
    expect(d.admit).toBe(true);
    expect(d.admit && d.spendableMicroUsd).toBe(9_999_999n);
  });

  it('and the sum can still be non-positive — promo does not admit by existing', () => {
    // The fail-open worth naming: "the practice holds promo" is not the test.
    // $1 of promo against a $2 overdraft is still an empty wallet.
    const d = decideAdmission(read(-2_000_000n, 1_000_000n));
    expect(d.admit).toBe(false);
    expect(!d.admit && d.reason).toBe('insufficient_balance');
  });

  it('a genuinely empty wallet is `insufficient_balance`', () => {
    const d = decideAdmission(read(0n, 0n));
    expect(!d.admit && d.reason).toBe('insufficient_balance');
  });

  it('`credit_not_spendable` SURVIVES, and is proven on a hand-built read', () => {
    // ⚠️ THIS BRANCH IS STRUCTURALLY UNREACHABLE TODAY AND IS TESTED ANYWAY.
    // With `SPENDABLE_BUCKETS == LEDGER_BUCKETS`, no real `readPracticeBalance`
    // result can have `total > spendable`, so `read()` above cannot construct
    // one — this arm builds the shape by hand on purpose.
    //
    // Deleting the branch instead would be a LOOSENING that is hard to reverse:
    // the day a third bucket lands that the writer cannot draw on, this is the
    // refusal that NAMES it rather than folding it into `insufficient_balance`.
    // It is derived from the two sums rather than from the word "promo", so it
    // needs no edit to keep working.
    const d = decideAdmission({
      ok: true,
      byBucket: { paid: 0n, promo: 0n },
      spendableMicroUsd: 0n,
      totalMicroUsd: 10_000_000n,
    });
    expect(!d.admit && d.reason).toBe('credit_not_spendable');
    expect(!d.admit && d.detail).toContain('10000000');
  });
});

// ---------------------------------------------------------------------------
// ARM 5 — the cross-file agreement no type can see.
// ---------------------------------------------------------------------------

describe('SPENDABLE_BUCKETS is DERIVED from the draw order, not mirrored', () => {
  it('the writer names NO bucket literal — the drift is unrepresentable now', () => {
    // ⚠️ THIS ARM REPLACES A MIRROR, AND THE REPLACEMENT IS THE STRONGER CLAIM.
    // It used to read the `bucket: 'paid'` literal out of `billing-charge.ts`
    // and assert it equalled this file's constant — a hand-kept agreement
    // between two files, policed by a regex. AGENTS.md: "a per-caller list is
    // kept complete by hand, and hand-kept lists are wrong eventually. Put the
    // behaviour where it cannot be forgotten."
    //
    // B7 step 3a did that: `DRAW_ORDER` is the one fact, the writer ITERATES it,
    // and `SPENDABLE_BUCKETS` is derived from it. So the assertion is no longer
    // "the two agree" — it is "there is nothing left to disagree WITH".
    const literals = [...chargeSrc().matchAll(/^\s*bucket:\s*'([a-z]+)'/gm)].map((m) => m[1]);
    expect(
      literals,
      'billing-charge.ts names a bucket literal again — the writer must iterate DRAW_ORDER',
    ).toEqual([]);
    expect(chargeSrc()).toContain('bucket: draw.bucket');
  });

  it('the matcher that found nothing CAN find something — the positive control', () => {
    // ⚠️ WITHOUT THIS, THE ARM ABOVE PASSES IF THE REGEX IS SIMPLY WRONG.
    // An empty result and a broken pattern are the same output, and this file
    // has already shipped one assertion that went vacuous when its anchor moved.
    const canary = "      bucket: 'paid',\n      kind: 'usage',";
    const found = [...canary.matchAll(/^\s*bucket:\s*'([a-z]+)'/gm)].map((m) => m[1]);
    expect(found).toEqual(['paid']);
  });

  it('SPENDABLE_BUCKETS and DRAW_ORDER are the same set, by identity', () => {
    expect([...SPENDABLE_BUCKETS].sort()).toEqual([...DRAW_ORDER].sort());
  });

  it('every drawable bucket is in the database vocabulary', () => {
    // A draw order naming a bucket the CHECK forbids would fail at INSERT, in
    // production, on the first split — long after any test could see it.
    for (const b of DRAW_ORDER) expect(LEDGER_BUCKETS).toContain(b);
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
