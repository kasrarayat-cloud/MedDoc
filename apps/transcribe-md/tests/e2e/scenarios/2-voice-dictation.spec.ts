// ============================================================================
// Scenario 2 — Fresh signup → voice dictation → READY → sign clipboard
// ----------------------------------------------------------------------------
// Originally attempted with a full MediaRecorder shim via
// page.addInitScript. Chromium headless's MediaRecorder + getUserMedia
// permission model is finicky, the VoiceDictator's state machine
// cares about specific event timings, and we lost a lot of time
// chasing flakiness. Switched to Approach B per T-M10 plan:
// bypass the UI recorder and POST the dictation audio straight to
// the upload endpoint. We still test:
//   - signup + create-visit in voice_dictation mode (covers Bug 1)
//   - dictation upload contract + pipeline end-to-end
//   - sign-and-send final state
// We lose coverage of the recorder UI itself (mic-prompt, chunked
// writes, level meter). That's a real gap; if the recorder UI
// regresses it's caught in manual QA, not here. Mark this as a
// follow-up if it becomes painful.
// ============================================================================

import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';
import { waitForVisitStatus } from '../helpers/waitForReady';

// Reuse the 3-sec ID3-header fixture. The mock-deepgram bypass
// doesn't read the bytes, and MinIO takes whatever we hand it.
const AUDIO_FIXTURE = resolve(__dirname, '../fixtures/audio/silence-3sec.mp3');

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 2: fresh signup → voice dictation → READY → sign clipboard', async ({
  page,
}) => {
  await signupFreshUser(page, 's2');

  await page.goto('/visits/new');
  // Step 1 (two-step flow): pick a patient so the capture-mode tiles render.
  await createPatientAndContinue(page);
  await page.getByRole('button', { name: /dictate live/i }).click();

  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitIdMatch = page.url().match(/\/visits\/(c[a-z0-9]+)/);
  const visitId = visitIdMatch?.[1];
  if (!visitId) {
    throw new Error(`couldn't parse visitId from ${page.url()}`);
  }

  // Bypass MediaRecorder UI. Send the audio bytes straight to the
  // dictation upload route — same contract the recorder uses after
  // it finalizes. Use the page's absolute URL so we don't rely on
  // relative-URL resolution inside APIRequestContext.
  const audioBytes = readFileSync(AUDIO_FIXTURE);
  const uploadUrl = new URL(
    `/api/visits/${visitId}/dictation/upload`,
    page.url()
  ).toString();
  const response = await page.request.post(uploadUrl, {
    data: audioBytes,
    headers: {
      // The fixture is an MP3 (ID3 header) — declare it honestly. The dictation
      // route now sniffs leading magic bytes and rejects a declared MIME that
      // doesn't match the actual bytes (INVALID_MAGIC_BYTES, 415); audio/mpeg is
      // an accepted dictation format. (Earlier this declared audio/webm while
      // sending MP3 bytes — a mismatch the hardened endpoint correctly rejects.)
      'content-type': 'audio/mpeg',
      'content-length': String(audioBytes.byteLength),
      'x-tm-filename': 'qa-dictation.mp3',
    },
  });
  expect(
    response.ok(),
    `dictation upload failed: ${response.status()} ${await response.text()}`
  ).toBe(true);

  await waitForVisitStatus(page, visitId, 'READY');

  // Reload so the visit page renders the READY state (the test
  // bypassed the UI so the client-side router never got a chance
  // to refresh).
  await page.reload();

  await page.getByRole('button', { name: /sign & send/i }).click();
  // Default: clipboard_epic + pdf. Uncheck PDF to avoid triggering
  // a download event in this scenario (we already cover downloads
  // in scenario 1).
  await page.getByRole('button', { name: /download pdf/i }).click();

  await page.getByRole('button', { name: /sign & deliver/i }).click();
  await expect(page.getByRole('dialog')).toBeHidden({ timeout: 5_000 });

  await waitForVisitStatus(page, visitId, 'SIGNED', { timeoutMs: 10_000 });
});
