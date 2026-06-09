// ============================================================================
// Scenario 7 — Visit list (/visits) + status filtering.
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. A READY visit shows in the all-visits list and the
// URL-driven status filter chips (?filter=signed|ready|…) narrow it correctly.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('visit list: READY visit lists + Signed/All filters narrow correctly', async ({
  page,
}) => {
  await signupFreshUser(page, 'v-list');
  const visitId = await createReadyTextVisit(page, { patientName: 'List Patient' });

  await page.goto('/visits');
  // The READY visit is in the (default = All) list, by patient + row link.
  const row = page.locator(`a[href="/visits/${visitId}"]`);
  await expect(row).toBeVisible();
  await expect(page.getByText('List Patient').first()).toBeVisible();

  // Filter → Signed: an unsigned visit drops out + the empty-filter copy shows.
  await page.getByRole('link', { name: 'Signed', exact: true }).click();
  await expect(page).toHaveURL(/filter=signed/);
  await expect(row).toHaveCount(0);
  await expect(page.getByText(/No visits match/i)).toBeVisible();

  // Filter → All: it comes back.
  await page.getByRole('link', { name: 'All', exact: true }).click();
  await expect(page).toHaveURL(/\/visits$/);
  await expect(row).toBeVisible();
});
