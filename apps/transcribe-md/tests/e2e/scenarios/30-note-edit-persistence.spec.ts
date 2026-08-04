// ============================================================================
// Scenario 30 — a note edit REACHES THE SERVER and survives a reload.
// ----------------------------------------------------------------------------
// ⚠️ THIS EXISTS TO CLOSE A COVERAGE HOLE F-ret.1 OPENED, IN THE SAME PASS THAT
// OPENED IT.
//
// `9-soap-edit.spec.ts` was retired on 2026-08-04: the inline SOAP textarea it
// drove cannot render on any shipped surface (`SoapInlineEdit.tsx:92` returns a
// plain div when `readonly`, and both live mounts pass `chromeless`). Retiring
// it was correct. It also left the REQUIRED pack with no coverage of the claim
// that spec actually protected — **that a doctor's edit to a note reaches the
// server and is still there after a reload.**
//
// That capability did not go away; it moved. The read-only paper is the
// display surface and the CHAT EDITOR is the way in
// (`saveNoteSectionAction`). But its coverage lived only in `visit-document`,
// a NON-REQUIRED project — and "a capability covered only by non-required
// packs" is precisely the two-month gate defect in miniature: the check exists,
// nothing blocks on it, and everyone believes it is guarded.
//
// ⚠️ WHY THE EXISTING SPEC WAS NOT SIMPLY PROMOTED. `visit-document.spec.ts`
// needs a **CERTIFIED TWIN fixture** (e2e.yml:197-198 — it refuses to skip
// without one) and the **Gotenberg converter sidecar** (e2e.yml:576), neither
// of which the default pack stands up. Moving it would mean pulling that
// infrastructure into the required job. Its chat-edit test also runs a 420s
// walk that additionally proves re-fill, E/M staleness, signing and the
// delivered file — far more than persistence.
//
// So the CLAIM is promoted rather than the spec. This test proves exactly what
// `9-soap-edit` proved, on the surface that replaced it, with no twin, no
// sidecar and no download.
//
// ─── WHAT WOULD MAKE THIS FAIL (rule 7) ─────────────────────────────────────
//  · the chat editor accepting the turn but never calling saveNoteSectionAction
//    → the marker is absent after reload while the transcript still says
//      "Changed <section>"; the reload assertion is the one that catches it
//  · a refused edit reported as success → the `not.toContainText(/could not/i)`
//    guard, which exists because a section-name-only assertion PASSED on a
//    refused edit once already (visit-document.spec.ts:70-74)
//  · the drawer trigger disappearing → named at the point of the click
//  · the paper not drawing at all → the `review-document-view` assertion, which
//    is a real precondition and is kept
//  · the addressed section not existing → the chat replies "Could not change
//    Assessment" and the two guards below red on it
// ============================================================================

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { createReadyTextVisit } from '../helpers/visit-setup';

const EDIT_MARK = 'QA-CHAT-PERSIST-4b9d1c';

test.afterEach(() => {
  cleanupTestUsers();
});

test('note edit: a chat edit persists to the server and survives a reload', async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signupFreshUser(page, 'note-persist');
  const visitId = await createReadyTextVisit(page, { patientName: 'Persist Patient' });

  await page.goto(`/visits/${visitId}`);
  // Settle before touching a client-driven control — the lesson from
  // 16-account-settings, where a click that beat the client tree submitted as a
  // native POST and the result never reached React.
  await page.waitForLoadState('networkidle');

  // The paper is READ-ONLY: no inline edit affordance anywhere. This is the
  // half of `9-soap-edit`'s world that genuinely went away, and asserting its
  // absence is what makes the chat path the only way in rather than a
  // coincidence.
  await expect(page.locator('[data-testid^="section-edit-"]')).toHaveCount(0);
  await expect(page.locator('[data-testid^="section-textarea-"]')).toHaveCount(0);

  // ⚠️ THE SECTION IS NAMED, NOT DISCOVERED FROM THE DOM — and that change is
  // the fix for a CI-only failure, not a weakening.
  //
  // This read `[data-section]` off the paper to learn a section name. It works
  // here and fails in CI: the paper DRAWS (asserted below) but carries no
  // `[data-section]` anchors there. Not timing — `createReadyTextVisit` already
  // waits for READY (visit-setup.ts:56) — and not ordering: running CI's exact
  // sequence locally, note-format specs first, is 12/12. It is an environmental
  // render-path difference, the same class as the `.qm-npv-docx` overflow that
  // reproduced only in CI.
  //
  // The DOM read was incidental to the CLAIM. This test is about persistence,
  // not about how the paper marks its sections. The note is SOAP and its
  // sections are canonical — measured: ["Subjective","Objective","Assessment",
  // "Plan"] — so addressing one by name removes a dependency that was never
  // part of what is being proven.
  //
  // ⚠️ AND IT CANNOT PASS VACUOUSLY IF THE SECTION IS ABSENT. The chat replies
  // "Could not change Assessment: …" on a refused edit, and the two guards
  // below — `Changed Assessment` present, `could not` absent — turn that into a
  // loud red rather than a silent skip. That pairing exists because a
  // section-name-only assertion PASSED on a refused edit once already
  // (visit-document.spec.ts:70-74).
  const section = 'Assessment';

  // Open the chat. Under Rounds it is a drawer off the action rail.
  const trigger = page.getByTestId('rounds-chat-trigger');
  await expect(
    trigger,
    'no chat trigger on the stage — the note has no edit path at all',
  ).toBeVisible({ timeout: 30_000 });
  await trigger.click();

  const editor = page.getByTestId('chat-editor');
  await expect(editor, 'the chat drawer opened but carries no editor').toBeVisible({
    timeout: 30_000,
  });

  // `MOCKEDIT <section> :: <body>` is the MOCK_AI directive the QA stack
  // answers deterministically — the same convention visit-document.spec.ts
  // uses, so one fixture serves both.
  const before = await page.getByTestId('chat-turn-assistant').count();
  await page.getByTestId('chat-input').fill(`MOCKEDIT ${section} :: ${EDIT_MARK}`);
  await page.getByTestId('chat-send').click();
  await expect(page.getByTestId('chat-turn-assistant')).toHaveCount(before + 1, {
    timeout: 120_000,
  });

  // ⚠️ THE TURN MUST SAY IT ACTED **AND** THAT IT SUCCEEDED. The failure line
  // is "Could not change <section>: <error>", so an assertion that only looks
  // for the section name passes on a REFUSED edit. That is not hypothetical —
  // it passed on one (visit-document.spec.ts:70-74).
  const actions = page.getByTestId('chat-actions').last();
  await expect(actions).toContainText(new RegExp(`Changed ${section}`, 'i'));
  await expect(actions).not.toContainText(/could not/i);

  // The edit is on the page…
  await expect(page.getByText(EDIT_MARK).first()).toBeVisible({ timeout: 60_000 });

  // …and it is on the SERVER. This is the whole point of the test and the one
  // assertion `9-soap-edit` existed for: a reload re-reads from the database,
  // so a marker that survives it was persisted rather than held in local state.
  await page.reload();
  await page.waitForLoadState('networkidle');
  await expect(
    page.getByText(EDIT_MARK).first(),
    'the edit did not survive a reload — it never reached saveNoteSectionAction, ' +
      'so the chat reported a change the server never made',
  ).toBeVisible({ timeout: 60_000 });
});
