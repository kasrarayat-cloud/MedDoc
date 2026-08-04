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
//
// RE-POINTED 2026-08-04 (F-ret). The sign walk moved under the Rounds skin:
// the opener is the stage rail, not a "Sign & Send" button, and the modal is
// reached through the gate flow. The walk now comes from `helpers/sign.ts`
// (`openSignFlow`) so it is not re-derived here. The three bugs above are
// unchanged and still the point of this test — see the inline notes on each
// assertion for what would make it fail.
// ============================================================================

import { resolve } from 'node:path';

import { expect, test } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { createPatientAndContinue } from '../helpers/patient';
import { signupFreshUser } from '../helpers/signup';
import { waitForVisitStatus } from '../helpers/waitForReady';
import { attestAndSubmit, openSignFlow } from '../helpers/sign';

const AUDIO_FIXTURE = resolve(__dirname, '../fixtures/audio/silence-3sec.mp3');

test.afterEach(() => {
  cleanupTestUsers();
});

test('scenario 1: fresh signup → audio upload → sign clipboard+PDF+DOCX', async ({
  page,
}) => {
  await signupFreshUser(page, 's1');

  await page.goto('/visits/new');
  // Step 1 (two-step flow): pick a patient so the capture-mode tiles render.
  await createPatientAndContinue(page);
  await page.getByRole('button', { name: /upload audio/i }).click();

  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split('/').pop()!;

  // AudioUploader uses a hidden <input type="file">. setInputFiles
  // fires the same onChange the drop-zone click uses, which only
  // populates the file-preview card — the actual upload POST
  // doesn't fire until "Upload & transcribe" is clicked.
  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles(AUDIO_FIXTURE);
  await page.getByRole('button', { name: /upload & transcribe/i }).click();

  // Upload POST → 202 → visit goes QUEUED → pipeline. Wait for READY.
  await waitForVisitStatus(page, visitId, 'READY');

  // ── Open the sign flow. ──────────────────────────────────────────────────
  // WAS: `page.getByRole('button', { name: /sign & send/i }).click()`.
  // That is the LEGACY opener. Under the Rounds skin no such button exists:
  // the stage rail carries "Review & sign" (`src/components/rounds/stage.tsx`
  // :255-264, label from `signLabel` at :100-104), which opens the gate flow,
  // and the modal's own trigger is the gate signbar's "Sign & Download"
  // (`src/app/visits/[id]/review-sign-bar.tsx:118`). Two walks to one modal,
  // so the walk lives in the shared helper — which branches on the DOM, not on
  // a flag that is absent from the Playwright runner's environment.

  // FIRST, wait for the READY surface to exist. `waitForVisitStatus` polls
  // /api/visits/[id]/status and never navigates, so when it returns the DOM
  // may still be the processing view — `RoundsStage` mounts only inside
  // `visit-ready-view.tsx:1115`. The old line got away with this because a
  // bare `.click()` auto-waits; `openSignFlow` opens with a NON-waiting
  // `count()` probe, so an un-refreshed page would send it down the legacy
  // branch on a Rounds build and fail 10s later against the wrong locator.
  // `.or()` accepts either skin's opener: this asserts "a signable surface has
  // rendered", never "which skin", so a flag-OFF rollback image still passes.
  // FAILS IF: the client poller never refreshes onto the READY view, or the
  // READY view ships with neither sign entry point.
  const signEntry = page
    .getByTestId('rounds-review-sign')
    .or(page.getByRole('button', { name: /sign & send/i }));
  await expect(
    signEntry.first(),
    'visit reached READY but the page never rendered a sign entry point ' +
      '(neither the Rounds rail nor the legacy "Sign & Send")',
  ).toBeVisible({ timeout: 30_000 });

  await openSignFlow(page);

  // The destination modal is the same component on both skins, and its title
  // is the one string unique to it (`sign-and-send-modal.tsx:347-358`).
  // Asserting it VISIBLE here is what keeps the "modal closed" check at the
  // end of this test honest — a modal that never opened is also a modal that
  // is not visible, so without this the closing assertion would be vacuous.
  // ⚠️ NOT `getByRole('dialog')`: under Rounds the gate flow carries
  // role="dialog" too (`src/components/rounds/gate-flow.tsx:228`), so with both
  // open the role query is strict-mode ambiguous.
  // FAILS IF: openSignFlow reaches the gate but the modal never mounts.
  const signModalTitle = page.getByRole('heading', {
    name: 'Sign and deliver your note',
    exact: true,
  });
  await expect(
    signModalTitle,
    'the sign flow ran but the destination modal never opened',
  ).toBeVisible({ timeout: 10_000 });

  // Defaults are clipboard_epic + pdf (`sign-and-send-modal.tsx:129-131`).
  // Toggle DOCX on. EXACT accessible names, not `/download docx/i` — a
  // substring would also match a future "Download DOCX (signed)" row.
  // Bug 2 is "PDF *and* DOCX selected at once", so assert both toggles are
  // actually pressed. Without it, a regression that dropped `pdf` from the
  // defaults would surface as an opaque 10s "waiting for event download"
  // instead of a statement about which destination was off.
  // FAILS IF: the DOCX row's click does not set aria-pressed, or PDF stops
  // being a default selection.
  const docxToggle = page.getByRole('button', {
    name: 'Download DOCX',
    exact: true,
  });
  await docxToggle.click();
  await expect(
    docxToggle,
    'clicked Download DOCX but the destination did not become selected',
  ).toHaveAttribute('aria-pressed', 'true');
  await expect(
    page.getByRole('button', { name: 'Download PDF', exact: true }),
    'PDF is no longer selected by default — this test can no longer prove ' +
      'that PDF and DOCX deliver together (T-M8 Bug 2)',
  ).toHaveAttribute('aria-pressed', 'true');

  // Two downloads expected: PDF then DOCX (T-M8 Bug 2 — 600ms gap).
  const pdfPromise = page.waitForEvent('download', { timeout: 10_000 });
  await attestAndSubmit(page);
  const pdf = await pdfPromise;
  expect(pdf.suggestedFilename()).toMatch(/\.pdf$/);

  // DOCX arrives up to ~1s later (gap + request latency).
  const docx = await page.waitForEvent('download', { timeout: 10_000 });
  expect(docx.suggestedFilename()).toMatch(/\.docx$/);

  // Modal closes (T-M8 Bug 3 — no more "Signing…" hang).
  // WAS: `expect(page.getByRole('dialog')).toBeHidden()`. Unusable once this
  // test walks the Rounds path: the gate flow is ALSO role="dialog"
  // (`gate-flow.tsx:228`) alongside the Radix modal, so the role query goes
  // strict-mode ambiguous and an "is it gone?" assertion can resolve against
  // whichever node it likes.
  // ⚠️ AND DELIBERATELY NOT the "Sign & Deliver" button. While the submit is
  // pending that button relabels itself to "Signing…"
  // (`sign-and-send-modal.tsx:587` vs :596), so a `/sign & deliver/i` locator
  // goes hidden EXACTLY in the hang this line exists to catch — it would pass
  // on the bug. The Dialog.Title never changes, so it stays visible through a
  // hang and only disappears when the modal really unmounts.
  // FAILS IF: the modal stays mounted after a successful sign (the T-M8 Bug 3
  // regression), which is also why it is paired with the toBeVisible above.
  await expect(
    signModalTitle,
    'the sign modal is still open 5s after submitting — the "Signing…" hang',
  ).toBeHidden({ timeout: 5_000 });

  await waitForVisitStatus(page, visitId, 'SIGNED', { timeoutMs: 10_000 });
});
