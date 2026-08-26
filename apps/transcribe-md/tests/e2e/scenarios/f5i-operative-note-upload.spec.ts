// ============================================================================
// F5-i PART 1a — THE OWED QA-STACK HALF: A SECOND SHAPE IS UPLOADED THROUGH THE
// REAL UI.
// ----------------------------------------------------------------------------
// `gate-f5i-second-shape-refuses-honestly.test.ts` walks the second shape from
// real document bytes, in process:
//
//     .docx bytes -> ingestDocxTemplateSource -> compileTemplateDocx
//                 -> fallbackSemanticMappings -> deriveVerificationEncounter
//
// and its own header names what it does NOT do, in as many words:
//
//     "it does NOT walk an upload through the UI or the worker. Those are the
//      QA-stack half of part 1a and are named as owed, not claimed here."
//
// THIS SPEC IS THAT OWED HALF. It is the no-caller class one layer out: the
// in-process gate hands the engine bytes it opened itself, so nothing in the
// suite has ever established that a doctor dragging this file into the real
// manager reaches that engine at all.
//
// ⚠️ WHAT THIS SPEC CLAIMS, AND IT IS DELIBERATELY NARROW.
// It claims the second SHAPE survives the real upload path end to end: the
// committed operative-note fixture is accepted by the manager, its text is
// extracted by REAL extraction code, and the parse lands on the confirm step.
// That is the FRONT half F5-i recorded as unproven.
//
// ⚠️ WHAT IT DOES NOT CLAIM — AND THE REASON IS IN THE SHIPPED SOURCE, NOT IN
// AN OPINION ABOUT IT. It does NOT claim the twin's fail-closed OOXML boundary
// was exercised. `docx-to-text.ts` states that under the flag the marker text
// is "identical to the flag-OFF path for a clean dropdown template", and both
// paths run `docxToTextWithControls`. So for a CLEAN template the flag-ON and
// flag-OFF uploads are byte-identical BY DESIGN, and reaching review cannot
// discriminate them. Only a hostile fixture (macro/OLE/zip) would, and that is
// a different fixture and a different item. Asserting "the twin ran" from this
// spec would be a wrong-universe claim wearing a green tick.
//
// ⚠️ IT ALSO DOES NOT CLAIM PERSISTENCE. `ingestDocxTemplateSource` returns an
// IR and writes NOTHING — no `template_twin_*` row is created by an ordinary
// upload. A reader expecting `template_twin_source_artifacts` to move here
// would read a correct zero as a failure. Persistence belongs to the
// certification door, which is a separate surface.
//
// ⚠️ NO SHARED REGEX OVER THE TWO DOORS. `upload-flow.tsx` renders BOTH
// "Looks right — use this format" (accept) and "Something's off" (edit). A
// matcher spanning them would pass on either and prove neither — the failure
// helpers/noteFormat.ts already records. Each is named exactly.
// ============================================================================

import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { gotoNoteFormat } from '../helpers/noteFormat';

/** The committed second shape. Tracked as a binary precisely so an UPLOAD walk
 *  has a real file to drag in; its bytes are pinned to reviewable text by
 *  `operative-note-source.ts` and the in-process gate. */
const OPERATIVE_NOTE = resolve(
  __dirname,
  '../fixtures/sample-operative-note.docx',
);

/** The venous duplex — the ONE shape every end-to-end claim rested on before
 *  F5-i. Carried here as a POSITIVE CONTROL: it proves the upload mechanics of
 *  this spec work, so a failure on the operative note is a fact about the
 *  SECOND SHAPE and not about the harness. Without it, a broken selector and a
 *  genuinely rejected fixture are the same red. */
const VENOUS_FORM = resolve(__dirname, '../fixtures/sample-form.docx');

test.afterEach(() => {
  cleanupTestUsers();
});

/** Drive the upload exactly as a doctor does — click the visible button, which
 *  programmatically opens the hidden <input type=file>, and feed the chooser.
 *  A direct setInputFiles on that aria-hidden display:none input does not
 *  reliably fire onChange (scenario 21 records this). */
async function uploadFile(page: Page, file: string): Promise<void> {
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.getByRole('button', { name: /upload a file/i }).click(),
  ]);
  await chooser.setFiles(file);
}

/** Upload a .docx template and assert the real extraction + parse reached the
 *  confirm step. Named by the EXACT accept-door label. */
async function uploadAndExpectConfirm(
  page: Page,
  file: string,
  what: string,
): Promise<void> {
  await uploadFile(page, file);

  await expect(
    page.getByRole('button', { name: /something.s off/i }),
    `${what}: the upload never reached the confirm step — extraction or parse ` +
      `did not complete, so the manager never offered the accept/edit doors`,
  ).toBeVisible({ timeout: 60_000 });
}

test('F5-i 1a: the venous duplex uploads through the real UI (POSITIVE CONTROL)', async ({
  page,
}) => {
  await signupFreshUser(page, 'f5ictl');
  await gotoNoteFormat(page);
  await uploadAndExpectConfirm(page, VENOUS_FORM, 'venous duplex (control)');
});

test('F5-i 1a: the SECOND SHAPE — a blank operative note — uploads through the real UI', async ({
  page,
}) => {
  await signupFreshUser(page, 'f5i');
  await gotoNoteFormat(page);
  await uploadAndExpectConfirm(page, OPERATIVE_NOTE, 'operative note (second shape)');
});
