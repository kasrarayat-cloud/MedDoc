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
  await loginUser(page, email, newPassword);
  await expect(page).toHaveURL(/\/dashboard$/);
});
