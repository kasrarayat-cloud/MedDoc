// ============================================================================
// FOUNDATION B8 step 2 — THE CALL SITE: ADMISSION BEFORE THE WORK, DEBIT AFTER
// ----------------------------------------------------------------------------
// Ruling 90(e): "B8 is where money is assessed ('insufficient balance blocks
// the work'), so the debit and the block belong in ONE CHANGE AND IN THAT
// ORDER." This file is that one change. It exports the two seams the pipeline
// calls and nothing else.
//
//   admitVisitOrThrow  — before any billable vendor call
//   chargeVisitUsage   — after the visit reaches READY
//
// ============================================================================
// ⚠️ IT SHIPS OFF, AND THAT IS THE ITEM'S CENTRAL DECISION — NOT A CAUTION
// ----------------------------------------------------------------------------
// `ledger_entries` holds **0 rows in production**, deliberately: rulings 89(e),
// 90(d) and 94(e) each spent design budget keeping it empty, and B7 step 3's
// promo grant — the only thing that would put money in a wallet — is PARKED
// behind this very item by ruling 94(e).
//
// So wiring this ON today does not "enable billing". It means:
//
//     every practice has a spendable balance of 0
//   → `decideAdmission` returns `insufficient_balance` for every one of them
//   → EVERY VISIT IN PRODUCTION FAILS, for every doctor, immediately
//
// A fail-closed money gate whose default is ON is normally the right posture.
// Here it is a total clinical outage, because the gate is correct and the
// wallets are empty. The ordering is the whole problem, and a flag is the
// mechanism that lets the debit and the block land together — as 90(e)
// requires — without the landing being the moment they take effect.
//
// ⚠️ SO THIS FLAG IS NOT A FEATURE TOGGLE AND MUST NOT OUTLIVE ITS PURPOSE. It
// exists to separate "the code is deployed" from "the wallets are funded". The
// sequence it is holding open is:
//
//     1. this item lands and deploys, INERT                      ← we are here
//     2. B7 step 3 grants the promo credit (197 `grant` rows)
//     3. `BILLING_ENFORCED=true`, and the block starts blocking
//
// Turning it on before step 2 is the outage described above. Deleting the flag
// after step 3 is the correct end state; leaving it OFF forever is a fail-open
// billing system wearing a shipped feature's clothes.
//
// ⚠️ AND THE DEBIT IS BEHIND THE SAME FLAG AS THE BLOCK, ON PURPOSE. They could
// have been separated — charging while not blocking is a coherent posture. It
// is the wrong one HERE: `ledger_entries` is APPEND-ONLY, so a debit written
// against a practice with no balance drives it negative with no way to remove
// the row, only to offset it with an `adjustment`. Charging before anyone can
// be funded manufactures a debt nobody agreed to, permanently, and ends the
// zero-row state three rulings depend on. One flag, both seams.
//
// ============================================================================
// ⚠️ AN UNREADABLE BALANCE IS A SYSTEM FAULT, NOT AN EMPTY WALLET
// ----------------------------------------------------------------------------
// SPEC §2.4 says "if the balance cannot be read, block", and B8 step 1 obeys
// it: `balance_unreadable` refuses. But refusing is only half a decision — the
// visit still has to be RECORDED as something, and the two refusals are not the
// same event:
//
//   insufficient_balance / credit_not_spendable
//       the practice is out of money. Retrying changes nothing. `permanent`.
//
//   balance_unreadable
//       OUR database was unreachable, or the ledger disagreed with itself.
//       The practice may be perfectly solvent. `transient`.
//
// Filing the second under the first would tell a paid-up doctor they are out of
// credit because our pool was exhausted — and would put that in the ledger's
// story of their account. It is also the half of B8 that the OTHER half exists
// to compensate: "system faults credit back via DLQ classification". A fault
// misfiled as a balance problem is a fault the auto-credit will never find.
//
// ⚠️ THE CATEGORY TRAVELS AS A TYPED PROPERTY, NEVER A MESSAGE SUBSTRING.
// `categorizeError` is a heuristic over message text, and AGENTS.md records
// four sightings of the substring trap — including one where a matcher hit its
// own explanatory comment. `retryCategory` is read structurally; nothing greps
// for the words "insufficient" or "balance" anywhere.
// ============================================================================

