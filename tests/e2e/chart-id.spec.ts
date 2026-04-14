import { test, expect, type Page } from '@playwright/test';

import { USERS, TEST_PASSWORD } from '../fixtures/tenancy';

// ============================================================================
// Chart ID auto-assignment — UI flow
// ----------------------------------------------------------------------------
// Verifies:
//   1. Opening Add Patient modal prefills the Chart ID placeholder with C-<n>
//   2. Creating a patient with blank Chart ID auto-assigns a C-<n>
//      visible on the patient list
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

test.describe('chart ID auto-assignment', () => {
  test('Add Patient modal shows next C-<n> placeholder and auto-assigns on blank submit', async ({ page }) => {
    await signIn(page, USERS.doctorA.email, TEST_PASSWORD);
    await page.goto('/dashboard/patients');

    await page.getByRole('button', { name: /add patient/i }).click();

    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();

    // The Chart ID input is the first input in the modal whose placeholder
    // starts with "C-" — unique within the form (MRN/DrChrono have different
    // placeholders). Placeholder is server-fetched, so we poll briefly.
    const chartInput = modal.locator('input[placeholder^="C-"]').first();
    await expect(chartInput).toBeVisible();
    await expect
      .poll(async () => (await chartInput.getAttribute('placeholder')) ?? '', { timeout: 5000 })
      .toMatch(/^C-\d+$/);

    // Create a patient with blank chartId — server must auto-assign.
    const unique = `E2EAuto${Date.now().toString().slice(-6)}`;
    await modal.locator('input[placeholder="Sarah"]').fill(unique);
    await modal.locator('input[placeholder="Mitchell"]').fill('Charty');

    await modal.getByRole('button', { name: /create patient/i }).click();
    await expect(modal.getByText(/patient created successfully/i)).toBeVisible();

    // Modal auto-closes after ~1s. Reload the list explicitly so we're
    // looking at fresh server-rendered data.
    await page.waitForTimeout(1200);
    await page.goto('/dashboard/patients');

    await page.getByPlaceholder(/search patients/i).fill(unique);
    const row = page.locator(`text=${unique} Charty`).first();
    await expect(row).toBeVisible();

    // The row's chart id column should show a C-<n> value — confirms the
    // server auto-assigned a chart ID. Loose assertion: any C-<digits>
    // in the filtered (single-row) list.
    const chartCell = page.locator('text=/^C-\\d+$/').first();
    await expect(chartCell).toBeVisible();
  });
});
