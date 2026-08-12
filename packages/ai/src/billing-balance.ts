// ============================================================================
// FOUNDATION B8 step 1 — THE WALLET READ, AND WHAT A PRACTICE MAY BE ADMITTED TO
// ----------------------------------------------------------------------------
// SPEC §2.4: "Fail-closed insufficient-balance block. Insufficient balance
// blocks the work. Fail-closed here means: if the balance cannot be read,
// block."
//
// Ruling 89(e) named this seam by hand when it explained why `ledger_entries`
// has NO `balanceAfter >= 0` CHECK: "the insufficient-balance block is checked
// at ADMISSION (B8) while `usage` rows land AFTER the vendor reports, so a
// legitimately-overrunning visit's last usage row would become unrepresentable".
//
// So a NEGATIVE balance is a legal state of this table, not a corruption. This
// file is the admission gate that makes it rare; it is not a constraint that
// makes it impossible, and it must never be turned into one.
//
// ── THE FILE IS IN TWO HALVES, THE SAME SPLIT B6 AND B7 MADE ───────────────
//
//   1. `decideAdmission` — PURE. A balance read in, a decision out. No
//      database, no clock, no environment.
//   2. `readPracticeBalance` — the only thing that touches the database. It
//      READS, so unlike B6's writer it is NOT production-only and must not
//      become so: a reader that refused off production would make the block
//      unprovable anywhere a test is allowed to run, which is precisely the
//      cost B6's header records paying for its writer.
//
// ── WHAT THIS STEP DOES NOT DO ─────────────────────────────────────────────
//
// NOTHING CALLS EITHER FUNCTION. The pipeline call site is B8 step 2, and that
// is deliberate rather than unfinished — ruling 90(e) requires the debit and the
// block to land "in one change and in that order", and the debit inherits the
// `logApiUsage` read-after-write race that same ruling moved onto B8. This step
// ships the decision so that change has something proven to wire.
//
// ============================================================================
// ⚠️ THE BALANCE IS READ TWO WAYS AND THEY MUST AGREE — the load-bearing part
// ----------------------------------------------------------------------------
// Every row carries `balanceAfter`, derived by `ledger_entries_derive()` under a
// per-(practice,bucket) advisory lock. So there are two ways to state a balance:
//
//   · SUM("amountMicroUsd")            — the arithmetic, ignoring the trigger
//   · "balanceAfter" of the MAX("seq") — the trigger's own running total
//
// They are identical by construction. B5's migration header says the only way
// they can diverge is "if something wrote around the trigger", and ruling 89(c)
// records a mutation proof where exactly that happened: a hand-written guard
// accepted an UPDATE that rewrote an amount 5000000 → 999 **while
// `balanceAfter` stayed 5000000**. That is a ledger row whose amount and running
// balance disagree, produced through a guard that reported success.
//
// Reading one number would trust whichever half of that pair happened to be
// right. Reading both and REFUSING on disagreement converts a silent corruption
// into a block, which is the direction a money check should fail in. It costs
// one extra aggregate in the same query.
//
// ⚠️ AND THE REFUSAL IS NOT "PICK THE SMALLER". A ledger that disagrees with
// itself has an unknown balance, and the smaller of two numbers you do not
// trust is still a number you do not trust.
//
// ============================================================================
// ⚠️ A ZERO THAT MEANS "NO ROWS" AND A ZERO THAT MEANS "I COULD NOT READ" ARE
//    DIFFERENT VALUES, AND HERE THE SLOPPY HABIT IS ACCIDENTALLY SAFE
// ----------------------------------------------------------------------------
// A practice with no rows in a bucket genuinely holds zero there. That is a
// fact, and `{ ok: true, 0n }` states it. A query that threw states nothing, and
// gets `{ ok: false }`.
//
// ⚠️ NOTE WHY THIS IS WORTH SPELLING OUT RATHER THAN LEAVING TO TASTE. At the
// PRICING seam, ruling 80(c) records that `claudeCostCents` returning 0 for an
// unrecognised model means an unpriced model silently bills NOTHING — the
// canonical fail-open. At THIS seam the same `?? 0` blocks, because zero money
// refuses work. **The identical habit is dangerous there and harmless here**, so
// a reader who learns "`?? 0` is fine" from this file carries the wrong lesson
// to the file where it is not. The distinction is kept in the TYPE — a caller
// cannot reach a balance without first passing `ok` — so nothing depends on
// anybody remembering which seam they are standing at.
//
// ============================================================================
// ⚠️ ADMISSION IS JUDGED ON THE **SPENDABLE** BALANCE, NOT THE TOTAL
// ----------------------------------------------------------------------------
// SPEC §2.4 requires "two buckets, not one number with a note", and B6's writer
// took the second half of that seriously: `commitVisitCharge` hard-codes
// `bucket: 'paid'`, with the comment "usage always draws on `paid`; the `promo`
// bucket is granted and drawn separately, and B7 owns that split". B7's three
// steps did not take it, so the split is genuinely unowned today.
//
// That makes admitting on `promo + paid` a FAIL-OPEN, and the reasoning is
// worth following because the naive form looks generous rather than broken:
//
//     a practice holding $10 promo and $0 paid would be ADMITTED on a total of
//     $10, and then debited against `paid` — which is empty. It goes negative,
//     the work happens, and the $10 nobody can reach is still sitting there.
//
// The block would have blocked nothing, and the promo grant would be a number
// that can never be spent. So admission reads the set of buckets the DEBIT can
// actually reach, {@link SPENDABLE_BUCKETS}, and the day a step teaches the
// writer to draw promo first, admission and debit change together at one named
// constant rather than in two files that must be remembered at once.
//
// ⚠️ AND THE COST OF THIS CHOICE IS PAID LOUDLY, ON PURPOSE. A promo-only
// practice is refused work it could arguably pay for. That is the fail-CLOSED
// direction, and it is reported as its own reason — `credit_not_spendable` —
// rather than folded into `insufficient_balance`. B6 made the same trade for an
// unpriceable visit and gave the reason: charging nothing and NAMING it is "the
// only one where being wrong is VISIBLE". A refusal that says "you have money I
// cannot spend" is a bug report; the same refusal called "insufficient balance"
// is a lie that reconciles.
// ============================================================================

