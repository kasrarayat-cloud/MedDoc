// ============================================================================
// FOUNDATION B8 step 3 — WHAT A FAILED VISIT COSTS, AND WHO IS ACCOUNTABLE
// ----------------------------------------------------------------------------
// RELAY carried this item from B8 step 2 in these words:
//
//     "The failure path does not charge. A visit that dies at L5 has already
//      paid for L1–L4 and nothing records it. Charging there is inseparable
//      from B8's other half — 'system faults credit back via DLQ
//      classification' — because the two decide the same question from
//      opposite ends, and building the debit without the credit would BILL
//      DOCTORS FOR OUR OUTAGES."
//
// This file answers that question, and the answer is narrower than the item's
// name suggests. See the next block — it is the item's central decision.
//
// ============================================================================
// ⚠️ IT CHARGES NOTHING. NOT "NOT YET" — NOTHING, BY CONSTRUCTION.
// ----------------------------------------------------------------------------
// There is no ledger write in this module, no import of `commitVisitCharge`,
// and no code path that reaches one. A failed visit is FREE.
//
// That is not timidity and it is not a stub. It is the direction the standing
// rulings force, and the argument is short:
//
//   1. THERE IS NO EVIDENCE TO PRICE THE DECISION WITH. `failureCategory` is
//      100% NULL across every production visit and production has never held a
//      single FAILED visit. A charging policy chosen from zero observations is
//      ruling #100(b)'s "guessing dressed as engineering", verbatim — that
//      ruling refused to ship a strict constraint on a 13-of-13 sample, and
//      this is a sample of nought.
//
//   2. CHARGING IS THE DIRECTION THAT CANNOT BE WALKED BACK. `ledger_entries`
//      is APPEND-ONLY: a debit written against a doctor for a visit that
//      produced no note can only ever be offset by an `adjustment` row that
//      then lives beside it forever. Not charging can be tightened into
//      charging the day a month of data says what the number is. Charging
//      cannot be loosened at all. **Tightening is the allowed direction** —
//      the same sentence #100(b) settled the requestId biconditional with.
//
//   3. AND THE ITEM'S OWN STATED FEAR IS DISCHARGED COMPLETELY BY IT. "Building
//      the debit without the credit would bill doctors for our outages" — a
//      failure path that bills nobody for anything cannot bill anybody for an
//      outage. The auto-credit that was inseparable from the debit is
//      inseparable from a debit that does not exist.
//
// ⚠️ SO WHAT THIS MODULE ACTUALLY DELIVERS IS THE MEASUREMENT THAT DECISION IS
// WAITING ON, plus the classifier the credit half will need whenever a debit
// does appear. It prices a failed visit exactly as the success path would and
// then declines to act on the number, loudly.
//
// ============================================================================
// ⚠️ AND THAT IS WHY IT RUNS UNFLAGGED — THE TRAP THIS FILE NEARLY FELL INTO
// ----------------------------------------------------------------------------
// The obvious shape is to gate this behind `BILLING_ENFORCED` like its two
// sibling seams. It is WRONG here, and the reason is AGENTS.md's own test:
//
//     "If the work this check guards SUCCEEDED completely, what number would
//      it print?"
//
// This observation exists to inform the decision to turn `BILLING_ENFORCED`
// ON. Gated behind that same flag it produces nothing until the flip it is
// meant to advise has already happened — a close condition that cannot be
// reached, which is the defect that section is about.
//
// Running unflagged is safe **because there is nothing to be unsafe with**: no
// ledger row, no money, no clinical state, no mutation of any kind. It reads
// the meter and prices it. The cost is one drain plus one indexed read plus a
// pricing pass, on a path that has already failed and already awaited a write.
//
// ⚠️ IT CANNOT THROW, AND THAT IS LOAD-BEARING RATHER THAN TIDY. It runs inside
// the worker's FAILED branch, whose job is to get a terminal status onto the
// visit row and re-throw the original error to BullMQ. An observation that
// threw would replace a real pipeline error with a billing error as the job's
// proximate cause — destroying the diagnosis of the very failure it is
// describing. Same trade `chargeVisitUsage` makes, for the same reason.
//
// ============================================================================
// ⚠️ ACCOUNTABILITY IS READ STRUCTURALLY, NEVER FROM MESSAGE TEXT
// ----------------------------------------------------------------------------
// `ErrorCategory` already carries the answer this module needs, because the
// worker's categorizer has always been sorting errors by exactly the question
// "would retrying change anything?" — which is the same question as "was this
// us?" wearing different clothes:
//
//   permanent      → the INPUT is wrong. Corrupt audio, unsupported format, a
//                    Zod failure, a content refusal. Retrying is futile because
//                    nothing on our side is broken.
//   transient      → a blip. OURS, or the vendor's on our behalf.
//   provider_down  → a sustained upstream outage. OURS, unambiguously.
//
// ⚠️ THE UNKNOWN DEFAULT FALLS TO `transient`, AND THAT IS WHY THIS MAPPING IS
// SAFE TO REUSE. `categorizeError`'s last line is "be generous and treat
// unknowns as transient" — so an unrecognised error is classified OURS here,
// which is the direction that never bills anybody for something we cannot
// explain. The generous default was chosen for retry economics and it happens
// to be exactly right for accountability too. Written down because that is a
// coincidence, not a guarantee: an edit that made unknowns `permanent` for
// retry reasons would silently make them chargeable here.
//
// ⚠️ AND A BILLING REFUSAL IS ITS OWN THIRD ANSWER, NOT A SUBTYPE OF EITHER.
// `BillingAdmissionError` is raised BEFORE the first vendor call, so the visit
// spent nothing at all. Filing it as `input` would say the doctor's recording
// was at fault; filing it as `ours` would put it in the pool of outages we are
// measuring in order to price. Both are false. It gets `not_started`, and the
// module short-circuits without reading the meter — there is nothing there.
// ============================================================================

