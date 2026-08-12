// ============================================================================
// FOUNDATION B7 step 3b — THE PROMO GRANT WRITER, AND WHY IT SHIPS UNWIRED
// ----------------------------------------------------------------------------
// SPEC §2.4: "$10 promo bucket, separate from paid balance. Two buckets, not
// one number with a note."
//
// ⚠️ THE FINDING THAT CREATED THIS STEP — THE BACKFILL IS NOT SUFFICIENT
// ----------------------------------------------------------------------------
// RELAY records B7 step 3 as "197 rows into an append-only table": one `grant`
// row per practice that exists TODAY. That is a one-shot backfill, and it says
// nothing about a practice created tomorrow.
//
// There is exactly ONE production path that creates a practice — `auth.ts:511`,
// inside the signup transaction (enumerated by ORM method, by raw SQL and by
// table, positive-controlled; every other site is a seed or the 2026-04-12
// tenancy migration). It writes NO ledger row, because nothing anywhere writes
// a `grant` row: the only two `ledger_entries` writers in the tree are the
// Stripe webhook (`topup`) and `commitVisitCharge` (`usage`).
//
// So with the backfill done and `BILLING_ENFORCED` turned on:
//
//     a practice created after the backfill holds 0 rows, so
//     `readPracticeBalance` reports spendable 0, so `decideAdmission` returns
//     `insufficient_balance`, so `admitVisitOrThrow` THROWS — and the first
//     visit of every new signup fails.
//
// ⚠️ THIS IS RULING #96(a)'s SHAPE, ONE LINK FURTHER DOWN THE CHAIN. There the
// grant funded nobody because no debit path could reach `promo`; here it funds
// nobody who arrives after it runs. Both times every step was individually
// right and the defect lived in the JOIN. And the discovery channel is the
// worst available: it is invisible in every environment until a real doctor
// signs up and records their first visit.
//
// The cure is that a grant is not an event that happened once — it is a
// PROPERTY OF BECOMING A PRACTICE. So the writer below is written to serve two
// call sites, and B7 step 3c takes both of them in one owner-gated change:
//
//     1. the signup transaction in `auth.ts` — every practice from now on
//     2. the backfill — every practice that already exists
//
// ============================================================================
// ⚠️ AND IT SHIPS UNWIRED, WHICH IS B6's PRECEDENT AND NOT A HALF-SHIP
// ----------------------------------------------------------------------------
// Ruling 90(e) shipped `commitVisitCharge` complete and with no call site, and
// gave the reason: wiring it would have appended rows against real practices
// before the surrounding decisions existed, on a table where a row can never be
// removed — only offset by an `adjustment` that then lives beside it forever.
//
// The identical argument applies here with one difference that makes it
// stronger, not weaker: this writer's rows are IRREVERSIBLE IN THE SAME WAY,
// and the ruling that makes them coherent — #96, promo drawn before paid — is
// PROVISIONAL and less than a day old. #96's own reversal path says, in as many
// words, "B7 step 3 must NOT be executed if this is reversed". Wiring either
// call site tonight would build an unremovable artifact on a decision the war
// room has not yet seen.
//
// So this step ships the DECISION, proven, and step 3c executes it. What is
// reversible lands first; what cannot be taken back waits until its premise has
// been reviewed. That is ruling #96(b)'s ordering argument applied to itself.
//
// ============================================================================
// ⚠️ THIS WRITER IS **NOT** PRODUCTION-ONLY, UNLIKE `commitVisitCharge`
// ----------------------------------------------------------------------------
// B6's writer takes `assertProdDatabase()` as its first statement (ruling
// 90(c)). This one deliberately does not, and the difference is not laziness:
//
//   · A CHARGE IS A CLAIM AGAINST A CUSTOMER. Writing one outside production
//     records money owed by somebody who owes nothing — a false financial
//     statement, in an environment that should hold none.
//
//   · A GRANT IS OUR OWN MONEY GOING OUT. Writing one on QA states that a
//     synthetic practice was given synthetic credit, which is TRUE of that
//     environment and reconciles to nothing outside it.
//
// ⚠️ AND THE COST OF GETTING THIS WRONG IS ALREADY MEASURED. B6's header
// records what prod-only cost it: nothing provable can run where a test is
// allowed to run. `readPracticeBalance` was deliberately NOT made prod-only for
// exactly that reason ("a reader that refused off production would make the
// block unprovable anywhere"). The QA behavioural proof of B8 has been owed
// across three items and its ADMIT half is unwalkable without a `grant` row on
// QA — a prod-only grant writer would make that permanently impossible while
// looking like the careful choice.
//
// The environment guard belongs on the BACKFILL, which is a one-shot act
// against a known population, not on the function that expresses what a grant
// is. Step 3c carries it.
//
// ============================================================================