import prisma from '@meddoc/db';

/**
 * The `bucket` vocabulary, pinned in the database by
 * `ledger_entries_bucket_vocabulary`. A new bucket is a migration, and that
 * refusal is the feature (B5's schema comment).
 */
export type LedgerBucket = 'paid' | 'promo';

/** Both buckets, in the order a report should read them. */
export const LEDGER_BUCKETS: readonly LedgerBucket[] = ['paid', 'promo'];

/**
 * THE BUCKETS A DEBIT CAN ACTUALLY REACH — see the header.
 *
 * ⚠️ THIS IS NOT A PREFERENCE, IT IS A MIRROR OF `commitVisitCharge`. B6 writes
 * `bucket: 'paid'` as a literal. If that literal changes and this constant does
 * not, admission starts judging money the debit cannot touch (fail-open) or
 * refusing money it can (a needless block). The gate asserts the two agree by
 * reading B6's source, because no type can see a string literal in another file.
 */
export const SPENDABLE_BUCKETS: readonly LedgerBucket[] = ['paid'];

/** Why a balance could not be established. Neither value is a balance of 0. */
export type BalanceUnreadable =
  /** The query threw — pool exhausted, database down, permissions. */
  | 'query_failed'
  /** SUM and the latest `balanceAfter` disagree for some bucket. See the
   *  header: something wrote around the derive trigger. */
  | 'derivation_disagrees';

