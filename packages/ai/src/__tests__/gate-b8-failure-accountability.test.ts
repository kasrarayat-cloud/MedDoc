// ============================================================================
// GATE — FOUNDATION B8 step 3: the failure path is CLASSIFIED and MEASURED,
// and it charges nobody.
// ----------------------------------------------------------------------------
// The item's acceptance criterion, from RELAY: "building the debit without the
// credit would bill doctors for our outages." This gate's job is to hold the
// property that discharges it, and the property is stronger than the criterion:
// **no failure is charged at all**, so no outage can be.
//
// ⚠️ WHAT WOULD MAKE EACH ARM FAIL IS NAMED BEFORE IT IS ASSERTED, per rule 7,
// and the mutations at the bottom were RUN. Two of them are the ones that
// matter and neither is a "does it go red on nonsense" check:
//
//   M1  order the classifier's arms the obvious way — category first, then the
//       admission name — and every `balance_unreadable` refusal (which carries
//       `retryCategory: 'transient'`) lands in the `ours` pool. The pool whose
//       SIZE is the input to a future pricing decision, inflated with visits
//       that spent nothing. Reddens A3.
//   M2  let the module reach a ledger writer at all. Reddens S1, which is a
//       SOURCE assertion rather than a behavioural one — see its own note for
//       why a behavioural test cannot state this property.
//
// ⚠️ AND THE HAPPY-PATH CONTROL IS HERE BECAUSE AGENTS.md SAYS THE RED
// DIRECTION IS THE CHEAPER HALF. B4 asserts the observation actually produces a
// number on a well-formed priced visit — a gate that only proved "it declines
// to charge" would pass identically against a module that did nothing at all.
// ============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const loadVisitChargeableUsage = vi.fn();
const priceUsageRows = vi.fn();

vi.mock('../billing-usage-source', () => ({
  loadVisitChargeableUsage: (...a: unknown[]) => loadVisitChargeableUsage(...a),
}));
vi.mock('../billing-charge', () => ({
  priceUsageRows: (...a: unknown[]) => priceUsageRows(...a),
}));

const { classifyFailureAccountability, observeFailedVisitUsage } = await import(
  '../billing-failure'
);

beforeEach(() => {
  loadVisitChargeableUsage.mockReset();
  priceUsageRows.mockReset();
});

// ---------------------------------------------------------------------------
// A — THE CLASSIFIER. Pure, structural, three answers.
// ---------------------------------------------------------------------------
describe('A — accountability is read structurally', () => {
  // FAILS IF: `permanent` stops meaning "the input was wrong" — the only class
  // that could ever become chargeable.
  it('A1 — `permanent` is the input’s fault', () => {
    expect(
      classifyFailureAccountability({ category: 'permanent', errorName: 'ZodError' })
    ).toBe('input');
  });

  // FAILS IF: a blip or an outage becomes chargeable. This is the arm the whole
  // item exists for.
  it('A2 — every non-permanent class is OURS', () => {
    expect(
      classifyFailureAccountability({ category: 'transient', errorName: 'Error' })
    ).toBe('ours');
    expect(
      classifyFailureAccountability({ category: 'provider_down', errorName: 'Error' })
    ).toBe('ours');
  });

  // ⚠️ THE LOAD-BEARING ORDERING ASSERTION — mutation M1.
  // FAILS IF: the admission arm is consulted after the category. A
  // `balance_unreadable` refusal carries `retryCategory: 'transient'`, so it
  // reaches the classifier as `category: 'transient'` and would be filed
  // `ours` — inflating the outage pool with visits that spent nothing.
  it('A3 — an admission refusal is `not_started` even when its category is transient', () => {
    expect(
      classifyFailureAccountability({
        category: 'transient',
        errorName: 'BillingAdmissionError',
      })
    ).toBe('not_started');
    // …and the permanent-category refusal (an empty wallet) too.
    expect(
      classifyFailureAccountability({
        category: 'permanent',
        errorName: 'BillingAdmissionError',
      })
    ).toBe('not_started');
  });

  // FAILS IF: the name match becomes a substring search. AGENTS.md records four
  // sightings of that trap; this is the negative control for the fifth.
  it('A4 — a look-alike error name gets no billing semantics', () => {
    expect(
      classifyFailureAccountability({
        category: 'permanent',
        errorName: 'BillingAdmissionErrorWrapper',
      })
    ).toBe('input');
    expect(
      classifyFailureAccountability({ category: 'permanent', errorName: null })
    ).toBe('input');
  });
});

