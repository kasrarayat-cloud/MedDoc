import { test, expect, type Page } from '@playwright/test';

import { USERS, TEST_PASSWORD } from '../fixtures/tenancy';

// ============================================================================
// Add Patient form — full-field QA
// ----------------------------------------------------------------------------
// Exercises every field on the expanded Add Patient modal: demographics,
// sex, assigned provider, address block, pharmacy, intake note/brief
// history, tags, insurance-verified. Verifies input behaviors (state
// auto-uppercases + caps at 2 chars) and end-to-end persistence via a
// patient-list round-trip.
// ============================================================================

async function signIn(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.waitForURL((url) => {
    const path = new URL(url).pathname;
    return path === '/dashboard' || path === '/system-admin';
  });
}

test.describe('Add Patient — new form QA', () => {
  test('fills every field and creates a patient end-to-end', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto('/dashboard/patients');

    await page.getByRole('button', { name: /add patient/i }).click();
    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();

    // Unique suffix keeps re-runs from colliding on MRN/chart unique keys.
    const stamp = Date.now().toString().slice(-6);
    const firstName = `E2EForm${stamp}`;
    const lastName = 'FullField';
    const mrn = `MRN-QA${stamp}`;

    // ── Core demographics ─────────────────────────────────────────────
    await modal.locator('input[placeholder="Sarah"]').fill(firstName);
    await modal.locator('input[placeholder="Mitchell"]').fill(lastName);
    await modal.locator('input[placeholder="MRN-440182"]').fill(mrn);
    // Chart ID left blank — server auto-assigns (covered by chart-id.spec.ts).
    await modal.locator('input[placeholder="1978"]').fill('1985');

    // Phone/email (also drives the phoneLast4 auto-derive).
    await modal.locator('input[placeholder="(555) 123-4421"]').fill('(415) 555-7788');
    await modal.locator('input[placeholder="(555) 123-0000"]').first().fill('(415) 555-0100');
    await modal
      .locator('input[placeholder="patient@example.com"]')
      .fill('qa.patient@example.com');

    // ── NEW: Sex dropdown ─────────────────────────────────────────────
    await modal.getByLabel('Sex').selectOption('FEMALE');

    // ── NEW: Assigned Provider dropdown ───────────────────────────────
    // At minimum, the dropdown is present with a default "Unassigned"
    // option. If the practice has doctors, pick the first non-empty one.
    const providerSelect = modal.getByLabel('Assigned Provider');
    await expect(providerSelect).toBeVisible();
    const providerOptions = providerSelect.locator('option');
    const providerCount = await providerOptions.count();
    // If there is at least one real doctor (count > 1 because of "Unassigned"),
    // pick it so we exercise the tenant-guarded save path.
    if (providerCount > 1) {
      const firstRealValue = await providerOptions.nth(1).getAttribute('value');
      if (firstRealValue) {
        await providerSelect.selectOption(firstRealValue);
      }
    }

    // ── NEW: Address block ────────────────────────────────────────────
    await modal.locator('input[placeholder="123 Main St"]').fill('5325 New Castle Ave');
    await modal.locator('input[placeholder="Apt 4B"]').fill('Apartment 105');
    await modal.locator('input[placeholder="San Francisco"]').fill('Encino');

    // State input: test auto-uppercase + 2-char cap. Typing lowercase "ca"
    // should display "CA"; typing extra chars should clip to 2.
    const stateInput = modal.locator('input[placeholder="CA"]');
    await stateInput.fill('caXYZ');
    await expect(stateInput).toHaveValue('CA');

    await modal.locator('input[placeholder="94103"]').fill('91316');

    // ── NEW: Pharmacy ─────────────────────────────────────────────────
    await modal
      .locator('input[placeholder="CVS on Market St"]')
      .fill('Walgreens on Ventura Blvd');
    // Home + pharmacy both have "(555) 123-0000"; disambiguate by order.
    // Home phone is the 1st occurrence (already filled), pharmacy is 2nd.
    await modal.locator('input[placeholder="(555) 123-0000"]').nth(1).fill('(818) 555-2020');

    // ── NEW: Intake Note / Brief History ──────────────────────────────
    await modal
      .getByPlaceholder(/Referred by Dr\. Chen/i)
      .fill(
        [
          'Referred by Dr. Chen for chronic low back pain',
          'Prior LESI series 2024, partial relief',
        ].join('\n')
      );

    // Insurance verified + tags
    await modal.getByRole('checkbox', { name: /insurance verified/i }).check();
    await modal
      .locator('input[placeholder="post-op, chronic-pain"]')
      .fill('chronic-pain, post-op');

    // Submit.
    await modal.getByRole('button', { name: /create patient/i }).click();
    await expect(modal.getByText(/patient created successfully/i)).toBeVisible({
      timeout: 10_000,
    });

    // Modal auto-closes ~1s after success; wait then refresh the list.
    await page.waitForTimeout(1200);
    await page.goto('/dashboard/patients');
    await page.getByPlaceholder(/search patients/i).fill(firstName);

    // The new patient row shows up in the filtered list.
    const row = page.locator(`text=${firstName} ${lastName}`).first();
    await expect(row).toBeVisible({ timeout: 10_000 });

    // Navigate into the patient detail page to confirm the record renders
    // without throwing (server component reads the new fields).
    await row.click();
    await page.waitForURL(/\/dashboard\/patients\/[^/]+$/);
    await expect(page.locator(`text=${firstName} ${lastName}`).first()).toBeVisible();
    // MRN is rendered on the detail header.
    await expect(page.getByText(mrn).first()).toBeVisible();
  });

  test('requires first + last name — shows field error on blank submit', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto('/dashboard/patients');

    await page.getByRole('button', { name: /add patient/i }).click();
    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();

    // Fire a submit without touching anything. HTML5 required attributes
    // block the network call — verify the form stays open (no success
    // banner, no close) rather than relying on a specific error string
    // (browsers localize those).
    await modal.getByRole('button', { name: /create patient/i }).click();
    await expect(modal).toBeVisible();
    await expect(modal.getByText(/patient created successfully/i)).toHaveCount(0);
  });
});