export type BalanceRead =
  | {
      ok: true;
      /** Per-bucket running balance, in SIGNED micro-dollars. May be negative
       *  — ruling 89(e) makes an overrun a legal state of the table. */
      byBucket: Record<LedgerBucket, bigint>;
      /** The sum over {@link SPENDABLE_BUCKETS}. What admission judges. */
      spendableMicroUsd: bigint;
      /** The sum over every bucket. For display and for B9; NOT the admission
       *  input, deliberately — see the header. */
      totalMicroUsd: bigint;
    }
  | { ok: false; reason: BalanceUnreadable; detail: string };

/** One bucket as the database reports it, both ways at once. */
interface BucketRow {
  bucket: string;
  sum_micro: string;
  latest_balance: string;
}

/**
 * THE QUERY. Both statements of the balance, per bucket, in one read.
 *
 * ⚠️ BIGINT COMES BACK AS TEXT ON PURPOSE. `$queryRaw` maps Postgres `BIGINT`
 * to JS `BigInt`, which is correct — but `SUM()` returns `NUMERIC`, not
 * `BIGINT`, and a `NUMERIC` arrives as a string or a Decimal depending on the
 * driver. Casting BOTH columns to `TEXT` and parsing them here makes the two
 * halves of the comparison travel identically, so a mismatch can only mean the
 * database disagrees with itself and never that two type mappings disagree.
 *
 * ⚠️ `ORDER BY "seq"`, NEVER `"createdAt"` — B5's schema comment: `createdAt`
 * is transaction-start time, so two rows written in one transaction share it
 * exactly. `seq` is the ledger's order.
 */
const BUCKET_BALANCE_SQL = `
  SELECT e1."bucket"                                       AS bucket,
         COALESCE(SUM(e1."amountMicroUsd"), 0)::TEXT       AS sum_micro,
         COALESCE((SELECT e2."balanceAfter"
                     FROM "ledger_entries" e2
                    WHERE e2."practiceId" = e1."practiceId"
                      AND e2."bucket"     = e1."bucket"
                    ORDER BY e2."seq" DESC
                    LIMIT 1), 0)::TEXT                     AS latest_balance
    FROM "ledger_entries" e1
   WHERE e1."practiceId" = $1
   GROUP BY e1."practiceId", e1."bucket"
`;

/**
 * READ A PRACTICE'S WALLET — every bucket, fail-closed.
 *
 * Returns `{ ok: false }` for anything that is not a confirmed balance. A
 * practice with no ledger rows is `{ ok: true }` with zeros: no rows is a
 * balance, not a failure.
 *
 * ⚠️ THE `catch` IS BROAD DELIBERATELY, AND IT IS THE FAIL-CLOSED DIRECTION.
 * Every way this can fail — a dead pool, a dropped table, a driver change that
 * stops returning text — produces "we do not know", and the caller's only legal
 * response to that is to block. There is no error here that should be recovered
 * into a number.
 */
export async function readPracticeBalance(practiceId: string): Promise<BalanceRead> {
  let rows: BucketRow[];
  try {
    rows = await prisma.$queryRawUnsafe<BucketRow[]>(BUCKET_BALANCE_SQL, practiceId);
  } catch (err) {
    return {
      ok: false,
      reason: 'query_failed',
      detail: `could not read ledger_entries for practice ${practiceId}: ${
        err instanceof Error ? err.message : String(err)
      }`,
    };
  }

  const byBucket: Record<LedgerBucket, bigint> = { paid: 0n, promo: 0n };

  for (const row of rows) {
    // A bucket outside the vocabulary means the CHECK constraint is gone. That
    // is the same class as a disagreeing balance — the table is not what this
    // code believes — so it refuses rather than silently ignoring the row and
    // reporting a balance that omits real money.
    if (!LEDGER_BUCKETS.includes(row.bucket as LedgerBucket)) {
      return {
        ok: false,
        reason: 'derivation_disagrees',
        detail:
          `bucket "${row.bucket}" is outside the vocabulary ` +
          `{${LEDGER_BUCKETS.join(', ')}} — ledger_entries_bucket_vocabulary is not enforcing`,
      };
    }
    const summed = BigInt(row.sum_micro);
    const derived = BigInt(row.latest_balance);
    if (summed !== derived) {
      return {
        ok: false,
        reason: 'derivation_disagrees',
        detail:
          `bucket "${row.bucket}" of practice ${practiceId}: SUM(amountMicroUsd)=${summed} but the ` +
          `latest row's balanceAfter=${derived} — something wrote around ledger_entries_derive()`,
      };
    }
    byBucket[row.bucket as LedgerBucket] = summed;
  }

  let spendableMicroUsd = 0n;
  let totalMicroUsd = 0n;
  for (const bucket of LEDGER_BUCKETS) {
    totalMicroUsd += byBucket[bucket];
    if (SPENDABLE_BUCKETS.includes(bucket)) spendableMicroUsd += byBucket[bucket];
  }

  return { ok: true, byBucket, spendableMicroUsd, totalMicroUsd };
}

