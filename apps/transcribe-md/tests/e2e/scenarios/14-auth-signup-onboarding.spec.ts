// ============================================================================
// Scenario 14 — Signup → first authenticated screen.
// ----------------------------------------------------------------------------
// Phase 2 Batch 2. The full new-account path through the signup form to the
// first-run dashboard — asserting the onboarding/landing state, not just that
// signup returned.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { E2E_INVITE_CODE } from '../helpers/signup';
import { TEST_PASSWORD, uniqueTestEmail } from '../helpers/test-utils';

test.afterEach(() => {
  cleanupTestUsers();
});

test('signup: a brand-new account lands on the first-run dashboard', async ({
  page,
}) => {
  const email = uniqueTestEmail('signup');

  await page.goto('/signup');
  // Invite-only pilot (2026-07-28). This spec fills the form inline rather than
  // through signupFreshUser, so it needs the code explicitly.
  await page.getByLabel('Invite code').fill(E2E_INVITE_CODE);
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

// ============================================================================
// THE GATE ITSELF — invite-only pilot (2026-07-28).
// ----------------------------------------------------------------------------
// Every other spec in the suite proves an INVITED signup works. This one proves
// the other half: without a code, no account comes into existence. Registration
// used to be open, rate-limited at 5/hour/IP and nothing else, and production
// accumulated 195 accounts of which 172 never logged in.
// ============================================================================

test('signup: WITHOUT an invite code, no account is created', async ({ page }) => {
  const email = uniqueTestEmail('uninvited');

  await page.goto('/signup');
  await page.getByLabel('Invite code').fill('DEFINITELY-NOT-A-REAL-CODE');
  await page.getByLabel('Full name').fill('Uninvited Doctor');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel('Confirm password').fill(TEST_PASSWORD);
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: /create account/i }).click();

  // Refused, and still on the form — not bounced to a dashboard.
  //
  // ⚠️ SCOPED TO THE ALERT, and the unscoped version asserted nothing.
  // `getByText(/invite-only during the pilot/i).first()` DOM-order-resolves to
  // the STATIC helper paragraph at `signup-form.tsx:113`, which is on the page
  // before the form is ever submitted. It was visible at t=0, so the assertion
  // passed whether or not the gate fired — and the `toHaveURL(/\/signup$/)`
  // below inherited that, because it ran before the server action had returned
  // and the page was trivially still on /signup.
  //
  // `AuthFieldError` (auth-shell.tsx) is the only `role="alert"` reachable on
  // /signup — verified against every globally-mounted component, including the
  // toaster, which carries no role at all. On this path `actions/auth.ts` sets
  // exactly one field error, so precisely one alert is in the DOM. Waiting on
  // it is waiting on the server's refusal.
  await expect(
    page.getByRole('alert').filter({ hasText: /invite/i }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(/\/signup$/);

  // AND THE ACCOUNT MUST NOT EXIST. A gate that shows an error while still
  // writing the row is the failure this whole change exists to prevent — so the
  // proof is that logging in with those credentials cannot work.
  //
  // ⚠️ THE NEGATED URL ASSERTION BELOW CANNOT FAIL ON ITS OWN, so it is no
  // longer asked to. `expect(page).not.toHaveURL(...)` compiles to
  // `waitForURL(url => !isNot === matches)`, and `waitForURL` tests the CURRENT
  // url first and returns immediately when the predicate holds. The click does
  // not await navigation, so at the first poll the page is still /login and the
  // assertion resolves green — before a leaked account's redirect to /dashboard
  // could possibly have landed. It passes on a broken gate.
  // The cure is a POSITIVE wait on the refusal that must happen first; only
  // then does the URL check have anything to say.
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: true }).fill(TEST_PASSWORD);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await expect(
    page.getByRole('alert'),
    'no sign-in refusal appeared — the credentials may have been accepted',
  ).toBeVisible({ timeout: 10_000 });
  await expect(page).not.toHaveURL(/\/dashboard$/);
});

test('the waitlist is reachable and creates no session', async ({ page }) => {
  await page.goto('/waitlist');
  await expect(page.getByRole('button', { name: /join the waitlist/i })).toBeVisible();
  // A prospect is not a user: nothing here grants access.
  await page.goto('/dashboard');
  await expect(page).not.toHaveURL(/\/dashboard$/, { timeout: 8_000 });
});