import { loadVisitChargeableUsage } from './billing-usage-source';
import { priceUsageRows } from './billing-charge';

/**
 * The three retry classes the worker's categorizer produces.
 *
 * ⚠️ DECLARED HERE RATHER THAN IMPORTED, AND THE DUPLICATION IS DELIBERATE.
 * `error-categorize.ts` lives in the app and keeps `@meddoc/ai` out of its
 * import graph on purpose — its header calls it a pure module and B8 step 2
 * refused to let the worker's error path acquire a dependency on the billing
 * package. Importing it in the other direction would create exactly the cycle
 * that comment exists to prevent. The union is three literals and a widening on
 * either side is caught at the call site by `tsc`.
 */
export type WorkerErrorCategory = 'transient' | 'permanent' | 'provider_down';

/**
 * WHOSE FAULT WAS THIS FAILURE, FOR MONEY PURPOSES?
 *
 * `input` is the ONLY value that could ever become chargeable. The other two
 * are the pool this item exists to protect doctors from.
 */
export type FailureAccountability =
  /** The recording or its content was the problem. Nothing on our side broke. */
  | 'input'
  /** A blip or an outage on our side, or a vendor's on our behalf. */
  | 'ours'
  /** Admission refused before the first vendor call — no money was spent. */
  | 'not_started';

/** The error class admission throws. Compared with `===` on the whole token,
 *  never searched for: AGENTS.md records four sightings of the substring trap,
 *  one of them a matcher that hit its own explanatory comment. */
const ADMISSION_ERROR_NAME = 'BillingAdmissionError';

