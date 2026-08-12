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
// ⚠️ ADMISSION IS JUDGED ON THE **SPENDABLE** BALANCE, AND B7 step 3a CHANGED
//    WHICH BUCKETS THOSE ARE
// ----------------------------------------------------------------------------
// This file shipped with `SPENDABLE_BUCKETS = ['paid']`, and that was CORRECT
// for the system as it then stood: B6's writer hard-coded `bucket: 'paid'`, so
// admitting on `promo + paid` would have been a fail-open — a practice holding
// $10 promo and $0 paid would be admitted on a total of $10, debited against an
// empty `paid`, and the $10 nobody could reach would still be sitting there.
//
// ⚠️ AND THE COST OF THAT CHOICE TURNED OUT TO BE THE ITEM AFTER IT. With
// `promo` unspendable, B7 step 3's $10 grant funds nobody: every practice moves
// from `insufficient_balance` to `credit_not_spendable` and the total clinical
// outage is unchanged. B7 step 3a closed that by giving the debit a DRAW ORDER
// — promo first, then paid — which is the "day a step teaches the writer to
// draw promo first" this comment used to anticipate.
//
// So the set is no longer a judgement made here. It is DERIVED from
// {@link DRAW_ORDER} in `billing-buckets.ts`, and a bucket is spendable exactly
// when the debit can draw on it. The mirror this file used to keep by hand —
// and the source-reading test that policed it — are gone, because the
// relationship is now an identity rather than an agreement.
//
// ⚠️ `credit_not_spendable` STAYS, AND IS DELIBERATELY UNREACHABLE TODAY.
// With `SPENDABLE_BUCKETS == LEDGER_BUCKETS` no real balance read can produce
// it. Deleting the branch would be a LOOSENING that is hard to reverse: the day
// a third bucket lands that the writer cannot draw on, this is the refusal that
// names it instead of folding it into `insufficient_balance`. It is derived
// from the two sums rather than from the word "promo", so it needs no edit to
// keep working. The gate drives it directly, and says in its own comment that
// it is proving a structurally-unreachable branch on purpose.
//
// B6 made the same trade for an unpriceable visit and gave the reason: naming a
// refusal is "the only one where being wrong is VISIBLE". A refusal that says
// "you have money I cannot spend" is a bug report; the same refusal called
// "insufficient balance" is a lie that reconciles.
// ============================================================================

import prisma from '@meddoc/db';

import { LEDGER_BUCKETS, SPENDABLE_BUCKETS, type LedgerBucket } from './billing-buckets';

// Re-exported so every existing importer — and the gates that assert on these
// names — keeps reading them from the file that USES them. The definitions live
// in `billing-buckets.ts` because the writer needs them too, and a shared
// constant that both sides import is the whole point of that file.
export { LEDGER_BUCKETS, SPENDABLE_BUCKETS, DRAW_ORDER } from './billing-buckets';
export type { LedgerBucket } from './billing-buckets';

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
 * The only thing {@link readPracticeBalance} needs of a client — so a Prisma
 * TRANSACTION client satisfies it without this file importing Prisma's
 * transaction type. Ruling 88 (F-TYPE) forbids typing a transaction callback as
 * `typeof prisma`; naming the one method used avoids the question entirely and
 * keeps the stubbed client in the gate honest, since it must provide exactly
 * this and nothing else.
 */
export interface BalanceQueryClient {
  $queryRawUnsafe<T>(query: string, ...values: unknown[]): Promise<T>;
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
 *
 * ⚠️ `client` EXISTS SO THE DEBIT CAN READ INSIDE ITS OWN TRANSACTION, and it is
 * a parameter rather than a second query on purpose. B7 step 3a needs the
 * per-bucket balance to split a charge, and it needs it under the same advisory
 * locks it is about to insert under. Writing a second, subtly different balance
 * query there would have given the system two answers to one question — the
 * shape ruling 04b(c) forbids: "a tested helper production has stopped calling,
 * beside an untested one it does call, is worse than no test". One query, two
 * callers, and the two-way agreement check applies to both.
 */
export async function readPracticeBalance(
  practiceId: string,
  client: BalanceQueryClient = prisma,
): Promise<BalanceRead> {
  let rows: BucketRow[];
  try {
    rows = await client.$queryRawUnsafe<BucketRow[]>(BUCKET_BALANCE_SQL, practiceId);
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
        `bucket(s) no debit path can draw on — commitVisitCharge iterates DRAW_ORDER, ` +
        `and a bucket outside it can be granted but never spent`,
    };
  }

  return {
    admit: false,
    reason: 'insufficient_balance',
    detail: `spendable balance is ${read.spendableMicroUsd} micro-USD — work requires more than zero`,
  };
}
