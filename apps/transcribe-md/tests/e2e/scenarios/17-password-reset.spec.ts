// ============================================================================
// Scenario 17 — Password reset: request → reset link → new-password login.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. The qa stack leaves RESEND_API_KEY unset, so forgot-password
// logs the reset link to the app container instead of emailing (the route's
// dev-escape-hatch). We capture the token from the logs (it's SHA-256-hashed in
// the DB, so the log is the only plaintext channel), complete the reset, and
// confirm the new password works end-to-end.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { TEST_PASSWORD } from '../helpers/test-utils';
import { loginUser, logoutViaMenu } from '../helpers/auth';
import { captureResetToken } from '../helpers/reset-token';
import { expectAtHome } from '../helpers/home';

test.afterEach(() => {
  cleanupTestUsers();
});

test('password reset: request → reset link → set new password → login', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'reset');
  await logoutViaMenu(page);

  // Request a reset link.
  await page.goto('/forgot-password');
  await page.getByLabel('Email').fill(email);
  await page.getByRole('button', { name: /send reset link/i }).click();
  await expect(
    page.getByText(/we've sent a reset link/i),
  ).toBeVisible({ timeout: 10_000 });

  // Capture the token from the dev-escape-hatch log + complete the reset.
  const token = captureResetToken();
  const newPassword = 'QaE2eResetPass9';
  await page.goto(`/reset-password?token=${token}`);
  await page.locator('#password').fill(newPassword);
  await page.locator('#confirmPassword').fill(newPassword);
  await page.getByRole('button', { name: /set new password/i }).click();
  await expect(
    page.getByText(/password updated/i).first(),
  ).toBeVisible({ timeout: 10_000 });

  // The password actually CHANGED — the old one no longer works…
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(
    page.getByText(/invalid email or password/i).first(),
  ).toBeVisible({ timeout: 10_000 });

  // …and the new one does.
  //
  // WAS: `await expect(page).toHaveURL(/\/dashboard$/)`. That named ONE of the
  // two home surfaces. The app computes its own home with `recoveryHref()`
  // (src/lib/recovery-href.ts:31) — '/board' under Rounds, '/dashboard'
  // otherwise — and it is a build-time fork, so the same spec faces either
  // destination depending on which image the QA stack was recreated onto.
  // Flag-ON it landed on /board and this line failed a login that had worked.
  //
  // NOW: `expectAtHome` (helpers/home.ts:33), which accepts both via the
  // anchored HOME_URL_RE (helpers/home.ts:30) — anchored so 'dashboard'
  // containing 'board' cannot false-match, and so a flag-OFF rollback image
  // does not turn this fix into a false red.
  //
  // KEPT RATHER THAN DELETED, and honestly: `loginUser` already calls
  // `expectAtHome` internally (helpers/auth.ts:38), so given today's helper
  // this line cannot fail on its own — the real proof that the new password
  // works is that `loginUser` RETURNS at all. It stays as a backstop against
  // the helper's assertion being softened later (an opts flag, an early
  // return), which would otherwise leave this test silently proving nothing.
  //
  // WHAT WOULD MAKE IT FAIL: login with `newPassword` not establishing a
  // session (we would sit on /login, or bounce back to it), or the
  // authenticated landing surface moving to a route that is neither /board
  // nor /dashboard without helpers/home.ts being updated.
  await loginUser(page, email, newPassword);
  await expectAtHome(page);
});