import { readPracticeBalance, decideAdmission } from './billing-balance';
import type { AdmissionRefusal } from './billing-balance';
import { commitVisitCharge } from './billing-charge';
import type { CommitResult } from './billing-charge';
import { loadVisitChargeableUsage } from './billing-usage-source';

/** The env var that separates "deployed" from "in effect". See the header. */
export const BILLING_ENFORCED_ENV = 'BILLING_ENFORCED';

/**
 * IS THE MONEY SEAM IN EFFECT?
 *
 * ⚠️ EXACT EQUALITY WITH `'true'`, not `!== 'false'`. The two idioms both exist
 * in this worker (`MINIO_ORPHAN_CLEANUP_ENABLED === 'true'` opt-in,
 * `STALE_VISIT_CLEANUP_ENABLED !== 'false'` opt-out) and they differ on exactly
 * the case that matters: an UNSET variable. Opt-out semantics would make a
 * missing `BILLING_ENFORCED` mean ENFORCED — so a container that simply had not
 * been told about this variable yet would block every visit it received. The
 * default has to be the inert one, and it has to survive a typo.
 */
export function billingEnforced(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  return env[BILLING_ENFORCED_ENV] === 'true';
}

/** Thrown when admission refuses. Carries its own retry classification — see
 *  the header for why that is a property and not a message. */
export class BillingAdmissionError extends Error {
  readonly reason: AdmissionRefusal;
  /** How the worker's FAILED branch should treat this. Structural. */
  readonly retryCategory: 'permanent' | 'transient';

  constructor(reason: AdmissionRefusal, detail: string) {
    super(`billing admission refused (${reason}): ${detail}`);
    this.name = 'BillingAdmissionError';
    this.reason = reason;
    // `balance_unreadable` is OUR fault and may clear on its own; the other two
    // are the practice being out of money, which a retry cannot change.
    this.retryCategory =
      reason === 'balance_unreadable' ? 'transient' : 'permanent';
  }
}

/**
 * MAY THIS VISIT'S BILLABLE WORK START?
 *
 * Returns normally when admitted, or when the seam is not in effect. Throws
 * {@link BillingAdmissionError} when refused.
 *
 * ⚠️ THROWS RATHER THAN RETURNING A DECISION, AND THAT IS THE FAIL-CLOSED
 * SHAPE. A boolean return has to be checked, and a caller that forgets the
 * check proceeds to spend money — the silent direction. An exception cannot be
 * ignored by omission.
 *
 * ⚠️ CALLED BEFORE THE FIRST VENDOR CALL, NOT MERELY "EARLY". Admission that
 * runs after transcription has already happened has not blocked the work, it
 * has blocked the *reporting* of work already paid for — the money is spent
 * either way, and the doctor gets nothing for it.
 */
export async function admitVisitOrThrow(args: {
  practiceId: string;
}): Promise<void> {
  if (!billingEnforced()) return;

  const read = await readPracticeBalance(args.practiceId);
  const decision = decideAdmission(read);
  if (decision.admit) return;

  throw new BillingAdmissionError(decision.reason, decision.detail);
}

export type ChargeOutcome =
  /** The seam is not in effect. Nothing was read and nothing was written. */
  | { charged: 'skipped_not_enforced' }
  /** Ledger rows were appended — one per bucket drawn (B7 step 3a), never
   *  zero. Plural because a charge can settle across `promo` and `paid`. */
  | { charged: 'written'; ledgerEntryIds: readonly string[]; chargeMicroUsd: bigint }
  /** Priced, and the decision was not to charge — an unpriceable component, or
   *  nothing billable at all. B6's ruling 90(a). */
  | { charged: 'declined'; reason: string }
  /** The charge threw. See the note on the catch below. */
  | { charged: 'failed'; detail: string }
  /** ADMIN-4 round 6 — the visit ALREADY carries its usage charge (a retry of a
   *  READY visit, or a replay). Nothing was read into the wallet and nothing was
   *  written. Not `failed` — no money was lost — and not `declined`, which is a
   *  pricing statement; this is "the ledger already holds it, in these rows". */
  | { charged: 'already_charged'; ledgerEntryIds: readonly string[] };

