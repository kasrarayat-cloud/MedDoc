// ============================================================================
// Scenario 3 — Fresh signup → text mode → READY → sign with PDF
// ----------------------------------------------------------------------------
// Regression for T-M8 Bug 1 (/visits/new 500 on mode-tile click
// without a specialty dropdown interaction) plus the text-mode
// pipeline path. Asserts the full round trip: signup, create
// text_notes visit, submit ~400 char clinical shorthand, wait for
// READY, sign with PDF only, confirm file downloaded + state SIGNED.
// ============================================================================

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';
import { waitForVisitStatus } from '../helpers/waitForReady';

const CLINICAL_NOTES = readFileSync(
  resolve(__dirname, '../fixtures/notes/clinical-notes.txt'),
  'utf8'
);

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 3: fresh signup → text → READY → sign PDF', async ({ page }) => {
  await signupFreshUser(page, 's3');

  await page.goto('/visits/new');
  // Step 1 (two-step flow): pick a patient so the capture-mode tiles render.
  await createPatientAndContinue(page);
  await page.getByRole('button', { name: /text to soap/i }).click();

  // Cuid format — matches /visits/c<alphanumeric> but NOT /visits/new
  // (which would be the pre-submission state).
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;

  // TextComposer renders a textarea with aria-label "Clinical
  // shorthand". Fill it and click the "Expand to SOAP" CTA.
  await page.getByLabel('Clinical shorthand').fill(CLINICAL_NOTES);
  await page.getByRole('button', { name: /expand to soap/i }).click();

  // Pipeline kicks off. With MOCK_AI_CALLS on the worker this
  // resolves in ~1-3 sec; 60s cap for safety.
  await waitForVisitStatus(page, visitId, 'READY');

  // Sign & Send modal — PDF only.
  await page.getByRole('button', { name: /sign & send/i }).click();
  // Default selection is Copy-for-Epic + PDF. Uncheck Epic, keep PDF.
  await page.getByRole('button', { name: /copy for epic/i }).click();
  // PDF should already be checked.

  const downloadPromise = page.waitForEvent('download', { timeout: 20_000 });
  await page.getByRole('button', { name: /sign & deliver/i }).click();
  const pdf = await downloadPromise;

  expect(pdf.suggestedFilename()).toMatch(/\.pdf$/);

  // Modal closes quickly (T-M8 Bug 3 fix).
  await expect(page.getByRole('dialog')).toBeHidden({ timeout: 5_000 });

  // Visit flipped to SIGNED.
  await waitForVisitStatus(page, visitId, 'SIGNED', { timeoutMs: 10_000 });
});
