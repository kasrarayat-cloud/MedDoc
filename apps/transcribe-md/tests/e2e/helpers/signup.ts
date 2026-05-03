// ============================================================================
// Signup helper — drives the UI happy path through the signup form
// ============================================================================

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

import { TEST_PASSWORD, uniqueTestEmail } from './test-utils';

export interface SignupResult {
  email: string;
  password: string;
  /** The cookie-backed session is live after this helper returns, so
   *  subsequent navigations to authed pages work without re-login. */
}

/** Fills the signup form and asserts the caller lands on /dashboard.
 *  The T-M9 fix (585fad4) routes auto-login failures to /login with a
 *  `warning` marker; this helper fails loudly if that path triggers so
 *  flakiness shows up as a real assertion, not a silent half-signup. */
export async function signupFreshUser(
  page: Page,
  tag: string,
  name = 'QA Test Doctor'
): Promise<SignupResult> {
  const email = uniqueTestEmail(tag);

  await page.goto('/signup');
  await page.getByLabel('Full name').fill(name);
  await page.getByLabel('Email').fill(email);
  // exact:true disambiguates "Password" from "Confirm password" — the
  // signup form has both, and the unqualified label match resolves to
  // two elements and throws under Playwright strict mode.
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('Confirm password').fill(TEST_PASSWORD);
  await page.getByRole('checkbox').check(); // accept terms
  await page.getByRole('button', { name: /create account/i }).click();

  // Auto-login should land us on /dashboard within the default
  // navigation timeout. If it lands on /login instead (auto-login
  // bombed), fail here with a clear error — the tests don't try to
  // recover because that would mask a real regression of T-M9's fix.
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });

  return { email, password: TEST_PASSWORD };
}