/**
 * APPEND THIS VISIT'S USAGE DEBIT.
 *
 * ⚠️ IT NEVER THROWS, AND THAT IS THE OPPOSITE OF ADMISSION ON PURPOSE. The two
 * seams fail in opposite directions because being wrong costs opposite things:
 *
 *   ADMISSION runs BEFORE the work. Refusing costs a visit that might have been
 *   affordable — recoverable, the doctor retries once funded.
 *
 *   THE DEBIT runs AFTER a finished clinical note exists. Throwing here would
 *   take a READY visit and fail it — destroying a doctor's completed work over
 *   a billing write. **No billing failure is worth a clinical outcome.**
 *
 * So the money we could not record is lost rather than the note, and the loss is
 * LOUD: it returns `failed` with the detail, and the caller logs it. That is the
 * same trade `logApiUsage` and `logAudit` already make in this codebase — an
 * audit write must never refuse a doctor's sign — and it is why B9's
 * reconciliation against the vendors' invoices is not optional. This seam can
 * under-record; only B9 can notice.
 */
export async function chargeVisitUsage(args: {
  practiceId: string;
  visitId: string;
}): Promise<ChargeOutcome> {
  if (!billingEnforced()) return { charged: 'skipped_not_enforced' };

  try {
    // The loader drains the meter first — see `billing-usage-source.ts`.
    const rows = await loadVisitChargeableUsage(args.visitId);
    const result: CommitResult = await commitVisitCharge({
      practiceId: args.practiceId,
      visitId: args.visitId,
      rows,
    });

    if (result.written) {
      return {
        charged: 'written',
        ledgerEntryIds: result.ledgerEntryIds,
        chargeMicroUsd: result.chargeMicroUsd,
      };
    }
    // ⚠️ THE NARROWING THAT USED TO LIVE HERE IS GONE, BECAUSE THE TYPE NOW
    // SAYS WHAT WAS ALWAYS TRUE. B8 step 2 wrote: "`CommitResult`'s `written:
    // false` arm types `decision` as the WHOLE `ChargeDecision` union, including
    // the `charge: true` branch that cannot occur there — B6 under-specifies the
    // pair", and narrowed rather than casting so the day it changed this would
    // stop compiling. B7 step 3a is that day: the arm is now
    // `DeclinedChargeDecision` and carries a `reason` discriminator, so the
    // impossible branch is unrepresentable instead of merely unreached.
    //
    // ⚠️ AND `balance_unreadable` IS `failed`, NOT `declined`. `declined` is a
    // pricing statement B9 must not chase; this is an infrastructure fault that
    // lost revenue on a chargeable visit, and filing it as a decline would hide
    // an outage inside a pricing statistic — the same distinction ruling 95(d)
    // drew between `balance_unreadable` and an empty wallet at admission.
    if (result.reason === 'balance_unreadable') {
      return { charged: 'failed', detail: result.detail };
    }
    // ADMIN-4 round 6 — a retry of a visit that is already on the ledger. The
    // writer refused it inside its transaction, under the per-visit lock.
    if (result.reason === 'already_charged') {
      return { charged: 'already_charged', ledgerEntryIds: result.ledgerEntryIds };
    }
    // ⚠️ AND `no_margin_rate` IS `failed` FOR THE SAME REASON — ADMIN-4.
    //
    // The first version of this change let it fall through to `declined`,
    // which routes it BYTE-IDENTICALLY to `nothing_billable` — a genuinely free
    // visit. The worker then logs `outcome: charge.charged` and NOT `reason`,
    // so a platform with no configured margin would bill nothing, forever, and
    // the only artifact would be a line indistinguishable from a mocked run.
    //
    // `declined` is a DECISION about a real visit: we looked, and there is
    // nothing to charge. "I do not know the rate" is not that decision — it is
    // the same class as a balance we could not read, and the comment above
    // already argues it.
    if (result.decision.reason === 'no_margin_rate') {
      return {
        charged: 'failed',
        detail: 'no platform margin configured at the usage instant (ADMIN-4)',
      };
    }
    return { charged: 'declined', reason: result.decision.reason };
  } catch (err) {
    return {
      charged: 'failed',
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}
