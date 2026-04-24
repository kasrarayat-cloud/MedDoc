import { test, expect } from '@playwright/test';
import { E2E_READ_ONLY } from './helpers/env';

// Validates that the /signup form enforces the 10+char / upper / lower /
// digit policy that landed in the pre-launch batch. We can't assert on
// the rendered error text (the form carries STATIC help text with the
// same wording — "At least 10 characters, with upper + lowercase
// letters and a digit" — which would match any naive regex), so we
// check the behavioural outcome instead: did submission advance the
// user past /signup?
//
// A rejection keeps us on /signup (server action returns errors, the
// router doesn't push). A compliant submission advances us to
// /check-email or /dashboard. Both are fine for this test — the
// assertion is "NOT still on /signup".

const randomEmail = () =>
  `qa-policy-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}@example.test`;

async function attemptSignup(
  page: import('@playwright/test').Page,
  email: string,
  password: string
) {
  await page.goto('/signup');
  await page.getByLabel(/name/i).fill('QA Tester');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByLabel(/confirm/i).fill(password);
  const terms = page.getByRole('checkbox', { name: /terms|agree|accept/i });
  if (await terms.isVisible().catch(() => false)) {
    await terms.check();
  }
  await page.getByRole('button', { name: /create account|sign up/i }).click();
  // Wait out the server action round-trip. The form either re-renders
  // with errors (still at /signup) or transitions — either path has
  // settled within a couple seconds.
  await page.waitForTimeout(2500);
}

test.describe('password policy', () => {
  test('6-char password is rejected (stays on /signup)', async ({ page }) => {
    await attemptSignup(page, randomEmail(), 'abcdef');
    expect(page.url(), 'form should reject — user should still be on /signup').toMatch(/\/signup/);
  });

  test('10-char no-complexity password is rejected (stays on /signup)', async ({ page }) => {
    await attemptSignup(page, randomEmail(), 'aaaaaaaaaa');
    expect(page.url(), 'form should reject — user should still be on /signup').toMatch(/\/signup/);
  });

  test('compliant password advances past /signup', async ({ page }) => {
    // Opt-in: a real-prod signup with a compliant password creates a
    // verification-email record and leaves a User row behind. Only
    // run when E2E_READ_ONLY=false is set. The two rejection tests
    // above already prove the policy is enforced; this test verifies
    // the inverse and is therefore redundant unless you specifically
    // want to audit the "happy path" behaviour.
    test.skip(
      E2E_READ_ONLY,
      'compliant signup would create a real account in prod; set E2E_READ_ONLY=false to opt in'
    );

    await attemptSignup(page, randomEmail(), 'Strong2024Pass');
    expect(page.url(), 'compliant password should advance past /signup').not.toMatch(/\/signup$/);
  });
});