// ---------------------------------------------------------------------------
// B — THE OBSERVATION. Reads the meter, prices it, charges nobody.
// ---------------------------------------------------------------------------
describe('B — the observation measures and does not act', () => {
  // FAILS IF: the meter is read for a visit that never made a vendor call.
  // Asserts the SHORT-CIRCUIT, not merely the return value — the loader is
  // proven un-called, which is the part a return-value assertion cannot see.
  it('B1 — `not_started` never touches the meter', async () => {
    const out = await observeFailedVisitUsage({
      visitId: 'v1',
      category: 'transient',
      errorName: 'BillingAdmissionError',
    });
    expect(out).toEqual({ observed: 'not_started', accountability: 'not_started' });
    expect(loadVisitChargeableUsage).not.toHaveBeenCalled();
    expect(priceUsageRows).not.toHaveBeenCalled();
  });

  // FAILS IF: a pricing gap on the failure path becomes indistinguishable from
  // a genuinely free failure. B9 must not chase the second.
  it('B2 — an unpriceable failure carries B6’s own reason', async () => {
    loadVisitChargeableUsage.mockResolvedValue([{ id: 'u1' }]);
    priceUsageRows.mockResolvedValue({
      charge: false,
      reason: 'unpriced',
      unpriced: [{ usageEventId: 'u1' }],
      pricedSoFarMicroUsd: 4200n,
    });
    const out = await observeFailedVisitUsage({
      visitId: 'v1',
      category: 'permanent',
      errorName: 'ZodError',
    });
    expect(out).toEqual({
      observed: 'unpriceable',
      accountability: 'input',
      reason: 'unpriced',
      pricedSoFarMicroUsd: 4200n,
    });
  });

  // FAILS IF: the observation can throw. It runs inside the worker's FAILED
  // branch; throwing would replace the real pipeline error with a billing one
  // as the job's proximate cause and destroy the diagnosis.
  it('B3 — it absorbs its own errors rather than throwing', async () => {
    loadVisitChargeableUsage.mockRejectedValue(new Error('postgres is gone'));
    const out = await observeFailedVisitUsage({
      visitId: 'v1',
      category: 'transient',
      errorName: 'Error',
    });
    expect(out).toEqual({ observed: 'failed', detail: 'postgres is gone' });
  });

  // ⚠️ THE POSITIVE CONTROL — the half everybody skips.
  // FAILS IF: the module stops producing a number at all. A gate made only of
  // the arms above passes identically against a module that returns a constant
  // and never reads anything.
  it('B4 — a priced failure yields the amount that WOULD have been charged', async () => {
    loadVisitChargeableUsage.mockResolvedValue([{ id: 'u1' }, { id: 'u2' }]);
    priceUsageRows.mockResolvedValue({
      charge: true,
      costMicroUsd: 100_000n,
      chargeMicroUsd: 150_000n,
      priced: [{ usageEventId: 'u1' }, { usageEventId: 'u2' }],
    });
    const out = await observeFailedVisitUsage({
      visitId: 'v1',
      category: 'transient',
      errorName: 'Error',
    });
    expect(out).toEqual({
      observed: 'priced',
      accountability: 'ours',
      wouldChargeMicroUsd: 150_000n,
      componentCount: 2,
    });
    // The measurement must be taken with the SUCCESS path's loader, or it is
    // not comparable to the number it exists to be compared with.
    expect(loadVisitChargeableUsage).toHaveBeenCalledWith('v1');
  });
});

// ---------------------------------------------------------------------------
// S — THE SOURCE ASSERTION. Mutation M2.
// ---------------------------------------------------------------------------
describe('S — the module cannot charge', () => {
  // ⚠️ WHY THIS IS A SOURCE READ AND NOT A BEHAVIOURAL TEST, STATED SO NOBODY
  // "UPGRADES" IT. The property is "there is NO input for which this module
  // writes a ledger row" — a universal over all inputs, which no finite set of
  // behavioural cases can establish. A behavioural gate would assert that the
  // four cases above write nothing and would pass against a module with a
  // fifth, charging branch. The absence of the import is the fact that makes
  // the universal true, so the absence is what is asserted.
  //
  // FAILS IF: a ledger writer is imported or referenced. That is exactly the
  // change that would make a failed visit chargeable.
  it('S1 — it imports no ledger writer and names no ledger table', () => {
    const src = readFileSync(
      join(__dirname, '..', 'billing-failure.ts'),
      'utf8'
    );
    // Strip comments first. The header discusses `commitVisitCharge` and
    // `ledger_entries` at length, and a matcher that read them would be
    // satisfied by PROSE — the substring trap's third sighting, arriving in
    // the file written to avoid it.
    const code = src
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .split('\n')
      .filter((line) => !line.trim().startsWith('//'))
      .join('\n');

    // Positive control: the matcher can see what IS there. Without this, a
    // stripper that ate the whole file would report a clean zero.
    expect(code).toContain('priceUsageRows');
    expect(code).toContain('loadVisitChargeableUsage');

    for (const forbidden of [
      'commitVisitCharge',
      'ledgerEntry',
      'ledger_entries',
      'splitCharge',
      'grantPromoCredit',
    ]) {
      expect(code).not.toContain(forbidden);
    }
  });
});
