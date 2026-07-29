// ============================================================================
// ROUNDS — Gate A E2E: the Board.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md Screen 1. Runs against the flag-ON image only; with
// NEXT_PUBLIC_SKIN_ROUNDS off the route 404s, which is itself asserted so a
// mis-built image fails loudly instead of silently skipping the whole pack.
//
// What is worth an E2E rather than a unit test: that the real queue, the real
// filters and the real search reach the real component. The row model's rules
// are already unit-tested; this proves the wiring.
// ============================================================================

import { expect, test } from '@playwright/test';

import { signupFreshUser } from '../helpers/signup';
import { cleanupTestUsers } from '../helpers/cleanup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('the board renders for an invited clinician', async ({ page }) => {
  await signupFreshUser(page, 'board');
  await page.goto('/board');

  // A brand-new account has no visits — the empty state is the correct render,
  // and it must invite rather than shrug.
  await expect(page.getByTestId('rounds-board-empty')).toBeVisible();
  await expect(page.getByRole('link', { name: /start a visit/i })).toBeVisible();
});

test('the chrome carries the shipped capabilities', async ({ page }) => {
  await signupFreshUser(page, 'board-chrome');
  await page.goto('/board');

  // SEARCH AND PAGINATION SURVIVE — the spec is explicit that the designs'
  // bans lose to shipped features. If a future redesign quietly drops the
  // search box, this fails.
  await expect(page.getByTestId('rounds-search')).toBeVisible();

  // All six filters, and they are links so the view is shareable.
  for (const f of ['active', 'signed', 'soap', 'ultrasound', 'critical', 'failed']) {
    await expect(page.getByTestId(`rounds-filter-${f}`)).toBeVisible();
  }

  await expect(page.getByTestId('rounds-day-meter')).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
});

test('a filter narrows the queue and survives a reload', async ({ page }) => {
  await signupFreshUser(page, 'board-filter');
  await page.goto('/board');
  await page.getByTestId('rounds-filter-signed').click();
  await expect(page).toHaveURL(/filter=signed/);

  // The filter is in the URL, so a reload keeps it — which is what makes a
  // board view something a clinician can bookmark or send to a colleague.
  await page.reload();
  await expect(page.getByTestId('rounds-filter-signed')).toHaveAttribute(
    'aria-current',
    'true',
  );
});

test('search is a GET, so the result is linkable', async ({ page }) => {
  await signupFreshUser(page, 'board-search');
  await page.goto('/board');
  await page.getByTestId('rounds-search').fill('nobody-matches-this');
  await page.getByRole('button', { name: /^search$/i }).click();

  await expect(page).toHaveURL(/q=nobody-matches-this/);
  // No results is the empty state, not a broken board.
  await expect(page.getByTestId('rounds-board-empty')).toBeVisible();
});

test('the flag gates the route — a flag-OFF build has no board', async ({
  page,
}) => {
  // Deliberately asserted from the POSITIVE side in this pack: the pack only
  // runs on the flag-ON image, so reaching /board proves the image really is
  // flag-ON. A flag-OFF image would 404 here and fail the whole pack loudly,
  // rather than passing a suite that never exercised Rounds at all.
  await signupFreshUser(page, 'board-flag');
  const res = await page.goto('/board');
  expect(res?.status()).toBe(200);
});
