// ============================================================================
// Scenario 10 — Visit lifecycle: delete → trash → restore, and archive.
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. Exercises VisitLifecycleActions:
//   - a READY visit → Delete (soft) → appears in the patient Trash tab → Restore
//   - a SIGNED visit → Archive → hidden from the active /visits list
// Signing is done via the API (no delivery) so the archive path reaches SIGNED
// without driving the export/clipboard machinery.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createPatientViaApi, createReadyTextVisit } from '../helpers/visit-setup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('lifecycle: delete a READY visit → trash → restore', async ({ page }) => {
  await signupFreshUser(page, 'v-del');
  const patient = await createPatientViaApi(page, 'Trash Patient');
  const visitId = await createReadyTextVisit(page, { patientId: patient.id });

  await page.goto(`/visits/${visitId}`);
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: /move to trash/i }).click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 });

  // Gone from the active visit list.
  await page.goto('/visits');
  await expect(page.locator(`a[href="/visits/${visitId}"]`)).toHaveCount(0);

  // Present in the patient's Trash tab (the trashed card links back to the visit).
  await page.goto(`/patients/${patient.id}?tab=trash`);
  await expect(page.locator(`#main a[href="/visits/${visitId}"]`)).toBeVisible();

  // Restore from the visit page's trash banner → back in the active list.
  //
  // The wait below is load-bearing, not defensive. Restore is a CLIENT fetch:
  // the handler does `await fetch(POST /restore)` and only then router.refresh().
  // Playwright's click() resolves as soon as the click is DISPATCHED, so a bare
  // `click(); goto('/visits')` navigates while that POST is still in flight —
  // and navigating tears the page down, which aborts it. The visit then never
  // leaves the trash and the list assertion fails 10s later, pointing at the
  // list rather than at the restore that never happened.
  //
  // This was intermittent in CI and green locally: the race only loses when the
  // box is loaded enough for the POST to still be in flight one tick after the
  // click, which is exactly what parallel workers on a CI runner produce. That
  // made "re-run the job" look like a fix, so it stayed a flake instead of a bug.
  //
  // Waiting on the RESPONSE is the deterministic signal — it proves the server
  // committed before we navigate. Deliberately not the success toast: toasts
  // auto-dismiss (4s) and would reintroduce a timing dependency.
  await page.goto(`/visits/${visitId}`);
  const restored = page.waitForResponse(
    (r) =>
      r.url().includes(`/api/visits/${visitId}/restore`) &&
      r.request().method() === 'POST',
    { timeout: 15_000 },
  );
  await page.getByRole('button', { name: /restore/i }).click();
  expect((await restored).status()).toBe(200);

  await page.goto('/visits');
  await expect(page.locator(`a[href="/visits/${visitId}"]`)).toBeVisible({
    timeout: 10_000,
  });
});

test('lifecycle: archive a SIGNED visit → hidden from the active list', async ({
  page,
}) => {
  await signupFreshUser(page, 'v-arch');
  const visitId = await createReadyTextVisit(page, { patientName: 'Archive Patient' });

  // Sign via the API (no delivery destinations) so the visit reaches SIGNED.
  const signRes = await page.request.post(`/api/visits/${visitId}/sign`, {
    data: { destinations: [] },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(
    signRes.ok(),
    `sign failed: ${signRes.status()} ${await signRes.text()}`,
  ).toBe(true);

  await page.goto(`/visits/${visitId}`);
  // SIGNED → the lifecycle offers Archive (trigger), then a confirm dialog.
  await page.getByRole('button', { name: 'Archive', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Archive', exact: true })
    .click();
  await expect(page).toHaveURL(/\/dashboard$/, { timeout: 10_000 });

  // Hidden from the active /visits list.
  await page.goto('/visits');
  await expect(page.locator(`a[href="/visits/${visitId}"]`)).toHaveCount(0);
});
