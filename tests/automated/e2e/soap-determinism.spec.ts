import { test, expect } from '@playwright/test';
import * as path from 'node:path';

import {
  requireTestCreds,
  E2E_READ_ONLY,
  PROCESSING_TIMEOUT_MS,
} from './helpers/env';
import { loginApp } from './helpers/auth';
import { cosineSimilarity } from './helpers/similarity';

// Uploads the same audio fixture three times against the live worker
// and asserts that the pairwise cosine similarity on the SOAP text is
// ≥ 0.80. Confirms the per-layer `temperature: 0.2` actually stuck
// and that Claude isn't sampling wildly.
//
// Expensive — 3 full pipeline runs hit real Deepgram + Anthropic. Only
// runs when E2E_READ_ONLY=false AND ENABLE_DETERMINISM_TEST=true.
// Leave the second flag off by default; enable from the nightly cron.

const ENABLED = process.env.ENABLE_DETERMINISM_TEST === 'true';
const AUDIO_FIXTURE = path.resolve(
  __dirname,
  '../../../apps/transcribe-md/tests/e2e/fixtures/audio/silence-3sec.mp3'
);

test.skip(
  E2E_READ_ONLY || !ENABLED,
  'determinism spec is opt-in; set E2E_READ_ONLY=false + ENABLE_DETERMINISM_TEST=true'
);

async function runOnce(
  page: import('@playwright/test').Page,
  patientName: string
): Promise<string> {
  await page.goto('/visits/new');
  await page.getByPlaceholder(/search patient|patient name/i).fill(patientName);
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: /create new patient|new patient/i }).click();

  const audioRadio = page.getByRole('radio', { name: /audio upload|upload audio/i });
  if (await audioRadio.isVisible().catch(() => false)) {
    await audioRadio.check();
  }
  await page.getByRole('button', { name: /create visit|start|continue/i }).click();

  await page.waitForURL(/\/visits\/[^/]+$/);
  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(AUDIO_FIXTURE);

  await expect(async () => {
    const ready = await page
      .getByText(/ready|needs review/i)
      .first()
      .isVisible({ timeout: 2_000 });
    expect(ready).toBe(true);
  }).toPass({ timeout: PROCESSING_TIMEOUT_MS, intervals: [3_000, 5_000] });

  // Grab the SOAP tab's plain text. The tab is already active on
  // landing when status is READY.
  const soap = await page
    .getByRole('button', { name: /soap note/i })
    .first();
  if (await soap.isVisible().catch(() => false)) {
    await soap.click();
  }
  return (await page.locator('article, [role="article"], main').first().innerText())
    .trim();
}

test('three identical dictations yield ≥80% similar SOAPs', async ({ page }) => {
  const creds = requireTestCreds('app');
  test.skip(!creds, 'TEST_APP_EMAIL / TEST_APP_PASSWORD not set');
  if (!creds) return;

  await loginApp(page, creds.email, creds.password);

  const soaps: string[] = [];
  for (let i = 1; i <= 3; i++) {
    const text = await runOnce(page, `Determinism Probe ${i}-${Date.now()}`);
    soaps.push(text);
  }

  const pairs: [number, number][] = [
    [0, 1],
    [0, 2],
    [1, 2],
  ];
  for (const [a, b] of pairs) {
    const sim = cosineSimilarity(soaps[a]!, soaps[b]!);
    expect(sim, `run ${a + 1} vs run ${b + 1}: similarity ${sim.toFixed(3)}`).toBeGreaterThanOrEqual(
      0.8
    );
  }
});
