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
import { expectAtHome, HOME_URL_RE } from '../helpers/home';
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

  // ── RE-POINT ─────────────────────────────────────────────────────────────
  // The recovery CTA actually navigates (graceful, not a dead end).
  //
  // WAS: getByRole('link', { name: /go to dashboard/i }) → toHaveURL(/\/dashboard$/).
  // WHY THAT BROKE: the root 404 FORKED for Rounds and returns EARLY at
  //   src/app/not-found.tsx:31, so the shipped (flag-ON) build never reaches
  //   the legacy branch at not-found.tsx:197-199 that carried the
  //   "Go to dashboard" label. The live CTA is the testid'd link at
  //   not-found.tsx:95-101 — label recoveryLabel() = 'Back to the board'
  //   (src/lib/recovery-href.ts:37-39), href recoveryHref() = '/board'
  //   (recovery-href.ts:30-32).
  // WHERE IT IS NOW: [data-testid="notfound-recover"] (not-found.tsx:98).
  //   The legacy branch is still what a flag-OFF rollback image renders, and
  //   it draws a <SpecularButton>, which does NOT forward a testid
  //   (src/components/specular-button.tsx:79-85) — so this locator also
  //   accepts that branch's label, matched EXACTLY, never as a substring.
  //   The destination is asserted with HOME_URL_RE (helpers/home.ts:30), which
  //   accepts either skin's home, so a rollback image is not a false red.
  //
  // WHAT WOULD MAKE THIS FAIL: the CTA losing its testid or its exact label;
  //   its href drifting off the app's own computed home — a hand-written
  //   '/board' with the flag off is a 404 → 404 loop, which is the precise
  //   failure recovery-href.ts:9-15 exists to prevent; a second recovery CTA
  //   appearing (toHaveCount(1)); or the click landing on another 404 rather
  //   than the home surface (the two negative assertions after the click —
  //   without them, a 404→404 loop still satisfies HOME_URL_RE).
  const recover = page
    .getByTestId('notfound-recover')
    .or(page.getByRole('link', { name: 'Go to dashboard', exact: true }));
  await expect(recover, 'exactly one recovery CTA on the 404').toHaveCount(1);
  await expect(recover).toBeVisible();
  // The href is the app's OWN computed home, not a hardcoded one.
  await expect(recover).toHaveAttribute('href', HOME_URL_RE);
  // ⚠️ AND THE LABEL, which the testid-only re-point had stopped asserting on
  // the shipped path. `recoveryLabel()` (`lib/recovery-href.ts`) is deliberately
  // kept beside `recoveryHref()` so the two cannot drift — "Back to dashboard"
  // pointing at /board is exactly the small lie that survives review because
  // each half looks right alone. A testid check cannot see that drift; this can.
  // Anchored alternation over BOTH skins' output, so a flag-OFF rollback image
  // is not a false red.
  await expect(recover).toHaveAccessibleName(/^(back to the board|go to dashboard)$/i);

  await recover.click();
  await expectAtHome(page);
  // …and it is a real landing, not a 404 loop.
  await expect(
    page.getByText('404', { exact: true }),
    'recovery landed on another 404 — the CTA points somewhere that does not exist for this build',
  ).toHaveCount(0);
  await expect(page.getByTestId('notfound-recover')).toHaveCount(0);
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
  // ── RE-POINT ─────────────────────────────────────────────────────────────
  // The recovery link is present, and it is a graceful EXIT — not just a
  // graceful-looking link.
  //
  // WAS: getByRole('link', { name: /dashboard/i }) — a BARE SUBSTRING over the
  //   accessible name, and the one that stopped meaning anything.
  // WHY THAT BROKE: the label is now recoveryLabel() — 'Back to the board'
  //   under Rounds (src/app/visits/[id]/not-found.tsx:61-64,
  //   src/lib/recovery-href.ts:37-39) — which /dashboard/i does not match at
  //   all.
  // WHERE IT IS NOW: the same single <Link> at
  //   src/app/visits/[id]/not-found.tsx:61-64. It carries no testid (this file
  //   is one of the two not-found pages that outlive the skin, and no app
  //   source may be touched for this row), so the name is matched ANCHORED and
  //   whole over BOTH labels, and the href — the load-bearing half — is
  //   asserted against HOME_URL_RE (helpers/home.ts:30) so a flag-OFF rollback
  //   image is not a false red.
  //
  // WHAT WOULD MAKE THIS FAIL: the label drifting from recoveryLabel(); the
  //   href being hardcoded instead of recoveryHref() — a literal '/board' on a
  //   flag-OFF build is a 404 → 404 loop (recovery-href.ts:9-15); a second link
  //   appearing so the exit is ambiguous (toHaveCount(1)); or the click not
  //   actually reaching the home surface / landing on another 404.
  const recover = page.getByRole('link', {
    name: /^back to (the board|dashboard)$/i,
  });
  await expect(
    recover,
    'exactly one recovery link on the visit-404',
  ).toHaveCount(1);
  await expect(recover).toBeVisible();
  await expect(recover).toHaveAttribute('href', HOME_URL_RE);

  await recover.click();
  await expectAtHome(page);
  await expect(
    page.getByText('404', { exact: true }),
    'the visit-404 recovery link walked to another 404',
  ).toHaveCount(0);
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
