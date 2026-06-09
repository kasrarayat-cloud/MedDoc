// ============================================================================
// Scenario 16 — Account/profile settings: view + edit, and password change.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Profile edit persists across reload; the logged-in password
// change actually takes effect (new password logs in afterwards).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { TEST_PASSWORD } from '../helpers/test-utils';
import { loginUser, logoutViaMenu } from '../helpers/auth';

test.afterEach(() => {
  cleanupTestUsers();
});

test('account: profile edit persists across reload', async ({ page }) => {
  await signupFreshUser(page, 'profile');

  await page.goto('/settings');
  await page.locator('#profile-name').fill('Dr. Renamed');
  // Confirm the new value is in the DOM before submitting, so the server action
  // can't capture a stale FormData value under load.
  await expect(page.locator('#profile-name')).toHaveValue('Dr. Renamed');
  await page.getByRole('button', { name: /save profile/i }).click();
  await expect(page.getByText('Saved')).toBeVisible({ timeout: 10_000 });

  // Server-rendered defaultName → survives a reload. Retry the reload+read to
  // absorb any read-after-write/revalidation lag under suite load.
  await expect(async () => {
    await page.reload();
    await expect(page.locator('#profile-name')).toHaveValue('Dr. Renamed', {
      timeout: 5_000,
    });
  }).toPass({ timeout: 20_000 });
});

test('account: logged-in password change takes effect at next login', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'pwchange');
  const newPassword = 'QaE2eNewPass9';

  await page.goto('/settings');
  await page.locator('#currentPassword').fill(TEST_PASSWORD);
  await page.locator('#newPassword').fill(newPassword);
  await page.locator('#confirmPassword').fill(newPassword);
  await page.getByRole('button', { name: /update password/i }).click();
  await expect(
    page.getByText(/password updated/i).first(),
  ).toBeVisible({ timeout: 10_000 });

  // The change is real — the new password logs in on a fresh session.
  await logoutViaMenu(page);
  await loginUser(page, email, newPassword);
  await expect(page).toHaveURL(/\/dashboard$/);
});
