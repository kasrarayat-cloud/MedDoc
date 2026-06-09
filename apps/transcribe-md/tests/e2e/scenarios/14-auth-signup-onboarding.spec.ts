// ============================================================================
// Scenario 14 — Signup → first authenticated screen.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. The full new-account path through the signup form to the
// first-run dashboard — asserting the onboarding/landing state, not just that
// signup returned.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { TEST_PASSWORD, uniqueTestEmail } from '../helpers/test-utils';

test.afterEach(() => {
  cleanupTestUsers();
});

test('signup: a brand-new account lands on the first-run dashboard', async ({
  page,
}) => {
  const email = uniqueTestEmail('signup');

  await page.goto('/signup');
  await page.getByLabel('Full name').fill('New Doctor');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('Confirm password').fill(TEST_PASSWORD);
  await page.getByRole('checkbox').check(); // accept terms
  await page.getByRole('button', { name: /create account/i }).click();

  // First authenticated screen = the dashboard in its empty first-run state.
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 15_000 });
  await expect(
    page.getByText(/start your first visit/i).first(),
  ).toBeVisible();
  // Account-specific: the authenticated TopNav renders THIS user's name, so the
  // assertion can't pass for just any empty dashboard.
  await expect(
    page.getByRole('button', { name: /account menu for new doctor/i }),
  ).toBeVisible();
});
