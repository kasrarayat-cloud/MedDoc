// ============================================================================
// Scenario 8 — Open an EXISTING visit + the detail tabs.
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. Navigates to a READY visit from the list (not the create
// flow), asserts the SOAP note renders, and that the SOAP/Codes/Extras tabs
// switch (aria-selected).
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('visit detail: open an existing visit → SOAP note renders + tabs switch', async ({
  page,
}) => {
  await signupFreshUser(page, 'v-detail');
  const visitId = await createReadyTextVisit(page, { patientName: 'Detail Patient' });

  // Open the EXISTING visit via the list link.
  await page.goto('/visits');
  await page.locator(`a[href="/visits/${visitId}"]`).click();
  await expect(page).toHaveURL(new RegExp(`/visits/${visitId}$`));

  // SOAP tab is the default + shows the MOCK-generated note body.
  await expect(
    page.getByRole('tab', { name: 'SOAP Note' }),
  ).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText(/tension headache/i)).toBeVisible();

  // The Codes tab switches — aria-selected flips AND the panel content actually
  // changes (the SOAP body is no longer rendered, so this isn't an aria-only
  // pass that a panel-render regression could slip through).
  await page.getByRole('tab', { name: 'Codes' }).click();
  await expect(
    page.getByRole('tab', { name: 'Codes' }),
  ).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText(/tension headache/i)).toBeHidden();

  // Extras tab switches too.
  await page.getByRole('tab', { name: 'Extras' }).click();
  await expect(
    page.getByRole('tab', { name: 'Extras' }),
  ).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText(/tension headache/i)).toBeHidden();
});
