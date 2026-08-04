// ============================================================================
// Scenario 24 — Rx clinical-safety: warnings rail · critical-override · sign gate
// ----------------------------------------------------------------------------
// 🔴 PATIENT-SAFETY. Layer 7c drafts prescriptions + safety warnings (critical /
// major / minor). A CRITICAL warning must be explicitly overridden (with a typed
// reason, audit-logged) before the visit can be signed — and that gate is
// SERVER-ENFORCED at POST /api/visits/[id]/sign (HTTP 422 OVERRIDE_REQUIRED), not
// just a disabled button (the F5-1 hardening: a direct/scripted caller must not
// be able to bypass it). Major/minor warnings inform but never block.
//
// Driven under MOCK with MOCK_RX_WARNINGS=true (the populated tm_rx_drafting
// fixture: 1 critical + 1 major + 1 minor + 3 prescriptions; L7c's deterministic
// validateRxDose floor appends one extra MINOR (warfarin complex-dosing) but
// never a critical here — no allergies, in-range doses — so the critical count
// is exactly 1, which the specs assert). Because that
// fixture would block every other spec's sign, this runs in its own `rx-safety`
// Playwright project against an app started with the flag. Gated on
// NOTE_FORMAT_E2E=1 (a fresh build with the mock fixtures present).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';
import {
  countCriticalOverrides,
  getRxOverrides,
  getVisitStatus,
  rxWarningSeverities,
} from '../helpers/rxSafety';
import { openRxGate } from '../helpers/rxGate';
import { signViaApi } from '../helpers/sign';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the mock fixtures, started with MOCK_RX_WARNINGS=true. Run via the rx-safety project with NOTE_FORMAT_E2E=1.';

const OVERRIDE_REASON =
  'Reviewed the INR plan with the patient; benefit outweighs the bleeding risk and we will monitor INR closely.';

test.afterEach(() => {
  cleanupTestUsers();
});

// ⚠️ RE-POINTED 2026-08-04, F-ret.1 tail. The local `openRxTab` opened a tab
// that cannot render under the shipped flag set; the gate is now inline on the
// read-only paper and `openRxGate` waits for it instead. The full arithmetic,
// the measured DOM and the reason this is a STRENGTHENING rather than a
// weakening are in `helpers/rxGate.ts`. Every assertion below is unchanged.

test('scenario 24: the Rx rail renders warnings by severity + the drafted prescriptions (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx1');
  const visitId = await createReadyTextVisit(page);

  // The fixture produced exactly one CRITICAL warning (+ at least one non-critical).
  const sevs = rxWarningSeverities(visitId);
  expect(sevs.filter((s) => s === 'critical')).toHaveLength(1);
  expect(sevs.some((s) => s !== 'critical')).toBe(true);

  await openRxGate(page, visitId);

  // Critical warning renders, not yet overridden, with an Override control.
  const critical = page.locator('.qm-warn-critical[data-overridden="false"]').first();
  await expect(critical).toBeVisible();
  await expect(page.locator('button.qm-warn-override-btn')).toBeVisible();
  // A non-critical warning renders too (major→serious / minor→info), with NO
  // override affordance — it informs, it doesn't gate.
  await expect(page.locator('.qm-warn-serious, .qm-warn-info').first()).toBeVisible();
  // The drafted prescriptions render in the left pane.
  await expect(page.locator('.qm-lin-rx-name').first()).toBeVisible();
  expect(await page.locator('.qm-lin-rx-name').count()).toBeGreaterThanOrEqual(3);
});

test('scenario 24: signing with an un-overridden CRITICAL warning is blocked server-side (422) (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx2');
  const visitId = await createReadyTextVisit(page);
  expect(rxWarningSeverities(visitId).filter((s) => s === 'critical')).toHaveLength(1);
  expect(countCriticalOverrides(visitId)).toBe(0);

  // Hit the sign endpoint DIRECTLY (the gate must hold for non-UI callers too —
  // the F5-1 hardening). page.request rides the browser's auth cookie.
  const res = await signViaApi(page, visitId, { destinations: ['pdf'] });
  expect(res.status()).toBe(422);
  const body = (await res.json()) as { code?: string; error?: string };
  expect(body.code).toBe('OVERRIDE_REQUIRED');
  expect(body.error).toMatch(/override before signing/i);

  // SAFETY-CRITICAL: the visit was NOT signed and no override was fabricated.
  expect(getVisitStatus(visitId)).toBe('READY');
  expect(countCriticalOverrides(visitId)).toBe(0);
});

