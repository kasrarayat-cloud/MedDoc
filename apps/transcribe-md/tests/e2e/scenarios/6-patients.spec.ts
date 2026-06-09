// ============================================================================
// Scenario 6 — Patient management: list, standalone create, detail, edit.
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. Covers the patient surfaces beyond the visit-picker create
// that scenarios 1-5 already exercise:
//   - /patients list rendering + the in-memory name filter
//   - "standalone" create via POST /api/patients (there is intentionally no
//     dedicated create-patient UI — patients are created in the visit flow or
//     the API; this asserts the API path + that the list reflects it)
//   - /patients/[id] detail header + visit-history tab
//   - the Edit-patient dialog persisting a rename to the header
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createPatientViaApi, createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('patients list: standalone-created patients render + name filter narrows', async ({
  page,
}) => {
  await signupFreshUser(page, 'p-list');
  const ada = await createPatientViaApi(page, 'Ada Lovelace');
  const bjarne = await createPatientViaApi(page, 'Bjarne Stroustrup');

  await page.goto('/patients');
  // Both standalone-created patients render as cards linking to their detail.
  await expect(page.locator(`a[href="/patients/${ada.id}"]`)).toBeVisible();
  await expect(page.locator(`a[href="/patients/${bjarne.id}"]`)).toBeVisible();

  // The client-side name filter narrows the grid to the match…
  await page.getByLabel('Filter patients by name').fill('Ada');
  await expect(page.locator(`a[href="/patients/${ada.id}"]`)).toBeVisible();
  await expect(page.locator(`a[href="/patients/${bjarne.id}"]`)).toHaveCount(0);

  // …and clearing it restores both.
  await page.getByLabel('Filter patients by name').fill('');
  await expect(page.locator(`a[href="/patients/${bjarne.id}"]`)).toBeVisible();
});

test('patient detail: header + stats + visit history reflect a real visit', async ({
  page,
}) => {
  await signupFreshUser(page, 'p-detail');
  const patient = await createPatientViaApi(page, 'Grace Hopper');
  const visitId = await createReadyTextVisit(page, { patientId: patient.id });

  await page.goto(`/patients/${patient.id}`);
  await expect(
    page.getByRole('heading', { name: 'Grace Hopper', level: 1 }),
  ).toBeVisible();
  // The "Total visits" stat + the Visits-tab history list the one visit.
  await expect(page.getByText('Total visits')).toBeVisible();
  await expect(page.locator(`#main a[href="/visits/${visitId}"]`)).toBeVisible();
});

test('patient edit: rename via the Edit dialog persists to the header', async ({
  page,
}) => {
  await signupFreshUser(page, 'p-edit');
  const patient = await createPatientViaApi(page, 'Original Name');

  await page.goto(`/patients/${patient.id}`);
  await expect(
    page.getByRole('heading', { name: 'Original Name', level: 1 }),
  ).toBeVisible();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.locator('#edit-patient-name').fill('Renamed Patient');
  await page.getByRole('button', { name: /save changes/i }).click();

  // router.refresh() re-renders the server header with the new name.
  await expect(
    page.getByRole('heading', { name: 'Renamed Patient', level: 1 }),
  ).toBeVisible({ timeout: 10_000 });
  await expect(
    page.getByRole('heading', { name: 'Original Name', level: 1 }),
  ).toHaveCount(0);
});
