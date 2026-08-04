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
import { attestAndSubmit, openSignFlow, expectSignModalClosed } from '../helpers/sign';

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

  // ── RE-POINT (F-ret) ──────────────────────────────────────────────────────
  // WAS: `page.getByRole('button', { name: /sign & send/i }).click()`.
  // That single button is the FLAG-OFF opener only (`soap-editor.tsx:478`,
  // `review-tabs-v2.tsx:258` set `triggerLabel="Sign & Send"`). Under the
  // shipped Rounds skin there is no such button: the stage's action rail
  // carries `rounds-review-sign` (`src/components/rounds/stage.tsx:259`), which
  // opens the gate flow, and the modal's trigger is the gate signbar's
  // "Sign & Download" (`src/app/visits/[id]/review-sign-bar.tsx:118`, rendered
  // at `variant="gate"` on line 127). Two walks, one modal.
  //
  // `openSignFlow` branches on the DOM — NOT on a flag — so this scenario runs
  // on both the flag-ON and flag-OFF images. It is deliberately not re-derived
  // here: five specs hand-rolled this walk and all five broke together.
  //
  // WHAT WOULD MAKE IT FAIL: no `rounds-review-sign` rail AND no "Sign & Send"
  // button on a READY visit (the helper asserts exactly that and says so); the
  // rail present but never enabled; the gate flow never presenting
  // `rounds-gate-attest`; or the gates never clearing to reveal
  // `review-doc-signbar`. It cannot pass on a visit that is not signable.
  await openSignFlow(page);

  // Default: clipboard_epic + pdf (`sign-and-send-modal.tsx:130`). Uncheck PDF
  // to avoid triggering a download event in this scenario (we already cover
  // downloads in scenario 1).
  //
  // WAS: a blind `.click()` on /download pdf/i. That row is a TOGGLE
  // (`CheckboxRow`, `sign-and-send-modal.tsx:645` — `aria-pressed={checked}`),
  // not a command, so a blind click SELECTS it if the default ever flips, and
  // this scenario would start firing an unhandled download while still passing
  // the click. Read the state, act only if needed, then assert the state we
  // actually depend on.
  //
  // WHAT WOULD MAKE IT FAIL: the PDF destination staying pressed after the
  // click (a broken toggle), or the row disappearing from the modal — either
  // way `toHaveAttribute('aria-pressed', 'false')` has nothing to resolve
  // against and reports it.
  const pdfDestination = page.getByRole('button', {
    name: /^download pdf$/i,
  });
  if ((await pdfDestination.getAttribute('aria-pressed')) === 'true') {
    await pdfDestination.click();
  }
  await expect(
    pdfDestination,
    'the PDF destination is still selected — this scenario would fire an ' +
      'unhandled download',
  ).toHaveAttribute('aria-pressed', 'false');

  await attestAndSubmit(page);

  // WAS: `expect(page.getByRole('dialog')).toBeHidden()`.
  // ⚠️ `role="dialog"` IS AMBIGUOUS UNDER ROUNDS. The gate flow carries it
  // (`src/components/rounds/gate-flow.tsx:228`) AND so does the Radix modal
  // (`sign-and-send-modal.tsx:321`), so on the flag-ON image the role query
  // resolves to two nodes and a strict-mode `toBeHidden` either violates or
  // answers about the wrong one. Anchor on the modal's own submit control
  // instead: "Sign & Deliver" exists ONLY at `sign-and-send-modal.tsx:596` and
  // only while `signOnSubmit` is true, so it is gone the moment `submit()`
  // calls `setOpen(false)` (line 208) — i.e. only after the server accepted the
  // signature. The re-export modal on a SIGNED visit renders "Deliver", which
  // this regex does not match.
  //
  // NOT VACUOUS BY RENAME: `attestAndSubmit` has just asserted that exact
  // locator is present and enabled (`helpers/sign.ts:110-124`), so a renamed
  // button fails loudly one line earlier rather than passing here silently.
  //
  // WHAT WOULD MAKE IT FAIL: the sign request being refused (400
  // ATTESTATION_REQUIRED, an unconfirmed E/M change, a delivery error) — the
  // modal stays open and the button stays on screen.
  await expectSignModalClosed(page);

  await waitForVisitStatus(page, visitId, 'SIGNED', { timeoutMs: 10_000 });
});
