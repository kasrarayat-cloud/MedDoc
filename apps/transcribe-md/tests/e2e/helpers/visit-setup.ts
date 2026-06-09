// ============================================================================
// Visit/patient setup helpers — Phase 2 Batch 1.
// ----------------------------------------------------------------------------
// Self-contained data builders so each spec creates exactly the state it needs
// (a fresh-signup user owns its own practice → no cross-spec coupling, no shared
// seed). Under MOCK_AI_CALLS the worker pipeline produces a deterministic SOAP,
// so createReadyTextVisit resolves quickly.
// ============================================================================

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';

import { createPatientAndContinue } from './patient';
import { waitForVisitStatus } from './waitForReady';

/** Create a patient via POST /api/patients (the "standalone" path the visit
 *  picker also uses) and return its id + name. Reuses the page's auth cookie. */
export async function createPatientViaApi(
  page: Page,
  name: string,
  dateOfBirth = '1985-05-15',
): Promise<{ id: string; name: string }> {
  const res = await page.request.post('/api/patients', {
    data: { name, dateOfBirth, externalId: null },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(
    res.ok(),
    `POST /api/patients failed: ${res.status()} ${await res.text()}`,
  ).toBe(true);
  const body = (await res.json()) as { patient: { id: string; name: string } };
  return { id: body.patient.id, name: body.patient.name };
}

/** Create a text_notes visit and drive it to READY under MOCK. Assumes the
 *  caller already signed up. With `patientId` it attaches to an existing
 *  patient (the ?patientId pre-select flow → step 2 directly); otherwise it
 *  creates a fresh patient via the picker. Returns the visit id. */
export async function createReadyTextVisit(
  page: Page,
  opts: { patientId?: string; patientName?: string } = {},
): Promise<string> {
  if (opts.patientId) {
    await page.goto(`/visits/new?patientId=${opts.patientId}`);
  } else {
    await page.goto('/visits/new');
    await createPatientAndContinue(page, opts.patientName ?? 'QA Patient');
  }
  await page.getByRole('button', { name: /text to soap/i }).click();
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;
  await page
    .getByLabel('Clinical shorthand')
    .fill('Follow-up visit. Patient stable, no new complaints. Continue current management.');
  await page.getByRole('button', { name: /expand to soap/i }).click();
  await waitForVisitStatus(page, visitId, 'READY');
  return visitId;
}
