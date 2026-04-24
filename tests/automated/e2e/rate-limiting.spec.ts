import { test, expect } from '@playwright/test';

// Credentials login bucket: 5 attempts / 15 min / IP. Sixth attempt
// should surface a rate-limit message. We use a clearly-nonexistent
// email so no real account gets locked out in the process — lockout
// fires off failed-credential count, not this rate-limit bucket, and
// the account is fake so the lockout path is a no-op.
//
// Skipped when E2E_READ_ONLY=false isn't explicitly enabled, because
// the rate limiter keeps the test IP blocked for 15 min after the
// run and that affects other tests sharing the same source IP.

import { E2E_READ_ONLY } from './helpers/env';

test.skip(E2E_READ_ONLY, 'rate-limit spec leaves the IP blocked for 15 min; set E2E_READ_ONLY=false to opt in');

test('6th failed login is rate-limited', async ({ page }) => {
  const email = `rate-limit-probe-${Date.now()}@example.test`;

  for (let i = 1; i <= 5; i++) {
    await page.goto('/login');
    await page.getByLabel(/email/i).fill(email);
    await page.getByLabel(/password/i).fill('wrong-password');
    await page.getByRole('button', { name: /sign in/i }).click();
    // Wait for the form to settle — either an inline error or a redirect.
    await page.waitForTimeout(500);
  }

  // Attempt #6
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill('wrong-password');
  await page.getByRole('button', { name: /sign in/i }).click();

  // The loginAction surfaces a 429-style message through its
  // error state. Text used by actions/auth.ts today is "too many" /
  // "rate limited" / "try again later" — match loosely so copy
  // changes don't break the test.
  const rateLimited = await page
    .getByText(/too many|rate.?limit|try again later|blocked/i)
    .isVisible({ timeout: 5_000 })
    .catch(() => false);

  expect(rateLimited, 'Expected a rate-limit message after 5 failures').toBe(true);
});
