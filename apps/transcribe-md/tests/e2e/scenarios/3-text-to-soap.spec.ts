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
import { attestAndSubmit, openSignFlow } from '../helpers/sign';

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

  // ── Sign flow → the Sign & Send modal — PDF only. ────────────────────────
  //
  // ⚠️ WAIT FOR AN OPENER BEFORE WALKING. `waitForVisitStatus` above polls the
  // API; the PAGE only swaps to its READY surface when its own poller fires
  // `router.refresh()` (`processing-typewriter.tsx:248`), so we can arrive here
  // a tick early with the processing view still mounted. `openSignFlow`
  // branches on a SYNCHRONOUS `.count()` of the Rounds rail — one tick early
  // and it would take the legacy branch and then fail 10s later on a button
  // the Rounds skin never renders. This turns that race into a statement about
  // the opener.
  await expect(
    page
      .getByTestId('rounds-review-sign')
      .or(page.getByRole('button', { name: /sign & send/i }))
      .first(),
    'visit reached READY but neither sign opener ever rendered on the page',
  ).toBeVisible({ timeout: 30_000 });

  // WAS (:54): page.getByRole('button', { name: /sign & send/i }).click()
  // That lone button is the FLAG-OFF opener only — `soap-editor.tsx:478` and
  // `review-tabs-v2.tsx:258`. Under Rounds it does not exist at all: the stage
  // rail carries `rounds-review-sign` (`stage.tsx:259`) → the gate flow's
  // attestation (`gate-flow.tsx:337`) → the gate signbar's "Sign & Download"
  // (`review-sign-bar.tsx:118`). `openSignFlow` walks whichever the BUILT skin
  // has, branching on the DOM rather than on a flag that is not in the runner's
  // environment.
  // FAILS IF: no opener is reachable, the rail is present but never enabled,
  // the gate flow never presents the attestation, or the gates never clear —
  // the helper asserts each of those by name.
  await openSignFlow(page);

  // ⚠️ NOT `getByRole('dialog')`. Under Rounds the gate flow carries
  // role="dialog" (`gate-flow.tsx:228`) AND so does the Radix modal, so the
  // role query is strict-mode ambiguous with both open. The modal's own
  // identity is its `Dialog.Title` (`sign-and-send-modal.tsx:347`, rendered as
  // an <h2> by Radix) — unique in the app, and present in EVERY modal state
  // including the pending "Signing…" one.
  const signModal = page.getByRole('heading', {
    name: 'Sign and deliver your note',
    exact: true,
  });
  await expect(
    signModal,
    'openSignFlow completed but the Sign & Send modal never opened',
  ).toBeVisible({ timeout: 10_000 });

  // Default selection is Copy-for-Epic + PDF (`sign-and-send-modal.tsx:130`).
  // Uncheck Epic, keep PDF. Assert the toggle actually FLIPPED rather than
  // trusting the click: under Rounds this row now sits above a second overlay,
  // and a swallowed click would otherwise surface 20s away as "waiting for
  // event download" with Epic still selected.
  const epic = page.getByRole('button', { name: 'Copy for Epic', exact: true });
  await expect(epic).toHaveAttribute('aria-pressed', 'true');
  await epic.click();
  await expect(
    epic,
    'clicked Copy for Epic but it stayed selected — the sign would deliver a ' +
      'clipboard destination this test never asked for',
  ).toHaveAttribute('aria-pressed', 'false');
  // PDF should already be checked.

  const downloadPromise = page.waitForEvent('download', { timeout: 20_000 });
  await attestAndSubmit(page);
  const pdf = await downloadPromise;

  expect(pdf.suggestedFilename()).toMatch(/\.pdf$/);

  // Modal closes quickly (T-M8 Bug 3 fix).
  // WAS (:66): expect(page.getByRole('dialog')).toBeHidden() — ambiguous under
  // Rounds per the note above, and doubly wrong here: Radix aria-hides the gate
  // flow only WHILE the modal is open, so the moment the modal closes the gate
  // flow's own dialog re-enters the a11y tree and a role-scoped hidden-check
  // would go red for a reason that has nothing to do with T-M8 Bug 3.
  // FAILS IF: the modal stays mounted after a successful sign — the exact
  // regression. Anchoring on the TITLE and not on the "Sign & Deliver" button
  // is load-bearing: that button relabels to "Signing…" while pending
  // (`sign-and-send-modal.tsx:596`), so a modal wedged mid-sign would satisfy
  // a hidden-check on the button while still sitting on screen.
  await expect(signModal).toBeHidden({ timeout: 5_000 });

  // Visit flipped to SIGNED.
  await waitForVisitStatus(page, visitId, 'SIGNED', { timeoutMs: 10_000 });
});
