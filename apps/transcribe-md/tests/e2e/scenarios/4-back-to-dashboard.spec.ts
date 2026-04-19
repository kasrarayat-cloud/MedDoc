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
  await page.getByRole('button', { name: /text to soap/i }).click();

  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitUrl = page.url();

  // The back link is an <a href="/dashboard"> rendered by
  // BackToDashboardLink (client component). role=link matches.
  await page.getByRole('link', { name: /back to dashboard/i }).click();

  await expect(page).toHaveURL(/\/dashboard$/);

  // Dashboard renders visit cards. A fresh user has exactly one,
  // and it was the one we just created. Its href points back to
  // the visit we came from.
  const visitId = new URL(visitUrl).pathname.split('/').pop()!;
  await expect(
    page.locator(`a[href="/visits/${visitId}"]`).first()
  ).toBeVisible({ timeout: 10_000 });
});
