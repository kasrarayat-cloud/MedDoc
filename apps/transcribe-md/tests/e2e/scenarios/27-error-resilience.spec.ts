// ============================================================================
// Scenario 27 — error / resilience: graceful degradation, not crashes
// ----------------------------------------------------------------------------
// The app should fail SOFT: a bad URL renders a styled 404 (not a white screen
// / stack trace), a missing visit renders a disclosure-minimising visit-404,
// and invalid input surfaces a FRIENDLY message rather than a raw Zod dump.
//
// Coverage notes (what's drivable here vs unit-covered):
//   - 404 routes + visit-404: driven directly (deterministic).
//   - friendly validation: driven through the note-format review editor — an
//     invalid template surfaces a human message, not a Zod dump, and the
//     editor stays put (input preserved, no error-boundary white screen). The
//     server-side friendlyValidationError variants (too_big / too_small /
//     unrecognized_keys) + clampDraftToLimits are unit-covered
//     (note-template-persist + note-template-parse __tests__).
//   - deployment-skew reload fallback (isStaleDeploymentError → "QuillMD was
//     just updated", input preserved) + the generic error boundary: the
//     detection logic is unit-covered (lib/__tests__/stale-deployment.test.ts)
//     and the manager surfaces it as a toast, but a real stale-action-hash
//     throw can't be deterministically forced from a test without a dedicated
//     throw route — covered at the unit layer, noted here.
//
// Runs in the default chromium project. The friendly-validation test needs the
// MOCK note-format parse fixture (NOTE_FORMAT_E2E=1, as CI sets for chromium).
// MOCK_AI_CALLS=true.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { gotoNoteFormat, parseToReview } from '../helpers/noteFormat';

const NOTE_FORMAT_GATE = process.env.NOTE_FORMAT_E2E !== '1';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 27: a nonexistent route renders the styled 404 page (not a crash) + the recovery CTA works', async ({
  page,
}) => {
  await signupFreshUser(page, 'res-404');

  const resp = await page.goto('/this-route-truly-does-not-exist-xyz');
  expect(resp?.status(), 'unknown route must 404').toBe(404);

  // The styled 404 renders — not a white screen / raw stack trace.
  await expect(page.getByText('404', { exact: true }).first()).toBeVisible();

  // The recovery CTA actually navigates (graceful, not a dead end).
  const dash = page.getByRole('link', { name: /go to dashboard/i });
  await expect(dash).toBeVisible();
  await dash.click();
  await expect(page).toHaveURL(/\/dashboard$/);
});

test('scenario 27: a nonexistent visit renders the visit-404 (not a crash, no ID enumeration leak)', async ({
  page,
}) => {
  await signupFreshUser(page, 'res-visit404');

  // visits/[id]/page.tsx → notFound() when the visit is missing OR not owned
  // (both → the SAME not-found, to prevent ID enumeration) → visits/[id]/
  // not-found.tsx. NB: a programmatic notFound() in a NESTED segment streams a
  // 200 shell (the layout already committed) rather than a top-level route-miss
  // 404 — so we assert graceful degradation (no 5xx crash) + the rendered
  // not-found content, which is the real resilience + anti-enumeration signal.
  const resp = await page.goto('/visits/this-visit-does-not-exist');
  expect([200, 404], 'never a 5xx crash').toContain(resp?.status());

  await expect(page.getByText('Visit not found')).toBeVisible();
  await expect(
    page.getByText(/doesn.t exist or you don.t have access/i),
  ).toBeVisible();
  // The recovery link is present (graceful exit).
  await expect(page.getByRole('link', { name: /dashboard/i })).toBeVisible();
});

test('scenario 27: invalid note-format input surfaces a FRIENDLY message, not a raw Zod dump (MOCK)', async ({
  page,
}) => {
  test.skip(
    NOTE_FORMAT_GATE,
    'Needs the MOCK note-format parse fixture — run with NOTE_FORMAT_E2E=1 (CI sets it for chromium).',
  );

  await signupFreshUser(page, 'res-friendly');
  await gotoNoteFormat(page);
  await parseToReview(page); // review editor, #nf-name prefilled by the mock fixture

  // Make the reviewed template invalid: clear the required name.
  await page.locator('#nf-name').fill('');
  await page.getByRole('button', { name: /save & activate/i }).click();

  // A friendly, human message — NOT a raw Zod dump, NOT a crash.
  await expect(page.getByText(/give your format a name/i)).toBeVisible({
    timeout: 10_000,
  });
  // The editor is still here — input preserved, no error-boundary white screen.
  await expect(
    page.getByRole('button', { name: /save & activate/i }),
  ).toBeVisible();
  // Negative: no raw Zod / validation-internal leakage rendered to the doctor.
  await expect(
    page.getByText(/zoderror|invalid_type|too_big|"code":|unrecognized_keys/i),
  ).toHaveCount(0);
});
