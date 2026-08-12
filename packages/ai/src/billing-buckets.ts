// ============================================================================
// FOUNDATION B7 step 3a — WHICH BUCKET A DEBIT DRAWS ON, AND IN WHAT ORDER
// ----------------------------------------------------------------------------
// SPEC §2.4: "$10 promo bucket, separate from paid balance. Two buckets, not one
// number with a note."
//
// ⚠️ WHY THIS FILE EXISTS AT ALL — THE DEFECT IT CLOSES
// ----------------------------------------------------------------------------
// B6 wrote `bucket: 'paid'` as a literal and left a comment saying "the `promo`
// bucket is granted and drawn separately, and B7 owns that split". B7's three
// steps did not take it. B8 step 1 then read that literal correctly and drew the
// only conclusion available to it: if the debit can only reach `paid`, then
// admission must judge `paid` alone, because admitting on `promo + paid` would
// let a promo-funded practice work and then drive `paid` negative while the
// promo sat untouched. So `SPENDABLE_BUCKETS` became `['paid']` and a
// promo-only wallet was refused under its own reason, `credit_not_spendable`.
//
// Every one of those steps was right. Together they made B7 step 3 — the $10
// promo grant, 197 `grant` rows — into a change that funds nobody:
//
//     grant $10 promo to every practice, turn `BILLING_ENFORCED` on, and every
//     practice is refused `credit_not_spendable` instead of
//     `insufficient_balance`. The reason string changes. The total clinical
//     outage does not.
//
// Ruling 95 states that B7 step 3 "is what makes turning the flag on possible".
// That is the sentence this file corrects: the grant is necessary and it is not
// sufficient, and the missing half is the draw order. See RULINGS #96.
//
// ⚠️ AND THE ORDER OF THE TWO HALVES IS FORCED BY REVERSIBILITY, NOT TASTE.
// This half is pure code behind a flag that is OFF, over a table holding zero
// rows: it is reversible by reverting one constant. The grant is 197 rows into
// an APPEND-ONLY table, which can never be deleted — only offset by
// `adjustment` rows that then live beside them forever. So the reversible half
// lands first and the irreversible half lands only once its premise is true.
//
// ============================================================================
// ⚠️ ONE CONSTANT, READ BY BOTH SIDES — THE HAND-KEPT MIRROR IS DELETED
// ----------------------------------------------------------------------------
// B8 step 1 could not do better than a MIRROR: `SPENDABLE_BUCKETS` in one file
// and a string literal in another, with a source-reading test asserting they
// agree, because "no type can see a string literal in another file". That test
// was correct and it was a hand-kept list in test form — AGENTS.md: put the
// behaviour where it cannot be forgotten, on the component, not on its callers.
//
// So {@link DRAW_ORDER} is the single fact. The writer ITERATES it instead of
// naming a bucket, and {@link SPENDABLE_BUCKETS} is DERIVED from it rather than
// asserted to match it. The drift the mirror test was written to catch is now
// unrepresentable, and the gate asserts the stronger property in its place:
// `billing-charge.ts` contains no `bucket:` literal at all.
//
// ============================================================================
// ⚠️ PROMO FIRST, AND THE OVERRUN LANDS ON THE LAST BUCKET
// ----------------------------------------------------------------------------
// Two decisions, and both are the conservative one for the customer:
//
//   · PROMO IS DRAWN BEFORE PAID. The alternative — paid first — means a doctor
//     spends their own money while free credit we granted them sits unused. It
//     is indefensible to explain and there is no accounting reason for it.
//
//   · AN OVERRUN GOES ON THE **LAST** BUCKET IN THE ORDER, i.e. `paid`. Ruling
//     89(e) makes a negative balance a legal state of this table: admission is
//     checked once, before the work, while `usage` lands after the vendors
//     report, so a visit can legitimately cost more than the wallet held. That
//     overrun has to be recorded somewhere. Putting it on `promo` would mean the
//     ledger claims we granted more promo than we granted, which is a false
//     statement about our own liability; putting it on `paid` states the true
//     one — the practice owes us.
//
// ⚠️ NOTE WHAT THE OVERRUN RULE MAKES TRUE, BECAUSE IT IS THE INERTNESS PROOF.
// With every bucket at zero — which is the state of `ledger_entries` in BOTH
// environments today, 0 rows — the split degenerates to exactly one draw, on
// `paid`, for the whole charge. That is byte-for-byte the row B6 writes today.
// This change therefore cannot move a number in any environment that exists,
// and the gate asserts that degeneration by name rather than leaving it to be
// inferred.
// ============================================================================

