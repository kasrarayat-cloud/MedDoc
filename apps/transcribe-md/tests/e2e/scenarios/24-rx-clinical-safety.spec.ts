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

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';
import {
  countCriticalOverrides,
  getRxOverrides,
  getVisitStatus,
  rxWarningSeverities,
} from '../helpers/rxSafety';
import { attestAndSubmit } from '../helpers/sign';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the mock fixtures, started with MOCK_RX_WARNINGS=true. Run via the rx-safety project with NOTE_FORMAT_E2E=1.';

const OVERRIDE_REASON =
  'Reviewed the INR plan with the patient; benefit outweighs the bleeding risk and we will monitor INR closely.';

test.afterEach(() => {
  cleanupTestUsers();
});

/** Open the visit's Rx tab and assert it is selected. */
async function openRxTab(page: Page, visitId: string): Promise<void> {
  await page.goto(`/visits/${visitId}`);
  const rxTab = page.getByRole('tab', { name: 'Rx' });
  await rxTab.click();
  await expect(rxTab).toHaveAttribute('aria-selected', 'true');
}

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

  await openRxTab(page, visitId);

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
  const res = await page.request.post(`/api/visits/${visitId}/sign`, {
    data: { destinations: ['pdf'] },
    headers: { 'Content-Type': 'application/json' },
  });
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
  await openRxTab(page, visitId);

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
  const res = await page.request.post(`/api/visits/${visitId}/sign`, {
    data: { destinations: ['pdf'] },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.status()).toBe(200);
  expect(getVisitStatus(visitId)).toBe('SIGNED');
});

test('scenario 24: the UI Sign & Send is blocked (and the doctor is told) until the override (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx4');
  const visitId = await createReadyTextVisit(page);
  await page.goto(`/visits/${visitId}`);

  // Attempt to sign via the real Sign & Send modal with the critical un-overridden.
  await page.getByRole('button', { name: /sign & send/i }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await attestAndSubmit(page);

  // The doctor is told, NOT silently failed — and the visit stays READY.
  await expect(page.getByText(/override before signing/i)).toBeVisible({ timeout: 10_000 });
  expect(getVisitStatus(visitId)).toBe('READY');
  expect(countCriticalOverrides(visitId)).toBe(0);
});
