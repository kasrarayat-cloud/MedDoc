// ============================================================================
// Patient-picker helper — Step 1 of the two-step /visits/new flow (T-M17.2).
// ----------------------------------------------------------------------------
// /visits/new is now two steps: Step 1 is the patient picker
// (new-visit-client.tsx → PatientPicker); the capture-mode tiles
// (Upload audio / Dictate live / Text to SOAP) only render in Step 2,
// AFTER a patient is selected. The scenario specs predate this split and
// clicked a mode tile straight away — so they timed out (full-qa F2).
//
// This helper creates a fresh patient via the picker's inline form so Step 2
// renders. A fresh-signup user has no patients, so the picker's fuzzy-match
// returns nothing and the create completes without the duplicate modal.
// `onSelect` then swaps the client to Step 2 (no URL change), so we wait for
// the "Pick a capture mode" heading before returning.
//
// Call AFTER page.goto('/visits/new') and BEFORE clicking a mode tile.
// ============================================================================

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

export async function createPatientAndContinue(
  page: Page,
  name = 'QA Patient',
  dob = '1990-01-01',
): Promise<void> {
  await page.getByRole('button', { name: /create new patient/i }).click();

  // The create form's <label>s aren't associated with their inputs, so target
  // the Name field by its unique placeholder and the DOB field by input type
  // (it's the only date input on the page). External ID is optional — skip it.
  await page.getByPlaceholder('Jane Doe').fill(name);
  await page.locator('input[type="date"]').fill(dob);

  await page.getByRole('button', { name: /create & continue/i }).click();

  // onSelect → Step 2 renders the patient pill + the capture-mode tiles.
  await expect(
    page.getByText(/pick a capture mode/i),
  ).toBeVisible({ timeout: 15_000 });
}
