// ============================================================================
// Scenario 11 — Live-recording view renders (smoke).
// ----------------------------------------------------------------------------
// Phase 2 Batch 1. /visits/[id]/record is the full-screen recorder, eligible
// only for QUEUED visits. We assert the recorder SHELL renders (the
// Start-recording affordance) for a fresh dictation visit. We deliberately do
// NOT drive MediaRecorder — getUserMedia/MediaRecorder is unreliable headless
// (see scenario 2's notes), and the dictation→SOAP pipeline is already covered
// by scenario 2 via the upload-endpoint bypass.
// ============================================================================

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';

test.afterEach(() => {
  cleanupTestUsers();
});

test('record view: the recorder shell renders for a QUEUED dictation visit', async ({
  page,
}) => {
  await signupFreshUser(page, 'record');

  // Create a "dictate live" (voice_dictation) visit — it lands QUEUED.
  await page.goto('/visits/new');
  await createPatientAndContinue(page, 'Record Patient');
  await page.getByRole('button', { name: /dictate live/i }).click();
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;

  // The dedicated recorder renders for the eligible (QUEUED) visit — no redirect.
  await page.goto(`/visits/${visitId}/record`);
  await expect(page).toHaveURL(new RegExp(`/visits/${visitId}/record$`));
  await expect(
    page.getByRole('button', { name: /start recording/i }),
  ).toBeVisible();
});
