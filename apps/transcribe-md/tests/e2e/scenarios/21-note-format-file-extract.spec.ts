// ============================================================================
// Scenario 21 — Note-format file upload → REAL text extraction → parse → review
// ----------------------------------------------------------------------------
// Scenario 5 covers the paste path; this covers FILE uploads. The LLM parse is
// mocked, but the file→text extraction is REAL code (txt = UTF-8 decode, pdf =
// unpdf, docx = mammoth) — the exact class the 2026-06-04 PDF incident broke. A
// successful extraction produces non-empty text that the (mocked) parser turns
// into the fixture template, landing on the review editor; a failed/empty
// extraction falls back to the entry view with a clear message.
//   • .txt / .pdf (text layer) / .docx → review editor reached.
//   • image-only .pdf (no text layer) → graceful "couldn't read" fallback.
//
// Reaching the review editor (name pre-filled with the mock fixture) is the
// proof extraction yielded text — under MOCK the parser is only reached with a
// non-empty extracted string. Gated on NOTE_FORMAT_E2E=1.
// ============================================================================

import { resolve } from 'node:path';

import { expect, test, type Page } from '@playwright/test';

import { cleanupTestUsers } from '../helpers/cleanup';
import { signupFreshUser } from '../helpers/signup';
import { gotoNoteFormat } from '../helpers/noteFormat';

const GATE = process.env.NOTE_FORMAT_E2E !== '1';
const GATE_MSG =
  'Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.';

const FIX = (f: string) => resolve(__dirname, '../fixtures/notes', f);
const TXT = FIX('clinical-notes.txt');
const PDF = FIX('sample-note.pdf'); // 2-page PDF with a real text layer
const DOCX = FIX('sample-note.docx'); // minimal OOXML, mammoth-readable
const SCANNED_PDF = FIX('scanned-no-text.pdf'); // no text layer → empty extraction

test.afterEach(() => {
  cleanupTestUsers();
});

/** Drive the upload exactly as a user does: click the visible "Upload a file"
 *  button (which programmatically opens the hidden <input type=file>) and feed
 *  the file via the intercepted chooser. The real-dialog path reliably fires the
 *  input's onChange; a direct setInputFiles on this aria-hidden display:none
 *  input does not. */
async function uploadFile(page: Page, file: string): Promise<void> {
  const [chooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.getByRole('button', { name: /upload a file/i }).click(),
  ]);
  await chooser.setFiles(file);
}

/** Upload a file and assert the extraction + (mocked) parse landed on the
 *  review editor with the fixture template. */
async function uploadAndExpectReview(page: Page, file: string): Promise<void> {
  await uploadFile(page, file);

  // ⚠️ THE UPLOAD PATH LANDS ON THE CONFIRM STEP FIRST, NOT THE EDITOR.
  // Established by DRIVING the production-shaped build, both entry modes:
  //     PASTE  → uploadConfirm=true  reviewEditor=false
  //     UPLOAD → uploadConfirm=true  reviewEditor=false
  //     …then "Something's off" → reviewEditor=TRUE
  // Flag-OFF an upload landed straight on `template-review-editor`. Both
  // components are LIVE — the confirm step is the ACCEPT door, the editor the
  // EDIT door — so each is asserted by its own exact label rather than a
  // matcher that would pass on either surface and prove neither.
  const confirm = page.getByRole('button', { name: /something.s off/i });
  await expect(
    confirm,
    'the upload extracted but never reached the confirm step',
  ).toBeVisible({ timeout: 20_000 });
  await confirm.click();

  await expect(page.getByRole('button', { name: /save & activate/i })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.locator('#nf-name')).toHaveValue('[MOCK] General Follow-up');
}

test('scenario 21: .txt upload → extract → parse → review (MOCK)', async ({ page }) => {
  test.skip(GATE, GATE_MSG);
  await signupFreshUser(page, 's21txt');
  await gotoNoteFormat(page);
  await uploadAndExpectReview(page, TXT);
});

test('scenario 21: .pdf (text layer) upload → unpdf extract → parse → review (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);
  await signupFreshUser(page, 's21pdf');
  await gotoNoteFormat(page);
  await uploadAndExpectReview(page, PDF);
});

test('scenario 21: .docx upload → mammoth extract → parse → review (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);
  await signupFreshUser(page, 's21docx');
  await gotoNoteFormat(page);
  await uploadAndExpectReview(page, DOCX);
});

test('scenario 21: image-only .pdf (no text layer) → graceful fallback (MOCK)', async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);
  await signupFreshUser(page, 's21blank');
  await gotoNoteFormat(page);

  await uploadFile(page, SCANNED_PDF);
  // Empty extraction → "Could not read that file" toast, stays on entry (paste
  // box still visible), never reaches the review editor.
  await expect(page.getByText('Could not read that file')).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel('Paste a note')).toBeVisible();
  await expect(page.getByRole('button', { name: /save & activate/i })).toBeHidden();
});