import { prisma } from '@meddoc/db';

import type { LedgerBucket } from './billing-buckets';

/**
 * THE PROMO GRANT, IN MICRO-DOLLARS — SPEC §2.4's "$10", written down once.
 *
 * ⚠️ IT IS A CONSTANT AND NOT A PARAMETER, DELIBERATELY. An `amountMicroUsd`
 * argument would make the size of a grant a property of each CALL SITE, so the
 * backfill and the signup path could drift apart, and a future caller could
 * invent a number. GATE 0.4 puts the whole ledger in integer micro-dollars, and
 * ruling #93(c) records that the denomination set is an allowlist rather than a
 * bound for the same reason: the set of amounts that can reach the ledger
 * should be defined by a reviewed diff, never by arithmetic.
 *
 * ⚠️ AND CHANGING IT IS NOT RETROACTIVE — it cannot be. Rows already written
 * carry the amount they were written with, on a table that refuses UPDATE. So
 * this constant is the grant for practices granted FROM NOW ON, and B9 reads
 * the amount off each row rather than off this file.
 */
export const PROMO_GRANT_MICRO_USD = 10_000_000n;

/** The bucket a promo grant lands in. Pinned by
 *  `ledger_entries_bucket_vocabulary`; named here rather than inlined so the
 *  reader of a `grant` row can find the vocabulary from this file. */
const PROMO_BUCKET: LedgerBucket = 'promo';

/**
 * THE IDEMPOTENCY KEY FOR A PRACTICE'S PROMO GRANT — ONE, FOREVER.
 *
 * ⚠️ THE KEY CARRIES NO OCCASION, AND THAT IS THE POINT. `visitChargeKey` is
 * per (visit, bucket) because a visit is an event that can legitimately recur.
 * A promo grant is not: SPEC says a practice HAS a $10 promo bucket, so the
 * fact being recorded is "this practice has been granted its promo", which can
 * be true at most once. Keying on a date, a run id or an attempt number would
 * make a second grant merely a different row rather than a refused one.
 *
 * ⚠️ SO THE BACKFILL AND THE SIGNUP PATH CANNOT DOUBLE-GRANT EACH OTHER, AND
 * THAT IS WHY THEY SHARE ONE KEY FUNCTION. The dangerous interleaving is
 * ordinary rather than exotic: a doctor signs up while the backfill is running,
 * their practice is created with a grant, and the backfill's own population —
 * re-derived moments earlier — still contains it. With one key the second
 * insert is refused by `ledger_entries.idempotencyKey`'s GLOBAL unique index,
 * in the database, rather than by a check-then-write race between two processes
 * that cannot see each other.
 *
 * ⚠️ IDEMPOTENCY MATTERS MORE ON THIS TABLE THAN ANYWHERE. A duplicate charge
 * on a mutable table is an UPDATE away from fixed. Here a duplicate grant can
 * only be offset by an `adjustment` row, so the mistake and its correction both
 * live in the ledger forever, and every future reader has to understand both.
 */
export function promoGrantKey(practiceId: string): string {
  return `grant:promo:practice:${practiceId}`;
}

/** What happened to one practice's grant. */
export type GrantResult =
  | { granted: true; ledgerEntryId: string; amountMicroUsd: bigint }
  /** The practice already holds its promo grant. NOT an error — this is the
   *  idempotency key doing its job, and the backfill counts these separately
   *  from the rows it wrote so a re-run is legible rather than silent. */
  | { granted: false; reason: 'already_granted' };

/** Postgres's unique-violation SQLSTATE. Matched by CODE, never by message
 *  text: AGENTS.md records four sightings of the substring trap, and a driver
 *  is free to reword an error string between versions. */
const UNIQUE_VIOLATION = 'P2002';

