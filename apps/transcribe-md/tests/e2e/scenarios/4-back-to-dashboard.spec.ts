// ============================================================================
// Scenario 4 — Back-to-dashboard navigation works from a visit page
// ----------------------------------------------------------------------------
// Regression for T-M8 Bug 4 (9e423df). The "Back to dashboard" link
// used to be a raw <Link> inside the server component; a stacking-
// context overlay or a subtle hydration glitch could eat the click.
// The fix extracted it into a client-component <a> with both href
// and an explicit router.push onClick, plus relative z-10 to ride
// above any overlay. This test clicks it and asserts navigation +
// that the dashboard correctly lists the visit we just created.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 4: back-to-dashboard navigates from a visit page', async ({
  page,
}) => {
  await signupFreshUser(page, 's4');

  // Create the cheapest visit we can — text mode, skip submission
  // and go straight to clicking Back. Layer 0 (/visits/new) sets a
  // default specialty from SPECIALTIES[0], so a mode-tile click is
  // valid even without opening the dropdown (T-M8 Bug 1 fix).
  await page.goto('/visits/new');
  // Step 1 (two-step flow): pick a patient so the capture-mode tiles render.
  await createPatientAndContinue(page);
  await page.getByRole('button', { name: /text to soap/i }).click();

  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });

  // In-content back-nav is now a breadcrumb (Dashboard › Patient › Visit) — the
  // Linear V1 redesign replaced the old inline "Back to dashboard" link. T-M8
  // Bug 4 regression still holds: this breadcrumb link must navigate, not be
  // eaten by an overlay. Scope to #main so we hit the breadcrumb's "Dashboard",
  // not the sidebar's identically-named nav link.
  await page
    .locator('#main')
    .getByRole('link', { name: 'Dashboard', exact: true })
    .click();

  await expect(page).toHaveURL(/\/dashboard$/);

  // The redesigned dashboard groups visits BY PATIENT (no per-visit anchors on
  // the overview) — confirm the just-created visit surfaces via its patient
  // card. Match the patient *href* (not just the name) so this can't collide
  // with a READY-only "drafts ready to sign" row that also carries the patient
  // name — scenario 4's draft never reaches READY, but scoping by href keeps
  // the assertion unambiguous regardless.
  await expect(
    page.locator('#main').locator('a[href^="/patients/"]', { hasText: 'QA Patient' }),
  ).toBeVisible({ timeout: 10_000 });
});