export type AdmissionRefusal =
  /** The balance could not be established. SPEC §2.4's "if the balance cannot
   *  be read, block". */
  | 'balance_unreadable'
  /** No spendable money, and none anywhere else either. The ordinary refusal. */
  | 'insufficient_balance'
  /** No SPENDABLE money, but the practice holds credit in a bucket the debit
   *  cannot reach. See the header — reported separately so the seam is loud. */
  | 'credit_not_spendable';

export type AdmissionDecision =
  | { admit: true; spendableMicroUsd: bigint }
  | { admit: false; reason: AdmissionRefusal; detail: string };

/**
 * MAY THIS PRACTICE START BILLABLE WORK?
 *
 * PURE, so the block is provable everywhere — including on QA, which RELAY
 * requires ("B8 must be proven on QA": production has no FAILED visit and
 * `failureCategory` is 100% NULL, so nothing about B8 can be proven there).
 *
 * ⚠️ THE THRESHOLD IS "MORE THAN NOTHING", AND NO PER-VISIT COST IS ESTIMATED.
 * The honest question at admission is whether the practice has any money at
 * all. Comparing against a predicted cost would need a distribution nobody has:
 * the single measured visit is the 2026-08-09 sanctioned smoke at $0.49 (13
 * calls, one specialty, one input mode, every call succeeding), which is n=1
 * and says nothing about the tail. A threshold invented from it would refuse
 * work on a guess and would be indistinguishable, in the ledger, from a
 * threshold that was measured. It arrives when B9 gives a real month.
 *
 * ⚠️ ZERO BLOCKS, AND SO DOES NEGATIVE. `> 0n`, not `>= 0n`: a wallet at
 * exactly zero cannot pay for the next visit, and a negative one is the overrun
 * ruling 89(e) permits the table to record — permitting the ROW is not
 * permitting more WORK.
 */
export function decideAdmission(read: BalanceRead): AdmissionDecision {
  if (!read.ok) {
    return {
      admit: false,
      reason: 'balance_unreadable',
      detail: `balance could not be established (${read.reason}): ${read.detail}`,
    };
  }

  if (read.spendableMicroUsd > 0n) {
    return { admit: true, spendableMicroUsd: read.spendableMicroUsd };
  }

  // Derived from the two sums rather than naming `promo`, so this stays correct
  // if the bucket vocabulary or the spendable set ever changes.
  const unspendable = read.totalMicroUsd - read.spendableMicroUsd;
  if (unspendable > 0n) {
    return {
      admit: false,
      reason: 'credit_not_spendable',
      detail:
        `spendable balance is ${read.spendableMicroUsd} micro-USD across ` +
        `{${SPENDABLE_BUCKETS.join(', ')}}, but the practice holds ${unspendable} micro-USD in ` +
        `bucket(s) no debit path can draw on — commitVisitCharge writes bucket:'paid' only`,
    };
  }

  return {
    admit: false,
    reason: 'insufficient_balance',
    detail: `spendable balance is ${read.spendableMicroUsd} micro-USD — work requires more than zero`,
  };
}
