// ============================================================================
// Scenario 13 — Logout clears the session.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. Sign out via the user menu → land on /login → the session
// is gone (a protected route bounces back to /login).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { logoutViaMenu } from '../helpers/auth';

test.afterEach(() => {
  cleanupTestUsers();
});

test('logout: signing out clears the session + protected routes bounce', async ({
  page,
}) => {
  // signupFreshUser already asserts we land authenticated on /dashboard.
  await signupFreshUser(page, 'logout');

  await logoutViaMenu(page); // asserts redirect to /login

  // Session cleared — the protected route now redirects back to /login.
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login/);
});