/**
 * CLASSIFY A TERMINAL PIPELINE FAILURE.
 *
 * PURE — no database, no clock, no environment. Takes the category the worker
 * already computed and the error's own class name; reads neither the message
 * nor anything derived from one.
 *
 * ⚠️ THE ADMISSION ARM IS FIRST AND IT IS NOT AN OPTIMISATION. A
 * `BillingAdmissionError` carrying `retryCategory: 'transient'` arrives here as
 * `category: 'transient'`, so an implementation that consulted the category
 * first would file every unreadable-balance refusal into the outage pool — the
 * pool whose size is the input to a pricing decision. It would not be wrong by
 * a little; it would inflate the measurement with visits that cost nothing.
 */
export function classifyFailureAccountability(args: {
  category: WorkerErrorCategory;
  errorName: string | null;
}): FailureAccountability {
  if (args.errorName === ADMISSION_ERROR_NAME) return 'not_started';
  return args.category === 'permanent' ? 'input' : 'ours';
}

/** What a failed visit was observed to have consumed. Never written anywhere.
 *  Every arm is reachable; `gate-b8-failure-accountability.test.ts` asserts
 *  each one by name. */
export type FailedVisitObservation =
  /** Admission refused; the meter was not read because nothing was spent. */
  | { observed: 'not_started'; accountability: 'not_started' }
  /** Priced. `wouldChargeMicroUsd` is what the SUCCESS path would have taken
   *  for this same usage — and is NOT taken. */
  | {
      observed: 'priced';
      accountability: 'input' | 'ours';
      wouldChargeMicroUsd: bigint;
      componentCount: number;
    }
  /** The meter held nothing chargeable, or nothing could be priced. Carries
   *  B6's own reason so a pricing gap on the failure path is distinguishable
   *  from a genuinely free failure — B9 must not chase the second. */
  | {
      observed: 'unpriceable';
      accountability: 'input' | 'ours';
      reason: string;
      pricedSoFarMicroUsd: bigint;
    }
  /** The observation itself broke. Absorbed — see the header. */
  | { observed: 'failed'; detail: string };

/**
 * PRICE WHAT A FAILED VISIT CONSUMED, AND CHARGE NOBODY FOR IT.
 *
 * The return value is the whole product: a number an operator and B9 can read,
 * attached to a classification that says whether it was ever a candidate for
 * being charged.
 *
 * ⚠️ IT USES THE SAME LOADER AS THE SUCCESS PATH, WHICH IS THE POINT. A
 * measurement taken with a different reader would be measuring a different
 * quantity, and the whole purpose of the number is to be comparable to the one
 * the success path would produce. The loader drains the fire-and-forget meter
 * before reading (ruling #95(b)/(c)), so this sees the writes the visit
 * actually issued rather than the subset that happened to have landed.
 *
 * ⚠️ NOTE WHAT THE NUMBER IS AND IS NOT. It is what we RECORDED, never provably
 * what we SPENT — the loader's own header says so, and a usage write Postgres
 * refused left no trace by the time this runs. B9's reconciliation against the
 * vendors' invoices is the only thing that can tell the difference. So this is
 * a floor on the cost of failures, not a total.
 */
export async function observeFailedVisitUsage(args: {
  visitId: string;
  category: WorkerErrorCategory;
  errorName: string | null;
}): Promise<FailedVisitObservation> {
  const accountability = classifyFailureAccountability({
    category: args.category,
    errorName: args.errorName,
  });

  // Nothing was spent, so there is nothing to read. Short-circuits BEFORE the
  // drain — see the note on the classifier.
  if (accountability === 'not_started') {
    return { observed: 'not_started', accountability };
  }

  try {
    const rows = await loadVisitChargeableUsage(args.visitId);
    const decision = await priceUsageRows(rows);

    if (decision.charge) {
      return {
        observed: 'priced',
        accountability,
        wouldChargeMicroUsd: decision.chargeMicroUsd,
        componentCount: decision.priced.length,
      };
    }
    return {
      observed: 'unpriceable',
      accountability,
      reason: decision.reason,
      pricedSoFarMicroUsd: decision.pricedSoFarMicroUsd,
    };
  } catch (err) {
    return {
      observed: 'failed',
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}
