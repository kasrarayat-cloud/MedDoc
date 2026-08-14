// ============================================================================
// Scenario 24 — the prescription-safety surface is DELETED, and extraction is NOT
// ----------------------------------------------------------------------------
// 🔴 PATIENT-SAFETY-ADJACENT, AND DELIBERATELY SO. Owner ruling #109 deleted the
// surface that DISPLAYED prescription safety and the sign gate that blocked on
// it. This file replaces scenarios 24 and 25, which proved that gate.
//
// ⚠️ THE REPLACEMENT IS NOT "DELETE THE TESTS". Two specs asserted a 422 and an
// override flow; deleting them would leave NOTHING watching the boundary the
// ruling actually drew, and a half-applied removal — surface gone, server
// refusal left behind — would present to a doctor as an unclearable block with
// no door in. So this asserts BOTH sides of that boundary:
//
//   DELETED   no Rx surface renders, and `POST /sign` no longer refuses
//   KEPT      L7c still extracts the warnings and they are still persisted
//
// The second half is the one that would otherwise rot silently. The ruling
// scoped the deletion to the SURFACE and left the DATA's disposition open; if a
// later change quietly stops extracting, nothing else in the suite would say so
// — the gate that used to depend on the data is gone.
//
// SAME ENV AS THE SPECS IT REPLACES. Runs only via `--project=rx-safety`
// against an app started with MOCK_RX_WARNINGS=true (the populated
// tm_rx_drafting fixture: 1 critical + 1 major + 1 minor + 3 prescriptions),
// gated on NOTE_FORMAT_E2E=1. The fixture is kept precisely because a visit
// carrying a REAL critical warning is now the interesting case: it must sign.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';
import {
  countCriticalOverrides,
  getVisitStatus,
  rxWarningSeverities,
} from '../helpers/rxSafety';
import { signViaApi } from '../helpers/sign';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the mock fixtures, started with MOCK_RX_WARNINGS=true. Run via the rx-safety project with NOTE_FORMAT_E2E=1.';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 24: EXTRACTION SURVIVES — the critical warning is still produced and persisted (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx1');
  const visitId = await createReadyTextVisit(page);

  // ⚠️ THIS IS THE HALF THAT WOULD ROT SILENTLY. The ruling deleted the surface
  // and explicitly left the DATA in place with its disposition open. Nothing
  // else in the suite reads these rows any more, so without this the pipeline
  // could stop emitting warnings entirely and every remaining test would still
  // be green.
  const sevs = rxWarningSeverities(visitId);
  expect(
    sevs.filter((s) => s === 'critical'),
    'L7c stopped producing the critical warning — extraction was NOT in scope of ruling #109',
  ).toHaveLength(1);
  expect(
    sevs.some((s) => s !== 'critical'),
    'the non-critical warnings stopped being produced too',
  ).toBe(true);
});

test('scenario 24: THE SURFACE IS GONE — a visit with a real critical warning shows none of it (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx2');
  const visitId = await createReadyTextVisit(page);

  // Precondition, asserted rather than assumed: this visit genuinely carries a
  // critical warning. Without it the absences below are vacuous — they would
  // hold on any visit that never had anything to show.
  expect(rxWarningSeverities(visitId).filter((s) => s === 'critical')).toHaveLength(1);

  await page.goto(`/visits/${visitId}`);
  await expect(page.getByTestId('rounds-review-sign').first()).toBeVisible({
    timeout: 30_000,
  });

  // Every artefact of the deleted surface, by the name it had.
  await expect(page.getByTestId('review-doc-rx-gate')).toHaveCount(0);
  await expect(page.locator('[class*="qm-warn"]')).toHaveCount(0);
  await expect(page.locator('[class*="qm-lin-rx"]')).toHaveCount(0);
  await expect(page.locator('[data-gate-slot="rx"]')).toHaveCount(0);
  await expect(page.getByTestId('rounds-gate-step-rx')).toHaveCount(0);
  await expect(page.getByTestId('rounds-critical-band')).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Rx' })).toHaveCount(0);
  await expect(page.getByText('Prescription safety')).toHaveCount(0);

  // POSITIVE CONTROL — the page rendered something. Eight zeroes against a
  // failed navigation look identical to eight zeroes against a working page,
  // and this file is nothing BUT zeroes.
  await expect(page.getByTestId('rounds-sheet')).toBeVisible();
});

test('scenario 24: THE SERVER NO LONGER REFUSES — an un-overridden critical warning signs (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);

  await signupFreshUser(page, 'rx3');
  const visitId = await createReadyTextVisit(page);

  expect(rxWarningSeverities(visitId).filter((s) => s === 'critical')).toHaveLength(1);
  expect(countCriticalOverrides(visitId)).toBe(0);

  // ⚠️ THIS ASSERTION IS THE INVERSE OF THE ONE IT REPLACES, WHICH READ
  // `expect(res.status()).toBe(422)`. That is the point and it is not an
  // oversight: ruling #109 removed the refusal along with the only surface a
  // doctor could have cleared it from. Leaving the refusal would have made
  // every visit carrying a critical warning permanently unsignable.
  const res = await signViaApi(page, visitId, { destinations: ['pdf'] });
  expect(
    res.status(),
    'POST /sign refused a visit with an un-overridden critical warning — the ' +
      'server gate came back, and there is no surface to clear it from',
  ).toBe(200);

  expect(getVisitStatus(visitId)).toBe('SIGNED');
  // And it signed WITHOUT anything fabricating an override to get there.
  expect(
    countCriticalOverrides(visitId),
    'an override row appeared with no surface to create it',
  ).toBe(0);
});