/**
 * The `bucket` vocabulary, pinned in the database by
 * `ledger_entries_bucket_vocabulary CHECK (bucket IN ('paid','promo'))`. A new
 * bucket is a migration, and that refusal is the feature (B5's schema comment).
 */
export type LedgerBucket = 'paid' | 'promo';

/** Both buckets, in the order a REPORT should read them. Not the draw order —
 *  see {@link DRAW_ORDER}, which is the one with behaviour attached. */
export const LEDGER_BUCKETS: readonly LedgerBucket[] = ['paid', 'promo'];

/**
 * THE ORDER A DEBIT DRAWS, AND THE ONLY PLACE IT IS WRITTEN DOWN.
 *
 * `commitVisitCharge` iterates this; `SPENDABLE_BUCKETS` is derived from it.
 * Changing it changes both, which is the entire reason it exists as a constant
 * rather than as a literal in the writer.
 *
 * ⚠️ THE LAST ENTRY IS LOAD-BEARING AND IS NOT MERELY "THE ONE LEFT OVER". It
 * is the bucket an overrun is recorded against — see the header. A reorder that
 * put `promo` last would start recording overruns as promo we never granted.
 */
export const DRAW_ORDER: readonly LedgerBucket[] = ['promo', 'paid'];

/**
 * THE BUCKETS ADMISSION MAY JUDGE — DERIVED, NEVER MAINTAINED.
 *
 * A bucket is spendable exactly when the debit can draw on it. B8 step 1 had to
 * assert that relationship with a source-reading test; here it is an identity,
 * so the fail-open it was guarding against (admission judging money no debit
 * path can reach) has no way to occur.
 */
export const SPENDABLE_BUCKETS: readonly LedgerBucket[] = DRAW_ORDER;

/** One bucket's share of a single visit's charge. A POSITIVE magnitude — the
 *  writer negates it, because `ledger_entries_kind_sign` CHECKs `usage <= 0`
 *  and the negation belongs next to the row that carries the sign. */
export interface BucketDraw {
  bucket: LedgerBucket;
  amountMicroUsd: bigint;
}

/**
 * SPLIT ONE CHARGE ACROSS THE BUCKETS, IN {@link DRAW_ORDER}.
 *
 * PURE — balances in, draws out. No database, no clock, no environment. The
 * same split B6 made between decision and effect, for the same reason: the
 * writer refuses off production (F4), so anything provable has to live outside
 * it.
 *
 * ⚠️ THE INVARIANT IS CONSERVATION, AND IT IS THE ONE THE GATE LEANS ON:
 * the draws SUM TO THE CHARGE, exactly, for every input. Not "at most" and not
 * "approximately" — a split that lost a micro-dollar would under-bill silently
 * into a table where only an `adjustment` row can correct it. Integer
 * arithmetic throughout (GATE 0.4 forbids float anywhere near money), so there
 * is no rounding step here to get wrong; the single rounding already happened
 * in `chargeMicroUsd` on the total.
 *
 * ⚠️ A NEGATIVE AVAILABLE BALANCE CONTRIBUTES NOTHING, IT DOES NOT SUBTRACT.
 * `max(available, 0)` — an already-overdrawn `promo` must not make this
 * function try to "repay" it out of the current charge.
 *
 * @param chargeMicroUsd the total to be drawn, POSITIVE (or zero — see below)
 * @param available      per-bucket balance, signed, as the reader reports it
 */
export function splitCharge(
  chargeMicroUsd: bigint,
  available: Readonly<Record<LedgerBucket, bigint>>,
): BucketDraw[] {
  const draws: BucketDraw[] = [];
  let remaining = chargeMicroUsd;

  // Every bucket except the last takes only what it actually holds.
  for (const bucket of DRAW_ORDER.slice(0, -1)) {
    if (remaining <= 0n) break;
    const held = available[bucket];
    const take = held > 0n ? (held < remaining ? held : remaining) : 0n;
    if (take > 0n) {
      draws.push({ bucket, amountMicroUsd: take });
      remaining -= take;
    }
  }

  // The last bucket absorbs whatever is left, INCLUDING an overrun it cannot
  // cover. `draws.length === 0` keeps a zero charge writing exactly one row, so
  // a fully-priced visit that happens to cost nothing still records itself the
  // way it does today rather than vanishing.
  const last = DRAW_ORDER[DRAW_ORDER.length - 1];
  if (remaining > 0n || draws.length === 0) {
    draws.push({ bucket: last, amountMicroUsd: remaining });
  }

  return draws;
}
