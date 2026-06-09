// ============================================================================
// Scenario 12 — Login failure path + the logged-out auth boundary.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Login SUCCESS is already exercised (signup auto-login +
// re-login helpers). Here we cover the failure path (wrong password → error,
// no session) and that protected routes bounce a logged-out visitor to /login.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { logoutViaMenu } from '../helpers/auth';

test.afterEach(() => {
  cleanupTestUsers();
});

test('login failure: wrong password shows an error + grants no session', async ({
  page,
}) => {
  const { email } = await signupFreshUser(page, 'login-fail');
  await logoutViaMenu(page);

  await page.goto('/login');
  // Wait for the form to be interactive (the suite's first test bears the app's
  // cold-start) before filling.
  await expect(page.getByRole('button', { name: /^sign in$/i })).toBeVisible();
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill('WrongPassword123');
  await page.getByRole('button', { name: /^sign in$/i }).click();

  // Generic invalid-credentials error + still on /login (no dashboard redirect).
  await expect(
    page.getByText(/invalid email or password/i).first(),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/login/);

  // And no session leaked through — a protected route still bounces to /login.
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);
});

test('auth boundary: logged-out protected routes redirect to /login', async ({
  page,
}) => {
  for (const path of ['/dashboard', '/visits', '/patients', '/settings']) {
    await page.goto(path);
    await expect(page, `${path} should redirect when logged out`).toHaveURL(
      /\/login/,
    );
  }
});
