// ============================================================================
// Scenario 25 — Rx override gate: PER-WARNING correlation (inflation bypass)
// ----------------------------------------------------------------------------
// 🔴 PATIENT-SAFETY · regression for fix/rx-override-gate-correlation.
//
// F5-1 server-enforced the critical-Rx override gate, but the original check
// compared a BARE COUNT of severity='critical' override rows against the
// critical-warning count. That let an authenticated visit owner mint
// fabricated / duplicate 'critical' override rows (with warningIds that match
// NO real warning) to inflate the count and sign PAST a genuine, un-reviewed
// critical warning.
//
// The hardened gate clears the READY→SIGNED transition ONLY when EVERY
// persisted critical warning has a matching override keyed by its REAL id
// (rx-warning-<index>). recordOverride additionally validates the submitted
// warningId + severity against rxDrafts on write, so the legit UI flow keeps
// working while fabricated rows are rejected/uncounted.
//
// ACCEPTANCE PROPERTY proven here: the gate clears IFF every genuine critical
// warning has been individually overridden with a server-validated matching
// warningId — fabricated/duplicate/mismatched rows never substitute for it.
//
// Same env as scenario 24: runs ONLY via `--project=rx-safety` against an app
// started with MOCK_RX_WARNINGS=true (the populated tm_rx_drafting fixture:
// exactly 1 critical warning), gated on NOTE_FORMAT_E2E=1.
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
  seedFabricatedCriticalOverride,
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

/** Override the visit's (single) critical warning through the real UI modal —
 *  the legit path. Uses the production rail → modal → recordOverride flow, so
 *  the warningId sent is the real `rx-warning-<index>` the rail derives. */
async function overrideCriticalViaUi(page: Page, visitId: string): Promise<void> {
  // ⚠️ RE-POINTED 2026-08-04, F-ret.1 tail — this was the SECOND copy of a tab
  // dance that cannot render under the shipped flag set, which is why both
  // specs broke identically and why the replacement lives in one helper.
  // Arithmetic and measured DOM: `helpers/rxGate.ts`.
  await openRxGate(page, visitId);

  await page.locator('button.qm-warn-override-btn').first().click();
  const reason = page.locator('textarea#override-reason');
  await expect(reason).toBeVisible({ timeout: 10_000 });
  await reason.fill(OVERRIDE_REASON);
  await page.getByRole('button', { name: /confirm override/i }).click();
  await expect(page.getByText('Override recorded')).toBeVisible({ timeout: 10_000 });
}

test('scenario 25: fabricated "critical" override rows do NOT clear the sign gate (count-inflation closed) (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rxc1');
  const visitId = await createReadyTextVisit(page);

  // Exactly one genuine critical warning, zero genuine overrides.
  expect(rxWarningSeverities(visitId).filter((s) => s === 'critical')).toHaveLength(1);
  expect(countCriticalOverrides(visitId)).toBe(0);

  // THE ATTACK: mint 3 fabricated 'critical' override rows whose warningIds
  // match no real warning. Under the OLD bare-count gate, 3 ≥ 1 would clear it.
  seedFabricatedCriticalOverride(visitId, 'fab-a');
  seedFabricatedCriticalOverride(visitId, 'fab-b');
  seedFabricatedCriticalOverride(visitId, 'fab-c');
  expect(countCriticalOverrides(visitId)).toBe(3);

  // Hit the sign endpoint DIRECTLY (the gate must hold for scripted callers).
  const res = await signViaApi(page, visitId, { destinations: ['pdf'] });

  // Still blocked: the 3 fabricated rows cover NONE of the real critical
  // warning's id, so coverage is unmet.
  expect(res.status()).toBe(422);
  const body = (await res.json()) as {
    code?: string;
    error?: string;
    warnings?: Array<{ warningId?: string; severity?: string }>;
  };
  expect(body.code).toBe('OVERRIDE_REQUIRED');
  expect(body.error).toMatch(/override before signing/i);
  // The unmet warning is surfaced with its REAL canonical id.
  expect(body.warnings?.length).toBeGreaterThanOrEqual(1);
  expect(body.warnings?.[0]?.warningId).toMatch(/^rx-warning-\d+$/);

  // SAFETY-CRITICAL: the visit was NOT signed.
  expect(getVisitStatus(visitId)).toBe('READY');
});

test('scenario 25: a genuine override of the REAL warning clears the gate → 200/SIGNED (legit flow intact) (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rxc2');
  const visitId = await createReadyTextVisit(page);
  expect(rxWarningSeverities(visitId).filter((s) => s === 'critical')).toHaveLength(1);

  await overrideCriticalViaUi(page, visitId);

  // The recorded row is keyed by the REAL canonical id (rx-warning-<index>),
  // at severity='critical', with the typed reason — recordOverride accepted it.
  const overrides = getRxOverrides(visitId);
  expect(overrides).toHaveLength(1);
  expect(overrides[0].severity).toBe('critical');
  expect(overrides[0].warningId).toMatch(/^rx-warning-\d+$/);
  expect(overrides[0].reason).toContain('benefit outweighs');

  // Sign now SUCCEEDS — every genuine critical warning is individually covered.
  const res = await signViaApi(page, visitId, { destinations: ['pdf'] });
  expect(res.status()).toBe(200);
  expect(getVisitStatus(visitId)).toBe('SIGNED');
});

test('scenario 25: a genuine override clears the gate even amid fabricated noise rows (coverage, not count) (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rxc3');
  const visitId = await createReadyTextVisit(page);

  // Pre-existing junk 'critical' rows on the visit (well-formed-but-wrong id +
  // a plausible-looking out-of-range positional id) must neither clear the
  // gate on their own nor block a genuine override from clearing it.
  seedFabricatedCriticalOverride(visitId, 'totally-bogus');
  seedFabricatedCriticalOverride(visitId, 'rx-warning-9999');

  // Genuine override of the real critical warning via the UI.
  await overrideCriticalViaUi(page, visitId);

  // Sign SUCCEEDS — the genuine, real-id override provides full coverage; the
  // bogus rows are simply ignored by the gate.
  const res = await signViaApi(page, visitId, { destinations: ['pdf'] });
  expect(res.status()).toBe(200);
  expect(getVisitStatus(visitId)).toBe('SIGNED');
});
