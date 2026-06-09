// ============================================================================
// Scenario 15 — MFA (TOTP) enrollment + login enforcement.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Enroll → verify with a real TOTP (generated in-test from the
// enrollment secret) → recovery codes shown. Then prove MFA is ENFORCED: a
// password-only login no longer reaches the dashboard — it demands the second
// factor. (If a password-only login DID reach the dashboard, that would be a
// high-severity auth bug — this spec is the regression guard for it.)
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { TEST_PASSWORD } from '../helpers/test-utils';
import { generateTotp, logoutViaMenu, totpSecretFromUri } from '../helpers/auth';

test.afterEach(() => {
  cleanupTestUsers();
});

test('MFA: enroll TOTP → verify → recovery codes, then enforced at login', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'mfa');

  await page.goto('/settings/security/mfa');
  await page.getByRole('button', { name: /generate qr code/i }).click();

  // The verify step renders the otpauth:// URI (with the base32 secret) for
  // manual entry — read the secret straight out of it.
  const uriCode = page.locator('code').filter({ hasText: 'otpauth://' }).first();
  await expect(uriCode).toBeVisible({ timeout: 10_000 });
  const secret = totpSecretFromUri((await uriCode.textContent()) ?? '');

  await page.locator('#mfa-token').fill(generateTotp(secret));
  await page.getByRole('button', { name: /verify \+ enable/i }).click();

  // Step 3 — exactly 10 single-use recovery codes, shown once.
  await expect(
    page.getByRole('heading', { name: /save your recovery codes/i }),
  ).toBeVisible({ timeout: 10_000 });
  const recoveryBlock = page.locator('pre');
  await expect(recoveryBlock).toBeVisible();
  const codes = ((await recoveryBlock.textContent()) ?? '')
    .trim()
    .split('\n')
    .filter(Boolean);
  expect(codes.length).toBe(10);

  // Finish enrollment → back to /settings, then log out.
  await page.getByRole('button', { name: /saved them/i }).click();
  await logoutViaMenu(page);

  // ENFORCEMENT: email + password alone must NOT log in — the 2nd factor field
  // appears instead of a dashboard redirect.
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(page.locator('#totpToken')).toBeVisible({ timeout: 10_000 });
  await expect(page).not.toHaveURL(/\/dashboard/);

  // Completing the second factor logs in.
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.locator('#totpToken').fill(generateTotp(secret));
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
});