test('scenario 24: overriding the critical warning records the audit row + clears the sign gate (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx3');
  const visitId = await createReadyTextVisit(page);
  await openRxGate(page, visitId);

  // Override the critical warning: open the modal, type a reason, confirm.
  await page.locator('button.qm-warn-override-btn').first().click();
  const reason = page.locator('textarea#override-reason');
  await expect(reason).toBeVisible({ timeout: 10_000 });
  await reason.fill(OVERRIDE_REASON);
  await page.getByRole('button', { name: /confirm override/i }).click();
  await expect(page.getByText('Override recorded')).toBeVisible({ timeout: 10_000 });

  // The audit row is persisted at severity='critical' with the typed reason.
  const overrides = getRxOverrides(visitId);
  expect(overrides).toHaveLength(1);
  expect(overrides[0].severity).toBe('critical');
  expect(overrides[0].reason).toContain('benefit outweighs');
  expect(countCriticalOverrides(visitId)).toBe(1);

  // The card flips to the overridden chip.
  await expect(
    page.locator('.qm-warn-critical[data-overridden="true"] .qm-warn-overridden').first(),
  ).toBeVisible();

  // Sign now SUCCEEDS — even though the major/minor warnings remain un-overridden
  // (the tier distinction: only critical gates).
  const sevs = rxWarningSeverities(visitId);
  expect(sevs.some((s) => s !== 'critical')).toBe(true);
  const res = await signViaApi(page, visitId, { destinations: ['pdf'] });
  expect(res.status()).toBe(200);
  expect(getVisitStatus(visitId)).toBe('SIGNED');
});

test('scenario 24: the UI sign flow is blocked (and the doctor is told) until the override (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx4');
  const visitId = await createReadyTextVisit(page);
  await page.goto(`/visits/${visitId}`);

  // ⚠️ RE-POINTED 2026-08-04 — a SECOND, DISTINCT drift, not the Rx tab. This
  // test never touched the rail; it timed out on
  // `getByRole('button', { name: /sign & send/i })`, because the Rounds stage
  // reaches signing through the action rail → gate flow, not a bare button.
  //
  // ⚠️ AND THE FIRST REPAIR WAS WRONG, WHICH IS WHY IT WAS DRIVEN. Swapping in
  // `openSignFlow` failed at `helpers/sign.ts:95` — "the gate flow never
  // presented the attestation". That helper is correct and the product is
  // correct; the ASSUMPTION was wrong. On a visit whose critical interaction is
  // un-overridden the flow never reaches attestation at all, so a helper that
  // waits for it can only time out.
  //
  // The old shape — attest, submit, read the refusal — has NO analogue here.
  // Under Rounds the doctor is stopped one step EARLIER and told why, which is
  // a stronger property than the one this test used to assert: they never get
  // to attest to a note they cannot sign.
  //
  // Measured on the QA stack against the flag-ON image, not inferred:
  //   steps  "1 CRITICAL INTERACTIONS / 2 DOCUMENTATION LEVEL / 3 SIGN & LOCK"
  //   lock   "🔒 Complete blockers to advance — 1 critical interaction outstanding"
  //   rounds-gate-attest  count = 0
  //
  // ⚠️ FLAG-DEPENDENT ON PURPOSE, AND SAID OUT LOUD. These testids exist only on
  // the Rounds gate flow. A `NEXT_PUBLIC_SKIN_ROUNDS=false` rollback would need
  // the legacy modal path back. That is not hedged for here because F-ret.3
  // removes the flag together with the flag-OFF arm — a branch written now would
  // be written for deletion this week. If that plan changes, this is the test to
  // revisit.
  await page.getByTestId('rounds-review-sign').first().click();

  // The flow opens ON the Rx blocker.
  await expect(
    page.getByTestId('rounds-gate-host-rx'),
    'the sign flow did not present the Rx blocker — a critical interaction ' +
      'would be skipped on the way to signing',
  ).toBeVisible({ timeout: 15_000 });

  // The doctor is TOLD, and told specifically — the count is named, so a lock
  // that appears with a generic message while the real blocker is something
  // else does not satisfy this.
  await expect(page.getByTestId('rounds-gate-lock')).toContainText(
    /1 critical interaction outstanding/i,
  );

  // THE ASSERTION THAT MATTERS: the attestation is step 3 and is not reachable.
  // This is what would catch a regression letting a doctor attest past an
  // un-reviewed critical interaction.
  await expect(page.getByTestId('rounds-gate-attest')).toHaveCount(0);

  // SAFETY-CRITICAL, unchanged: the visit stays READY and nothing fabricated an
  // override on the way through.
  expect(getVisitStatus(visitId)).toBe('READY');
  expect(countCriticalOverrides(visitId)).toBe(0);
});
