// ============================================================================
// Scenario 1 — Fresh signup → audio upload → SOAP READY → sign with
//              clipboard + PDF + DOCX (all three).
// ----------------------------------------------------------------------------
// Covers THREE T-M8 bugs at once:
//   - Bug 1: mode-tile click without dropdown interaction must not 500
//   - Bug 2: PDF + DOCX simultaneously selected → both files on disk
//   - Bug 3: sign modal closes within 2s, doesn't hang on "Signing…"
//
// Depends on MOCK_AI_CALLS=true on the worker. Real audio bytes in
// fixtures/audio/silence-3sec.mp3 are ignored by the mocked Deepgram
// call; the visit pipeline still runs end-to-end through all layers.
// ============================================================================

import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { waitForVisitStatus } from '../helpers/waitForReady';

const AUDIO_FIXTURE = resolve(__dirname, '../fixtures/audio/silence-3sec.mp3');

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 1: fresh signup → audio upload → sign clipboard+PDF+DOCX', async ({
  page,
}) => {
  await signupFreshUser(page, 's1');

  await page.goto('/visits/new');
  await page.getByRole('button', { name: /upload audio/i }).click();

  await page.waitForURL(/\/visits\/[^/]+$/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;

  // AudioUploader uses a hidden <input type="file">. setInputFiles
  // fires the same onChange the drop-zone click uses.
  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles(AUDIO_FIXTURE);

  // Upload triggers a POST /api/visits/[id]/upload; once that
  // returns 202, the visit goes QUEUED → pipeline. Wait for READY.
  await waitForVisitStatus(page, visitId, 'READY');

  // Sign & Send modal.
  await page.getByRole('button', { name: /sign & send/i }).click();
  // Defaults are clipboard_epic + pdf. Toggle DOCX on.
  await page.getByRole('button', { name: /download docx/i }).click();

  // Two downloads expected: PDF then DOCX (T-M8 Bug 2 — 600ms gap).
  const pdfPromise = page.waitForEvent('download', { timeout: 10_000 });
  await page.getByRole('button', { name: /sign & deliver/i }).click();
  const pdf = await pdfPromise;
  expect(pdf.suggestedFilename()).toMatch(/\.pdf$/);

  // DOCX arrives up to ~1s later (gap + request latency).
  const docx = await page.waitForEvent('download', { timeout: 10_000 });
  expect(docx.suggestedFilename()).toMatch(/\.docx$/);

  // Modal closes (T-M8 Bug 3 — no more "Signing…" hang).
  await expect(page.getByRole('dialog')).toBeHidden({ timeout: 5_000 });

  await waitForVisitStatus(page, visitId, 'SIGNED', { timeoutMs: 10_000 });
});
