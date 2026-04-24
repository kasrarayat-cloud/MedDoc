import { test, expect } from '@playwright/test';
import * as path from 'node:path';

import { requireTestCreds, E2E_READ_ONLY, PROCESSING_TIMEOUT_MS } from './helpers/env';
import { loginApp } from './helpers/auth';

// End-to-end: login → new visit → upload audio → wait for READY →
// check the SOAP tab renders → sign. Mutates prod state, so it only
// runs when E2E_READ_ONLY=false is explicitly set AND credentials
// exist. Audio fixture reuses the one shipped with the existing
// transcribe-md e2e suite.

const AUDIO_FIXTURE = path.resolve(
  __dirname,
  '../../../apps/transcribe-md/tests/e2e/fixtures/audio/silence-3sec.mp3'
);

test.skip(
  E2E_READ_ONLY,
  'full-visit-flow mutates prod (creates patient + visit + signs); set E2E_READ_ONLY=false to run'
);

test('full visit flow — login → upload → SOAP → sign', async ({ page }) => {
  const creds = requireTestCreds('app');
  test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
  if (!creds) return;

  await loginApp(page, creds.email, creds.password);

  // New visit. The button text on the dashboard "Start new visit".
  await page.getByRole('link', { name: /new visit|start new/i }).first().click();
  await page.waitForURL(/\/visits\/new/);

  // Patient picker: create a disposable test patient by typing a unique
  // name that won't match any existing patient (forces the "create new"
  // branch of the picker).
  const patientName = `E2E Probe ${Date.now()}`;
  await page.getByPlaceholder(/search patient|patient name/i).fill(patientName);
  // Short wait for the 300ms debounce.
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: /create new patient|new patient/i }).click();

  // Specialty + chief complaint. Use whatever the first <select> option
  // is — the test doesn't care which specialty, only that the visit
  // draft validates.
  const specialtySelect = page.getByLabel(/specialty/i);
  if (await specialtySelect.isVisible().catch(() => false)) {
    await specialtySelect.selectOption({ index: 1 });
  }
  const cc = page.getByLabel(/chief complaint|reason/i);
  if (await cc.isVisible().catch(() => false)) {
    await cc.fill('Automated test: chest pain check');
  }

  // Choose the upload-audio input mode then submit.
  const audioRadio = page.getByRole('radio', { name: /audio upload|upload audio/i });
  if (await audioRadio.isVisible().catch(() => false)) {
    await audioRadio.check();
  }
  await page.getByRole('button', { name: /create visit|start|continue/i }).click();

  // On the visit page, the audio-uploader file input accepts our
  // fixture. Wait for a ready state to appear.
  await page.waitForURL(/\/visits\/[^/]+$/);
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(AUDIO_FIXTURE);

  // Poll for READY by watching the status chip in the header. The
  // status changes QUEUED → TRANSCRIBING → EXTRACTING → ... → READY.
  await expect(async () => {
    const status = await page
      .getByText(/ready|needs review|signed/i)
      .first()
      .isVisible({ timeout: 2_000 });
    expect(status).toBe(true);
  }).toPass({ timeout: PROCESSING_TIMEOUT_MS, intervals: [2_000, 5_000] });

  // SOAP tab should be the default. Look for at least one heading the
  // polish layer emits.
  await expect(
    page.getByRole('heading', { name: /subjective|objective|assessment|plan/i }).first()
  ).toBeVisible({ timeout: 10_000 });

  // Sign & Send → confirm → modal closes. Don't actually email — use
  // the download PDF path to avoid SMTP traffic.
  await page.getByRole('button', { name: /sign & send/i }).click();
  await page.getByRole('button', { name: /download pdf/i }).click();
  await page.getByRole('button', { name: /sign & deliver/i }).click();
  await expect(page.getByRole('dialog')).toBeHidden({ timeout: 10_000 });
});