/**
 * APPEND ONE `grant` ROW FOR A PRACTICE, OR REPORT THAT IT ALREADY HAS ONE.
 *
 * ⚠️ THE AMOUNT IS POSITIVE, AND THE DATABASE AGREES. `ledger_entries_kind_sign`
 * CHECKs `grant > 0`: money arriving is a positive amount, the mirror of the
 * negation `commitVisitCharge` performs for `usage`. Nothing here negates.
 *
 * ⚠️ `pricing` IS NOT SET, AND THAT IS A CONSTRAINT RATHER THAN AN OMISSION.
 * `ledger_entries_usage_has_pricing` reads `kind <> 'usage' OR pricing IS NOT
 * NULL` — a grant is money arriving, not money computed, and inventing a
 * pricing object for one would be a claim nobody made (ruling 90(d)).
 *
 * ⚠️ `balanceAfter`, `seq` AND `practiceIdSnapshot` ARE DATABASE-OWNED. The
 * derive trigger computes them and IGNORES whatever the caller sent — it does
 * not validate, it discards. `practiceIdSnapshot` is passed only because
 * Prisma's generated type requires it, from the SAME variable as `practiceId`
 * in the same statement, so the pair cannot drift. B6's writer records this
 * seam defect at length; it is not re-argued here.
 *
 * ⚠️ NO ADVISORY LOCK IS TAKEN, AND THE REASON IS THE DEADLOCK ORDER.
 * `commitVisitCharge` locks because it READS a balance and then decides how
 * much to draw from it — a read-then-write the derive trigger's per-row lock
 * does not close. This writer reads nothing: it inserts a fixed amount into one
 * bucket, and the trigger's own lock serialises the balance derivation. Taking
 * a second lock here would be inert at best; `billing-charge.ts`'s header
 * already states the invariant this preserves — "a grant takes `promo` alone
 * and a top-up takes `paid` alone. No cycle exists."
 *
 * @param client the transaction client when a caller has one (the signup path
 *   MUST pass its `tx`, so a grant that fails rolls the practice back with it
 *   rather than leaving a practice nobody funded); defaults to `prisma`.
 */
export async function grantPromoCredit(
  practiceId: string,
  client: Pick<typeof prisma, 'ledgerEntry'> = prisma,
): Promise<GrantResult> {
  try {
    const created = await client.ledgerEntry.create({
      data: {
        practiceId,
        practiceIdSnapshot: practiceId,
        bucket: PROMO_BUCKET,
        kind: 'grant',
        amountMicroUsd: PROMO_GRANT_MICRO_USD,
        idempotencyKey: promoGrantKey(practiceId),
        note: `SPEC §2.4 promo grant — $${(PROMO_GRANT_MICRO_USD / 1_000_000n).toString()}`,
      },
      select: { id: true },
    });

    return {
      granted: true,
      ledgerEntryId: created.id,
      amountMicroUsd: PROMO_GRANT_MICRO_USD,
    };
  } catch (err) {
    // ⚠️ ONLY THE UNIQUE VIOLATION IS ABSORBED, AND ONLY ON *THIS* KEY.
    // Swallowing every error would turn a CHECK violation, a dead connection or
    // a missing trigger into "already granted" — a refusal reported as a
    // success, which on this table is how a practice silently ends up unfunded
    // with nothing recording it. Everything else propagates.
    if (isPromoGrantCollision(err, practiceId)) {
      return { granted: false, reason: 'already_granted' };
    }
    throw err;
  }
}

/**
 * Is this error the promo-grant unique index refusing a second grant?
 *
 * ⚠️ THE TARGET IS CHECKED, NOT JUST THE CODE. `idempotencyKey` is GLOBALLY
 * unique, so a `P2002` on this table could in principle come from another key
 * shape entirely; and `ledger_entries` also carries `UNIQUE(practiceId, bucket,
 * seq)`, whose violation means the derive trigger's lock was lost — a loud
 * structural fault that must NEVER be reported as "already granted". Reading
 * the code alone would convert that into a silent success.
 */
function isPromoGrantCollision(err: unknown, practiceId: string): boolean {
  if (typeof err !== 'object' || err === null) return false;
  const e = err as { code?: unknown; meta?: { target?: unknown } };
  if (e.code !== UNIQUE_VIOLATION) return false;

  const target = e.meta?.target;
  const fields = Array.isArray(target) ? target.map(String) : typeof target === 'string' ? [target] : [];

  // The `practiceId` argument is unused for matching on purpose: the driver
  // reports the CONSTRAINT, not the value. It stays in the signature so the
  // call site reads as "this practice's collision" and so a future matcher that
  // does need the value has it.
  void practiceId;

  return fields.some((f) => f === 'idempotencyKey' || f.includes('idempotencyKey'));
}
